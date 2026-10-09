import argparse
import dataclasses
import json
import os
import shutil
import time
import uuid
from datetime import datetime, timezone
import subprocess
import sys
import tempfile
from pathlib import Path

from . import ci, reality, runner
from .decision import Decision, Finding, check, render
from . import __version__, adapters, envsetup
from .report import render_html, render_markdown, to_dict


def collect_test_evidence(repo: Path, base: str, suites: list, timeout: int = 600) -> None:
    """Run each suite at base and at the current state in throwaway worktrees; the user's tree is never touched.

    suites: list of (name, argv, subdir). Uncommitted work is overlaid onto the HEAD worktree so the tests see exactly
    what the agent left behind, and the evidence is bound to that working-tree hash."""
    git = lambda *x: subprocess.run(["git", *reality.GIT_SAFE, "-C", str(repo), *x], capture_output=True, text=True, check=True).stdout.strip()
    head, base_sha = git("rev-parse", "HEAD"), git("rev-parse", "--verify", "--end-of-options", base + "^{commit}")
    subprocess.run(["git", *reality.GIT_SAFE, "-C", str(repo), "worktree", "prune"], capture_output=True)   # leftovers of a killed earlier run
    tmp = Path(tempfile.mkdtemp(prefix="agentmirror_"))
    try:
        for name, sha in (("base", base_sha), ("head", head)):
            git("worktree", "add", "--detach", str(tmp / name), sha)
        for f in reality.changed_files(repo, "HEAD"):  # overlay uncommitted work (modified, new, deleted)
            src, dst = repo / f, tmp / "head" / f
            if src.is_symlink():
                continue   # never follow a link out of the repository (it could point at the signing key or credentials)
            if src.is_file():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            elif dst.exists():
                dst.unlink()
        for i, (name, argv, sub) in enumerate(suites):
            b = runner.run_tests(tmp / "base", argv, timeout=timeout, write=False, suite=name, subdir=sub)
            h = runner.run_tests(tmp / "head", argv, timeout=timeout, baseline_failed=b["failed_ids"], baseline_passed=b["passed_ids"],
                                 write=False, suite=name, subdir=sub, base_repo=tmp / "base")
            reality.safe_write(repo, Path(".agentmirror") / "evidence" / f"testrun_{head[:10]}_{i}.json", json.dumps(reality.sign_record(h)))
    finally:
        for name in ("base", "head"):
            subprocess.run(["git", *reality.GIT_SAFE, "-C", str(repo), "worktree", "remove", "--force", str(tmp / name)], capture_output=True)
        shutil.rmtree(tmp, ignore_errors=True)


def _write_sealed(repo: Path, d) -> None:
    obj = to_dict(d)
    obj["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")   # every run gets a unique seal, so each turn's verdict is a new one
    obj["run_id"] = uuid.uuid4().hex
    obj["repo"] = os.path.realpath(repo)   # bound to this repository: a result copied from another one is rejected by the extension
    page, dec = render_html(d).encode("utf-8"), json.dumps(obj).encode("utf-8")
    last = Path(".agentmirror") / "last"
    reality.safe_write(repo, last / "report.html", page)
    reality.safe_write(repo, last / "decision.json", dec)
    reality.safe_write(repo, last / "decision.sig", reality.seal(page, dec))  # lets the editor extension reject files it did not receive from this tool


def run_hook(a) -> int:
    """Stop/agentStop hook for any agent (Claude Code, VS Code/Copilot, Copilot CLI/cloud agent, Codex, Cursor, Gemini...).

    Informs, never blocks: exit 0 and no "decision" field. The result is (1) printed as a systemMessage for harnesses that
    show it, and (2) written to <repo>/.agentmirror/last/ so an editor extension can display it for harnesses that do not."""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        info = adapters.parse_hook_payload(payload)
        if os.environ.get("AGENTMIRROR_DEBUG") and info["cwd"] and (Path(info["cwd"]) / ".git").exists():
            # structure only (key names, types, lengths): safe to share to diagnose an unknown agent format
            shapes = {"hook_payload": adapters.shape_of(payload), "parsed": {k: bool(v) for k, v in info.items()},
                      "transcript": adapters.transcript_shapes(Path(info["transcript"]).expanduser()) if info["transcript"] else None}
            reality.safe_write(Path(info["cwd"]).resolve(), Path(".agentmirror") / "last" / "payload_shape.json", json.dumps(shapes, indent=2))
        if info["loop"]:
            return 0
        repo = Path(info["cwd"] or ".").resolve()
        if not (repo / ".git").exists():
            return 0
        text, unreadable = info["message"] or "", False
        if not text and info["transcript"]:
            # Agents run the stop hook milliseconds after writing the final answer (observed: 5 ms with Copilot), so the transcript may not
            # contain it yet. Wait briefly for it instead of judging nothing, or worse the previous turn's answer.
            deadline = time.time() + float(os.environ.get("AGENTMIRROR_WAIT", "3"))
            tpath = Path(info["transcript"]).expanduser()
            while True:
                msg, is_final, cop = adapters.final_message_info_file(tpath)
                if msg and (is_final or not cop):
                    text = msg
                    break
                if time.time() >= deadline:
                    text, unreadable = msg or "", not msg
                    break
                time.sleep(0.25)
        dirty = reality.snapshot(repo).dirty
        base, base_how = (a.base, "given") if a.base else reality.default_base(repo, dirty)
        if a.run_tests:
            py = a.python or envsetup.default_python(repo)
            collect_test_evidence(repo, base, [("tests", a.test_cmd[0].format(py=py).split(), "")] if a.test_cmd else
                                  [("tests", f"{py} -m pytest -q -rA -p no:cacheprovider".split(), "")], a.test_timeout)
        extra = ci.ci_evidence(repo, reality.snapshot(repo)) if a.ci else []
        d = check(repo, base, text, extra, a.new_test_failures, message_missing=unreadable)
        d.scope += f" Compared against {base} ({base_how}); if that is not the state before the agent's work, regressions can be hidden."
        msg = render(d)
        obj = to_dict(d)
        obj["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")   # every run gets a unique seal, so each turn's verdict is a new one
        _write_sealed(repo, d)
    except Exception as e:
        msg = f"AgentMirror could not check this turn ({type(e).__name__}: {e}). Nothing was verified."
        try:   # a crash is not a verdict: replace any older sealed result so a stale all-clear is not left on display
            r = locals().get("repo")
            if r is not None and (r / ".git").exists():
                _write_sealed(r, Decision("INSUFFICIENT EVIDENCE", "unknown", False, [], [Finding(
                    "(the check could not complete)", "error", "UNKNOWN", f"AgentMirror failed on this turn ({type(e).__name__}). Nothing was verified.")],
                    "No check completed.", []))
        except Exception:
            pass
    out = {"systemMessage": msg}
    fb = None if locals().get("d") is None else agent_feedback(d)
    if a.feedback_to_agent and fb:
        out.update({"decision": "block", "reason": fb})   # explicit opt-in; stop_hook_active (checked above) limits this to once per chain
    print(json.dumps(out))
    return 0


INSTR_BEGIN, INSTR_END = "<!-- agentmirror:begin -->", "<!-- agentmirror:end -->"


def instructions_block(exe: str) -> str:
    q = f'"{exe}"' if any(ch in exe for ch in " \t") else exe
    return (f"{INSTR_BEGIN}\n## AgentMirror check\n"
            "When you changed code, or you report test results, or you state that something is unaffected, then BEFORE your final answer run this in the "
            "terminal, replacing the heredoc body with the exact draft of your final answer. Show its output under the heading \"AgentMirror check\" and "
            "do not edit it. If it lists a contradicted claim, correct your answer first.\n\n"
            f"```bash\n{q} check --repo . --transcript - --markdown - <<'AGENTMIRROR_EOF' || true\n<your draft final answer>\nAGENTMIRROR_EOF\n```\n{INSTR_END}\n")


def run_agent_instructions(a) -> int:
    exe = shutil.which("agentmirror") or sys.argv[0]
    block = instructions_block(os.path.abspath(exe))
    if not a.write:
        print(block)
        return 0
    target = Path(a.write)
    if target.is_symlink():
        print(f"refusing to write through a symlink: {target}", file=sys.stderr)
        return 3
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    if INSTR_BEGIN in existing:
        print(f"{target} already contains the AgentMirror block; left unchanged.")
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text((existing.rstrip() + "\n\n" if existing.strip() else "") + block, encoding="utf-8")
    print(f"added the AgentMirror block to {target}")
    return 0


def context_for_agent(dec: dict) -> str:
    """Context handed to the agent about ITS PREVIOUS reply. Built from fixed templates and the agent's own claim wording only (never
    repository-controlled strings such as file or test names), so a hostile repository cannot inject instructions through it."""
    why = {"no_downstream_impact": "other modules depend on the code that changed", "tests_pass": "an independent test run or the project's CI contradicts it",
           "backward_compatible": "the public API changed"}
    f = [x for x in dec.get("findings", []) if x.get("kind") != "snapshot"]
    bad = [x for x in f if x.get("verdict") == "CONTRADICTED"]
    unk = [x for x in f if x.get("verdict") == "UNKNOWN"]
    lines = [f"AgentMirror (an independent, deterministic check; not an AI) examined your previous reply. Result: {str(dec.get('status', 'unknown'))[:60]}. "
             f"{len(bad)} contradicted, {len(unk)} unknown."]
    if f and all(x.get("kind") in ("none", None) for x in f):
        lines.append("It found no checkable claims in that reply, so nothing was verified.")
    for x in bad[:5]:
        lines.append(f'- contradicted: "{str(x.get("claim", ""))[:160]}" ({why.get(x.get("kind"), "the repository contradicts it")})')
    lines.append("Begin your next answer with ONE short line telling the user this AgentMirror result, quoting the result text exactly. "
                 "Do not change anything you said earlier unless a claim is listed as contradicted.")
    return "\n".join(lines)


def run_prompt_hook(a) -> int:
    """UserPromptSubmit / userPromptSubmitted hook. Outputs {"additionalContext": ...} once per new sealed verdict, else {}. Never blocks."""
    out: dict = {}
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        info = adapters.parse_hook_payload(payload)
        repo = Path(info["cwd"] or ".").resolve()
        last = repo / ".agentmirror" / "last"
        dec, stamp = reality.read_sealed_result(last)
        if dec is not None and stamp:
            delivered = (last / "delivered.sig").read_text().strip() if (last / "delivered.sig").is_file() else ""
            worth = a.min == "always" or any(x.get("verdict") == "CONTRADICTED" for x in dec.get("findings", []))
            if stamp != delivered and worth:
                out = {"additionalContext": context_for_agent(dec)}
            if stamp != delivered:
                reality.safe_write(repo, Path(".agentmirror") / "last" / "delivered.sig", stamp)   # deliver each verdict at most once
    except Exception:
        out = {}
    print(json.dumps(out))
    return 0


def agent_feedback(d) -> str | None:
    """Text fed BACK TO THE AGENT: built from the agent's own claim wording and fixed explanations, never from repository-controlled strings
    (file names, test names), so a hostile repository cannot use this channel to inject instructions."""
    why = {"no_downstream_impact": "other modules depend on the code that changed", "tests_pass": "an independent test run or the project's CI contradicts it",
           "backward_compatible": "the public API changed"}
    bad = [f for f in d.findings if f.verdict == "CONTRADICTED"]
    if not bad:
        return None
    lines = [f'- "{f.claim[:160]}": {why.get(f.kind, "the repository contradicts it")}' for f in bad[:5]]
    return ("An independent check (AgentMirror) found that these statements in your last message are contradicted by the repository:\n" + "\n".join(lines)
            + "\nPlease verify them and revise your final answer to say only what is true; do not repeat the contradicted statements.")


def final_message(path: Path):
    last = None
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                o = json.loads(line)
            except ValueError:
                continue
            content = (o.get("message") or {}).get("content") if o.get("type") == "assistant" else None
            if isinstance(content, list):
                t = "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text").strip()
                last = t or last
    return last


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="agentmirror")
    ap.add_argument("--version", action="version", version=f"agentmirror {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    dm = sub.add_parser("demo", help="build a small demo repository, check a sample claim and write the sealed result (see the verdict without an agent)")
    dm.add_argument("--path", default=os.path.join(tempfile.gettempdir(), "agentmirror-demo"))
    d = sub.add_parser("doctor", help="check the installation and run the hook path end to end")
    d.add_argument("--repo", default=".")
    ai = sub.add_parser("agent-instructions", help="print (or write) instructions that make a chat agent run AgentMirror itself and show the verdict in the chat")
    ai.add_argument("--write", metavar="PATH", help="append the block to this file (e.g. .github/copilot-instructions.md); idempotent")
    ph = sub.add_parser("prompt-hook", help="UserPromptSubmit hook: hand the previous turn's sealed verdict to the agent once, as context, so it can state it in chat")
    ph.add_argument("--min", choices=["always", "review"], default="always", help="always: every new verdict; review: only when a claim was contradicted")
    c = sub.add_parser("check", help="check an agent's claims against the repository")
    c.add_argument("--repo", default=".")
    c.add_argument("--base", default=None,
                   help="git ref the agent started from (default: HEAD if the tree has uncommitted changes, else HEAD~1)")
    c.add_argument("--transcript", default="-", help="file with the agent's final message/transcript, or - for stdin")
    c.add_argument("--session", help="Claude Code session .jsonl; its final assistant message is used as the transcript")
    c.add_argument("--ci", action="store_true", help="also read the project's CI check results for HEAD (GitHub, via the gh CLI)")
    c.add_argument("--html", metavar="PATH", help="write a self-contained visual report (use - for stdout)")
    c.add_argument("--markdown", metavar="PATH", help="write a compact markdown summary (use - for stdout), e.g. for a PR comment")
    c.add_argument("--ci-sha", help="commit to read CI results for (default: HEAD); use the PR head SHA in pull_request workflows")
    c.add_argument("--new-test-failures", choices=["unknown", "review"], default="unknown",
                   help="failing tests that this change added or changed have no baseline: unknown (default, conservative) or review (raise REVIEW REQUIRED; can alert on network-dependent new tests)")
    c.add_argument("--feedback-to-agent", action="store_true",
                   help="hook mode, opt-in: when a claim is CONTRADICTED, ask the agent (once) to revise its answer (decision=block + reason). Off by default: the hook otherwise never blocks")
    c.add_argument("--hook", action="store_true",
                   help="Claude Code Stop-hook mode: read the hook JSON on stdin, check the final message, print a systemMessage; never blocks")
    c.add_argument("--json", action="store_true")
    c.add_argument("--run-tests", action="store_true",
                   help="run the tests at --base and HEAD in temporary worktrees (network denied, macOS sandbox)")
    c.add_argument("--python", default=None, help="python used to run tests. Default: the project's own .venv/venv/env if present, else the interpreter running agentmirror")
    c.add_argument("--setup", choices=["none", "auto"], default="none",
                   help="auto: build a throwaway virtualenv from the project's declared dependencies (for CI/servers; installs run sandboxed with size/disk guards). Prefer --python with your own venv")
    c.add_argument("--test-timeout", type=int, default=600, help="seconds allowed for each test run (base and head); the whole process group is killed on timeout")
    c.add_argument("--test-cmd", action="append",
                   help="test command; repeat for several suites, optionally 'name=cmd' or 'name@subdir=cmd' to run from a "
                        "subfolder of the repo. {py} is replaced by --python. Default: {py} -m pytest -q -rA -p no:cacheprovider")
    a = ap.parse_args(argv)
    if getattr(a, "base", None) and a.base.startswith("-"):
        ap.error("--base must be a commit or branch name, not an option")
    if a.cmd == "agent-instructions":
        return run_agent_instructions(a)
    if a.cmd == "prompt-hook":
        return run_prompt_hook(a)
    if a.cmd == "demo":
        from .demo import run_demo
        print(json.dumps(run_demo(Path(a.path))))
        return 0
    if a.cmd == "doctor":
        from .doctor import run_doctor
        return run_doctor(Path(a.repo))
    if a.hook:
        return run_hook(a)
    if a.session:
        sp = Path(a.session).expanduser()
        if not sp.is_file():
            raise FileNotFoundError(f"session file not found: {sp}")
        text = adapters.final_message(sp)
        if not text:
            print("No assistant message found in the session file.", file=sys.stderr)
            return 2
    else:
        text = sys.stdin.read(adapters.MAX_TRANSCRIPT_BYTES) if a.transcript == "-" else adapters.read_tail(Path(a.transcript))
    repo = Path(a.repo).resolve()
    dirty = reality.snapshot(repo).dirty if (repo / ".git").exists() else False
    base, base_how = (a.base, "given") if a.base else (reality.default_base(repo, dirty) if (repo / ".git").exists() else ("HEAD~1", "assumed"))
    if a.run_tests and a.setup == "auto":
        venv_root = Path(tempfile.mkdtemp(prefix="agentmirror_env_"))
        try:
            py, notes, aborted = envsetup.build_env(repo, venv_root / "venv", venv_root / "home")
            a.python = py
            if aborted or not py:
                print(f"agentmirror: automatic environment setup incomplete ({'; '.join(notes)[:300]})", file=sys.stderr)
            d = _run(a, repo, base, base_how, text)
        finally:
            shutil.rmtree(venv_root, ignore_errors=True)
        return d
    return _run(a, repo, base, base_how, text)


def _run(a, repo, base, base_how, text):
    if a.python is None:
        a.python = envsetup.default_python(repo)
    a.python = os.path.abspath(os.path.expanduser(a.python))  # relative paths would break once we run inside a worktree
    if a.run_tests:
        specs = a.test_cmd or ["{py} -m pytest -q -rA -p no:cacheprovider"]
        suites = []
        for i, spec in enumerate(specs):
            head_, sep, cmd = spec.partition("=")
            if sep and " " not in head_:
                name, _, sub = head_.partition("@")
            else:
                name, sub, cmd = (f"suite{i + 1}" if len(specs) > 1 else "tests"), "", spec
            if ".." in Path(sub).parts or Path(sub).is_absolute():
                raise SystemExit(f"--test-cmd subdir must be inside the repo: {sub}")
            suites.append((name, cmd.format(py=a.python).split(), sub))
        collect_test_evidence(repo, base, suites, a.test_timeout)
    extra = ci.ci_evidence(repo, reality.snapshot(repo), sha=a.ci_sha) if a.ci else []
    d = check(repo, base, text, extra, a.new_test_failures)
    d.scope += f"; base: {base_how}"
    if a.markdown:
        md = render_markdown(d)
        if a.markdown == "-":
            print(md)
        else:
            Path(a.markdown).write_text(md, encoding="utf-8")
    if a.markdown == "-":
        pass
    elif a.html:
        page = render_html(d)
        if a.html == "-":
            print(page)
        else:
            Path(a.html).write_text(page, encoding="utf-8")
            print(render(d))
    else:
        print(json.dumps(to_dict(d), indent=2) if a.json else render(d))
    return {"REVIEW": 1, "INSUFF": 2}.get(d.status[:6], 0)


def run() -> int:
    """Exit codes: 0 no contradiction found (scoped), 1 review required, 2 insufficient evidence, 3 tool error."""
    try:
        return main()
    except SystemExit:
        raise
    except Exception as e:  # never let a crash look like a verdict
        print(f"agentmirror: tool error: {type(e).__name__}: {e}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(run())
