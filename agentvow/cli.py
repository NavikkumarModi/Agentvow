import argparse
import dataclasses
import json
import os
import re
import shutil
import time
import uuid
from datetime import datetime, timezone
import subprocess
import sys
import tempfile
from pathlib import Path

from . import capsule as capsule_mod, changedcov, ci, reality, runner
from .decision import Decision, Finding, check, render
from . import __version__, adapters, envsetup
from .report import render_html, render_markdown, to_dict


def collect_test_evidence(repo: Path, base: str, suites: list, timeout: int = 600, return_records: bool = False):
    """Run each suite at base and at the current state in throwaway worktrees; the user's tree is never touched.

    suites: list of (name, argv, subdir). Uncommitted work is overlaid onto the HEAD worktree so the tests see exactly
    what the agent left behind, and the evidence is bound to that working-tree hash."""
    git = lambda *x: subprocess.run(["git", *reality.safe_prefix(repo), "-C", str(repo), *x], capture_output=True, text=True, check=True).stdout.strip()
    head, base_sha = git("rev-parse", "HEAD"), git("rev-parse", "--verify", "--end-of-options", base + "^{commit}")
    subprocess.run(["git", *reality.safe_prefix(repo), "-C", str(repo), "worktree", "prune"], capture_output=True)   # leftovers of a killed earlier run
    tmp = Path(tempfile.mkdtemp(prefix="agentvow_"))
    recs: list = []
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
        for i, spec in enumerate(suites):
            name, argv, sub = spec[:3]
            opts = spec[3] if len(spec) > 3 else {}   # {"env_extra": {...}, "meta": {...}} (agent-declared recipe)
            b = runner.run_tests(tmp / "base", argv, timeout=timeout, write=False, suite=name, subdir=sub, env_extra=opts.get("env_extra"), prepare=opts.get("prepare"), pythonpath_rel=opts.get("pythonpath_rel"))
            cov_rc = cov_df = None
            run_argv = argv
            h_cov = None
            if opts.get("coverage"):   # changed-line coverage: run the head tests under coverage (an empty rc file: the project's own coverage config is never loaded)
                if runner.probe(argv[0], "import coverage").returncode != 0:
                    h_cov = {"available": False, "reason": "coverage is not installed in the test environment"}
                else:
                    cov_rc, cov_df = tmp / "empty.rc", tmp / "head" / ".agentvow" / "cov"
                    cov_rc.write_text("[run]\n"); cov_df.parent.mkdir(parents=True, exist_ok=True)
                    wrapped = changedcov.coverage_argv(argv, str(cov_rc), str(cov_df))
                    if wrapped is None:
                        h_cov = {"available": False, "reason": "the test command is not `python -m pytest|unittest`"}
                    else:
                        run_argv = wrapped
            h = runner.run_tests(tmp / "head", run_argv, timeout=timeout, baseline_failed=b["failed_ids"], baseline_passed=b["passed_ids"],
                                 write=False, suite=name, subdir=sub, base_repo=tmp / "base", env_extra=opts.get("env_extra"), prepare=opts.get("prepare"), pythonpath_rel=opts.get("pythonpath_rel"))
            if opts.get("coverage"):
                if h_cov is None and cov_df is not None:
                    cov = changedcov.export_json(argv[0], str(cov_rc), str(cov_df), str(tmp / "cov.json"), tmp / "head", wrap=lambda a_: runner.wrap(a_, tmp / "head", scratch=tmp, env=os.environ))
                    changed = {}
                    for f in reality.changed_files(repo, base):
                        if changedcov.is_source(f) and (tmp / "head" / f).is_file():
                            bt = subprocess.run(["git", "-C", str(tmp / "base"), "show", f"HEAD:{f}"], capture_output=True, text=True)
                            changed[f] = changedcov.added_lines(bt.stdout if bt.returncode == 0 else "", (tmp / "head" / f).read_text(errors="replace"))
                    h_cov = changedcov.measure(changed, cov, tmp / "head")
                h["changed_line_coverage"] = h_cov
            if opts.get("meta"):
                h.update(opts["meta"])
                h["executed_test_files"] = runner.executed_test_files(list(h.get("passed_ids", [])) + list(h.get("failed_ids", [])), tmp / "head")
                tf = [x for x in reality.changed_files(repo, base) if re.fullmatch(r"(?:.*/)?(?:test_[^/]*|[^/]*_test)\.py", x) and (repo / x).is_file()]
                per = lambda ids: sum(1 for i in ids if any(f in runner.executed_test_files([i], tmp / "head") for f in tf))
                h["scoped"] = {"files": tf, "passed": per(h.get("passed_ids", [])), "failed": per(h.get("failed_ids", []))}
                if str(h.get("summary", "")).startswith("missing dependency"):   # the environment came ONLY from the declaration: say so
                    h["summary"] = re.sub(r"\(pass --python.*\)$", "(the agent's declared recipe does not provide it, so the declared preconditions were insufficient)", h["summary"])
            if return_records:   # an additional context for the evidence pack: nothing is written as evidence
                recs.append(h)
                continue
            reality.safe_write(repo, Path(".agentvow") / "evidence" / f"testrun_{head[:10]}_{i}.json", json.dumps(reality.sign_record(h)))
    finally:
        for name in ("base", "head"):
            subprocess.run(["git", *reality.safe_prefix(repo), "-C", str(repo), "worktree", "remove", "--force", str(tmp / name)], capture_output=True)
        shutil.rmtree(tmp, ignore_errors=True)
    return recs if return_records else None


def _ensure_coverage(py: str, venv_root: Path) -> None:
    """Install `coverage` into an environment Agentvow itself built (never into a user-supplied one), with the same guards as every other install."""
    if runner.probe(py, "import coverage").returncode == 0:
        return
    home = venv_root / "home"
    envsetup._pip(venv_root / "venv", home / "proj" if (home / "proj").is_dir() else home, home, ["install", "-q", "coverage"], 300, envsetup.MAX_VENV, envsetup.MIN_FREE)


def _write_sealed(repo: Path, d) -> None:
    obj = to_dict(d)
    obj["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")   # every run gets a unique seal, so each turn's verdict is a new one
    obj["run_id"] = uuid.uuid4().hex
    obj["repo"] = os.path.realpath(repo)   # bound to this repository: a result copied from another one is rejected by the extension
    page, dec = render_html(d).encode("utf-8"), json.dumps(obj).encode("utf-8")
    last = Path(".agentvow") / "last"
    reality.safe_write(repo, last / "report.html", page)
    reality.safe_write(repo, last / "decision.json", dec)
    reality.safe_write(repo, last / "decision.sig", reality.seal(page, dec))  # lets the editor extension reject files it did not receive from this tool
    return obj["run_id"]


def _collect_from_capsule(repo: Path, base: str, cap: dict, timeout: int, coverage: bool = False) -> str:
    """Replay the head and base tests in a clean environment built from the captured packages. -> '' on success or a reason (nothing was run)."""
    from . import recipe as recipe_mod
    rec, files = capsule_mod.to_recipe(cap, ["-m", "pytest", "-q"])
    venv_root = Path(tempfile.mkdtemp(prefix="agentvow_env_"))
    try:
        py, notes, aborted = recipe_mod.build_env(repo, rec, venv_root / "venv", venv_root / "home", extra_files=files)
        if not py or aborted:
            return "the environment could not be built" + (f" ({aborted})" if aborted else "")
        if coverage:
            _ensure_coverage(py, venv_root)
        targv = [*rec.test, "-rA", "-p", "no:cacheprovider"]
        meta = {"recipe_sha256": rec.sha256, "declared_by": "captured environment", "runner_supplied": rec.runner_supplied, "dropped_pins": list(rec.dropped_pins), "capture_source": cap.get("capture_source", "local"),
                "capsule_python": cap["python_version"], "replay_python": ".".join(map(str, sys.version_info[:3]))}
        collect_test_evidence(repo, base, [("tests", [py, *targv], "", {"env_extra": rec.env, "pythonpath_rel": rec.local_roots, "coverage": coverage, "meta": meta})], timeout)
        return ""
    finally:
        shutil.rmtree(venv_root, ignore_errors=True)


def recipe_mod_error():
    from . import recipe as recipe_mod
    return recipe_mod.RecipeError


def _collect_native(repo: Path, base: str, timeout: int, coverage: bool) -> str:
    """Replay in an environment Agentvow builds from the project's own files (setup files, CI workflow, Dockerfiles, requirements files: see baseline.py), with optional changed-line coverage. -> '' or the reason nothing ran."""
    from . import baseline
    venv_root = Path(tempfile.mkdtemp(prefix="agentvow_env_"))
    try:
        py, rec, notes, aborted = baseline.prepare(repo, venv_root / "venv", venv_root / "home")
        if not py or aborted:
            return "the environment could not be built" + (f" ({aborted})" if aborted else "")
        if coverage:
            _ensure_coverage(py, venv_root)
        collect_test_evidence(repo, base, [("tests", [py, "-m", "pytest", "-q", "-rA", "-p", "no:cacheprovider"], "", {"coverage": coverage, "env_extra": rec.env, "pythonpath_rel": rec.local_roots})], timeout)
        return ""
    except (OSError, subprocess.SubprocessError, ValueError, recipe_mod_error()) as e:   # nothing may escape the hook's background worker
        return f"the environment could not be built ({type(e).__name__})"
    finally:
        shutil.rmtree(venv_root, ignore_errors=True)


def _spawn_finish(repo: Path, base: str, text: str, turn_changed, run_id: str, a, from_capsule: bool = False) -> None:   # also passes --changed-coverage, --evidence-pack
    """Run the tests AFTER the hook has returned (they can take minutes; agents give hooks about a minute): a detached process updates the result."""
    spool = Path(tempfile.mkdtemp(prefix="agentvow_turn_"))
    (spool / "message.txt").write_text(text, encoding="utf-8")
    (spool / "changed.json").write_text(json.dumps(turn_changed))
    cmd = reality.isolated_argv(sys.executable, "finish-turn", "--repo", str(repo), "--base", base, "--spool", str(spool), "--run-id", run_id,
                                "--test-timeout", str(a.test_timeout), *(["--python", a.python] if a.python else []), *(["--from-capsule"] if from_capsule else []), *(["--changed-coverage"] if getattr(a, "changed_coverage", False) else []), *(["--evidence-pack"] if getattr(a, "evidence_pack", False) else []))
    subprocess.Popen(cmd, cwd=tempfile.gettempdir(), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def run_finish_turn(a) -> int:
    """Background half of --background-tests. One run per repository at a time, serialised with an OS file lock kept in the user's private
    Agentvow home (not in the repository: a repository-writable lock could be planted to stop tests from ever running; an OS lock also vanishes with
    its process, so there is no stale-pid case). A newer turn waits for the older run, then runs; the older run's result is dropped if a newer
    verdict has already replaced the one it started from."""
    import fcntl
    import hashlib
    repo, spool = Path(a.repo).resolve(), Path(a.spool)
    lockdir = reality.home_dir() / "locks"
    lockdir.mkdir(parents=True, exist_ok=True)
    fd = os.open(lockdir / (hashlib.sha256(str(repo).encode()).hexdigest()[:16] + ".lock"), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        text = (spool / "message.txt").read_text(encoding="utf-8")
        turn_changed = json.loads((spool / "changed.json").read_text())
        deadline = time.time() + 2 * a.test_timeout + 120
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.time() > deadline:
                    return 0
                time.sleep(2)
        note = " Includes a test run that finished after the agent stopped."
        pack_on = getattr(a, "evidence_pack", False)
        cov = getattr(a, "changed_coverage", False) or pack_on
        if getattr(a, "from_capsule", False):
            cap = capsule_mod.load(repo)
            why = _collect_from_capsule(repo, a.base, cap, a.test_timeout, cov) if cap else "no capsule exists for this exact state (it changed after the agent stopped)"
            note = (" Includes a test run in a clean environment built from the packages captured when the agent stopped." if not why else
                    f" The capture-based test run was not made: {why}. Nothing was verified by test execution.")
        elif pack_on:   # no capsule: the project's own setup is the only context, and the pack says the captured replay is missing
            why = _collect_native(repo, a.base, a.test_timeout, cov)
            note = (" Includes a test run in an environment built from the project's own setup, after the agent stopped." if not why else
                    f" The test run was not made: {why}. Nothing was verified by test execution.")
        else:
            py = a.python or envsetup.default_python(repo)
            collect_test_evidence(repo, a.base, [("tests", f"{py} -m pytest -q -rA -p no:cacheprovider".split(), "")], a.test_timeout)
        d = check(repo, a.base, text, None, "unknown", changed_override=turn_changed)
        if pack_on:
            from . import pack as pack_mod
            try:
                d.pack = pack_mod.build(a, repo, a.base, d, collect_test_evidence)
            except Exception as e:   # additional information only: never hide or change the verdict
                note += f" The evidence pack could not be built ({type(e).__name__})."
        d.scope += note
        cur = reality.read_sealed_result(repo / ".agentvow" / "last")[0]
        if cur and cur.get("run_id") == a.run_id:   # still this turn's result: a newer turn must not be overwritten by a slow run
            _write_sealed(repo, d)
        return 0
    finally:
        os.close(fd)
        shutil.rmtree(spool, ignore_errors=True)


def run_post_test_hook(a) -> int:
    """PostToolUse hook (Claude Code `Bash` tool): when the command the agent just ran looks like a test run, capture the environment NOW, so the capsule describes the state at the test run
    and not only at the stop. Silent and fast; never blocks and never prints a decision; any problem is swallowed (the Stop hook still captures)."""
    try:
        payload = json.loads(sys.stdin.read(1_000_000) or "{}")
        tool = str(payload.get("tool_name") or payload.get("toolName") or "")
        cmd = (payload.get("tool_input") or payload.get("toolInput") or {}).get("command", "") if isinstance(payload.get("tool_input") or payload.get("toolInput"), dict) else ""
        repo = Path(str(payload.get("cwd") or ".")).resolve()
        if tool.lower() in ("bash", "shell", "run_shell_command") and capsule_mod.looks_like_test_command(str(cmd)) and (repo / ".git").exists():
            capsule_mod.capture(repo, a.python, source="post-test", command=str(cmd))
    except Exception:
        pass
    return 0


def run_hook(a) -> int:
    """Stop/agentStop hook for any agent (Claude Code, VS Code/Copilot, Copilot CLI/cloud agent, Codex, Cursor, Gemini...).

    Informs, never blocks: exit 0 and no "decision" field. The result is (1) printed as a systemMessage for harnesses that
    show it, and (2) written to <repo>/.agentvow/last/ so an editor extension can display it for harnesses that do not."""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        info = adapters.parse_hook_payload(payload)
        if os.environ.get("AGENTVOW_DEBUG") and info["cwd"] and (Path(info["cwd"]) / ".git").exists():
            # structure only (key names, types, lengths): safe to share to diagnose an unknown agent format
            shapes = {"hook_payload": adapters.shape_of(payload), "parsed": {k: bool(v) for k, v in info.items()},
                      "transcript": adapters.transcript_shapes(Path(info["transcript"]).expanduser()) if info["transcript"] else None}
            reality.safe_write(Path(info["cwd"]).resolve(), Path(".agentvow") / "last" / "payload_shape.json", json.dumps(shapes, indent=2))
        loop = bool(info["loop"])   # second pass after a feedback block: still check (the revised answer may repeat the claim) but never block again
        repo = Path(info["cwd"] or ".").resolve()
        if not (repo / ".git").exists():
            return 0
        text, unreadable = info["message"] or "", False
        if not text and info["transcript"]:
            # Agents run the stop hook milliseconds after writing the final answer (observed: 5 ms with Copilot), so the transcript may not
            # contain it yet. Wait briefly for it instead of judging nothing, or worse the previous turn's answer.
            deadline = time.time() + float(os.environ.get("AGENTVOW_WAIT", "3"))
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
        prev = reality.load_turn_state(repo)
        turn_changed = reality.changed_this_turn(repo, prev) if prev else None
        d = check(repo, base, text, extra, a.new_test_failures, message_missing=unreadable, changed_override=turn_changed)
        d.scope += (" Changes are counted since the previous Agentvow check in this repository (this turn, plus anything you edited in between)."
                    if prev else " First check in this repository: every uncommitted change is counted, including work that predates this turn.")
        if prev and not turn_changed and reality.changed_files(repo, "HEAD"):
            d.scope += (f" Note: no change was counted this turn although {len(reality.changed_files(repo, 'HEAD'))} file(s) are uncommitted; if the agent did edit files, "
                        "the turn baseline may have been reset (any process running as you can write it), so do not read 'no changes' as proof.")
        d.scope += f" Compared against {base} ({base_how}); if that is not the state before the agent's work, regressions can be hidden."
        msg = render(d)
        run_id = _write_sealed(repo, d)
        reality.save_turn_state(repo)
        pack_flag = getattr(a, "evidence_pack", False)
        if (a.background_tests or pack_flag) and not a.run_tests and not loop:
            captured = False
            if getattr(a, "capture", False) or pack_flag:   # record the agent's packages NOW, while its environment is as it left it, and replay from that later
                try:
                    captured = capsule_mod.capture(repo, a.python)[0] is not None
                except Exception:
                    captured = False
            _spawn_finish(repo, base, text, turn_changed, run_id, a, from_capsule=captured)
    except Exception as e:
        msg = f"Agentvow could not check this turn ({type(e).__name__}: {e}). Nothing was verified."
        try:   # a crash is not a verdict: replace any older sealed result so a stale all-clear is not left on display
            r = locals().get("repo")
            if r is not None and (r / ".git").exists():
                _write_sealed(r, Decision("INSUFFICIENT EVIDENCE", "unknown", False, [], [Finding(
                    "(the check could not complete)", "error", "UNKNOWN", f"Agentvow failed on this turn ({type(e).__name__}). Nothing was verified.")],
                    "No check completed.", []))
        except Exception:
            pass
    out = {"systemMessage": msg}
    fb = None if locals().get("d") is None else agent_feedback(d)
    if a.feedback_to_agent and fb and not loop:
        out.update({"decision": "block", "reason": fb})   # explicit opt-in; stop_hook_active (checked above) limits this to once per chain
    print(json.dumps(out))
    return 0


INSTR_BEGIN, INSTR_END = "<!-- agentvow:begin -->", "<!-- agentvow:end -->"


def instructions_block(exe: str) -> str:
    q = f'"{exe}"' if any(ch in exe for ch in " \t") else exe
    return (f"{INSTR_BEGIN}\n## Agentvow check\n"
            "When you changed code, or you report test results, or you state that something is unaffected, then BEFORE your final answer run this in the "
            "terminal, replacing the heredoc body with the exact draft of your final answer. Show its output under the heading \"Agentvow check\" and "
            "do not edit it. If it lists a contradicted claim, correct your answer first.\n\n"
            f"```bash\n{q} check --repo . --transcript - --markdown - <<'AGENTVOW_EOF' || true\n<your draft final answer>\nAGENTVOW_EOF\n```\n{INSTR_END}\n")


def run_init(a) -> int:
    """`agentvow init`: preview, confirm, back up, write; then an end-to-end self test. Never edits silently and never overwrites a settings file it cannot parse."""
    from . import init as init_mod
    repo = Path(a.repo).resolve()
    if a.user and a.shared:
        print("agentvow init: choose --user or --shared, not both", file=sys.stderr)
        return 3
    path = init_mod.target_path(repo, a.shared, a.user)
    bad = init_mod.symlink_problem(path, None if a.user else repo)
    if bad:
        print(f"agentvow init: {bad}", file=sys.stderr)
        return 3
    settings, err = init_mod.load(path)
    if err:
        print(f"agentvow init: {err}", file=sys.stderr)
        return 3
    prefix = init_mod.command_prefix()
    new, changes = init_mod.unmerge(settings) if a.remove else init_mod.merge(settings, prefix, a.force)
    exclude = None if (a.remove or a.user) else init_mod.exclude_line_needed(repo)
    print(f"Target: {path}" + ("" if path.exists() else "  (does not exist yet; it will be created)"))
    for c in changes:
        print(f"  - {c}")
    if exclude:
        print(f"  - add `.agentvow/` to {exclude} (local to this clone; no tracked file changes)")
    if not a.remove and not init_mod.has_python_env(repo):
        print("  ! no .venv, venv or env folder and no active virtual environment: the hooks cannot record the agent's packages until the project has one (or pass --python in the hook command)")
    if a.shared and not a.remove:
        print("  ! .claude/settings.json is normally committed: every teammate's Claude Code would run these hooks")
    if new == settings and not exclude:
        print("Nothing to change.")
        return 0
    if a.dry_run:
        print("Dry run: nothing was written.")
        return 0
    if not a.yes:
        if not sys.stdin.isatty():
            print("Not written: confirm with --yes (or run this in a terminal).", file=sys.stderr)
            return 2
        if input("Write these changes? [y/N] ").strip().lower() not in ("y", "yes"):
            print("Not written.")
            return 2
    b = init_mod.backup(path) if new != settings else None
    if new != settings:
        init_mod.write_json(path, new)
    if exclude:
        try:
            exclude.parent.mkdir(parents=True, exist_ok=True)
            lead = ""
            if exclude.exists() and exclude.stat().st_size:
                lead = "" if exclude.read_text(encoding="utf-8", errors="replace").endswith("\n") else "\n"
            with exclude.open("a", encoding="utf-8") as f:
                f.write(lead + ".agentvow/\n")
        except OSError as e:
            print(f"  ! could not update {exclude} ({type(e).__name__})", file=sys.stderr)
    print(f"Written: {path}" + (f" (previous version kept as {b.name})" if b else ""))
    if a.remove or a.no_verify:
        return 0
    from .doctor import self_test
    ok, detail = self_test(sys.executable)
    print(("Self test passed: " if ok else "Self test FAILED: ") + detail)
    print("Next: work with Claude Code as usual; run `agentvow doctor --repo .` any time. The hooks never block the agent; delete them with `agentvow init --remove`.")
    return 0 if ok else 1


def run_agent_instructions(a) -> int:
    exe = shutil.which("agentvow") or sys.argv[0]
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
        print(f"{target} already contains the Agentvow block; left unchanged.")
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text((existing.rstrip() + "\n\n" if existing.strip() else "") + block, encoding="utf-8")
    print(f"added the Agentvow block to {target}")
    return 0


def context_for_agent(dec: dict) -> str:
    """Context handed to the agent about ITS PREVIOUS reply. Built from fixed templates and the agent's own claim wording only (never
    repository-controlled strings such as file or test names), so a hostile repository cannot inject instructions through it."""
    why = {"no_downstream_impact": "other modules depend on the code that changed", "tests_pass": "an independent test run or the project's CI contradicts it",
           "backward_compatible": "the public API changed", "files_scope": "git's change list disagrees with what it says about files", "docs_updated": "no documentation file was changed",
           "lint_clean": "the linter reports findings"}
    f = [x for x in dec.get("findings", []) if x.get("kind") != "snapshot"]
    bad = [x for x in f if x.get("verdict") == "CONTRADICTED"]
    unk = [x for x in f if x.get("verdict") == "UNKNOWN"]
    lines = [f"Agentvow (an independent, deterministic check; not an AI) examined your previous reply. Result: {str(dec.get('status', 'unknown'))[:60]}. "
             f"{len(bad)} contradicted, {len(unk)} unknown."]
    if f and all(x.get("kind") in ("none", None) for x in f):
        lines.append("It found no checkable claims in that reply, so nothing was verified.")
    for x in bad[:5]:
        lines.append(f'- contradicted: "{str(x.get("claim", ""))[:160]}" ({why.get(x.get("kind"), "the repository contradicts it")})')
    lines.append("Begin your next answer with ONE short line telling the user this Agentvow result, quoting the result text exactly. "
                 "Do not change anything you said earlier unless a claim is listed as contradicted.")
    return "\n".join(lines)


def run_prompt_hook(a) -> int:
    """UserPromptSubmit / userPromptSubmitted hook. Outputs {"additionalContext": ...} once per new sealed verdict, else {}. Never blocks."""
    out: dict = {}
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        info = adapters.parse_hook_payload(payload)
        repo = Path(info["cwd"] or ".").resolve()
        last = repo / ".agentvow" / "last"
        dec, stamp = reality.read_sealed_result(last)
        if dec is not None and stamp:
            mark = reality.seal(b"delivered", stamp.encode())   # keyed: a writer without the signing key cannot pre-mark a verdict as delivered
            delivered = (last / "delivered.sig").read_text().strip() if (last / "delivered.sig").is_file() else ""
            stamp_is_delivered = delivered == mark
            worth = a.min == "always" or any(x.get("verdict") == "CONTRADICTED" for x in dec.get("findings", []))
            if not stamp_is_delivered and worth:
                out = {"additionalContext": context_for_agent(dec)}
            if not stamp_is_delivered:
                reality.safe_write(repo, Path(".agentvow") / "last" / "delivered.sig", mark)   # deliver each verdict at most once
    except Exception:
        out = {}
    print(json.dumps(out))
    return 0


def agent_feedback(d) -> str | None:
    """Text fed BACK TO THE AGENT: built from the agent's own claim wording and fixed explanations, never from repository-controlled strings
    (file names, test names), so a hostile repository cannot use this channel to inject instructions."""
    why = {"no_downstream_impact": "other modules depend on the code that changed", "tests_pass": "an independent test run or the project's CI contradicts it",
           "backward_compatible": "the public API changed", "files_scope": "git's change list disagrees with what it says about files", "docs_updated": "no documentation file was changed",
           "lint_clean": "the linter reports findings"}
    bad = [f for f in d.findings if f.verdict == "CONTRADICTED"]
    if not bad:
        return None
    lines = [f'- "{f.claim[:160]}": {why.get(f.kind, "the repository contradicts it")}' for f in bad[:5]]
    return ("An independent check (Agentvow) found that these statements in your last message are contradicted by the repository:\n" + "\n".join(lines)
            + "\nPlease verify them and revise your final answer to say only what is true; do not repeat the contradicted statements."
            + "\nStart your revised answer with one short line telling the user that an independent check (Agentvow) flagged your previous answer and which statement it corrected, "
              "so the user knows the answer changed and why.")


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
    ap = argparse.ArgumentParser(prog="agentvow")
    ap.add_argument("--version", action="version", version=f"agentvow {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ft = sub.add_parser("finish-turn", help=argparse.SUPPRESS)
    for flag in ("--repo", "--base", "--spool", "--run-id"):
        ft.add_argument(flag, required=True)
    ft.add_argument("--python", default=None)
    ft.add_argument("--test-timeout", type=int, default=600)
    pt = sub.add_parser("post-test-hook", help="PostToolUse hook: capture the environment right after the agent runs a test command (see docs/CAPSULES.md)")
    pt.add_argument("--python", default=None, help="the interpreter the agent uses (default: the project's .venv/venv/env or the active VIRTUAL_ENV)")
    cp = sub.add_parser("capture", help="record the Python packages of the agent's environment for the current state, so a later check can replay from them")
    cp.add_argument("--repo", default=".")
    cp.add_argument("--python", default=None, help="the interpreter the agent used (default: the project's .venv/venv/env or the active VIRTUAL_ENV)")
    cp.add_argument("--export", metavar="FILE", default=None, help="also write a portable, unsigned capture bundle (agentvow-capture/1) bound to the content hash of the working tree, for a separate verifier (`check --from-capture`)")
    ft.add_argument("--from-capsule", action="store_true")
    ft.add_argument("--changed-coverage", action="store_true")
    ft.add_argument("--evidence-pack", action="store_true")
    au = sub.add_parser("audit-env", help="compare what an agent session installed/exported with what the repository and the recipe declare")
    au.add_argument("--repo", default=".")
    au.add_argument("--session", required=True, help="Claude Code session .jsonl or Copilot CLI events.jsonl")
    au.add_argument("--recipe", default=None)
    au.add_argument("--json", action="store_true")
    dm = sub.add_parser("demo", help="build a small demo repository, check a sample claim and write the sealed result (see the verdict without an agent)")
    dm.add_argument("--path", default=os.path.join(tempfile.gettempdir(), "agentvow-demo"))
    d = sub.add_parser("doctor", help="check the installation and run the hook path end to end")
    d.add_argument("--repo", default=".")
    rc = sub.add_parser("receipt", help="turn the JSON of `check --json` into a minimal, shareable receipt (no source, no free text, no environment values) bound to the content hash of the files")
    rc.add_argument("--decision", required=True, help="file with the JSON printed by `agentvow check --json` (or .agentvow/last/decision.json)")
    rc.add_argument("--repo-slug", required=True, help="owner/name as the CI runner knows it")
    rc.add_argument("--repo", default=".")
    rc.add_argument("--base", default="")
    rc.add_argument("--pr", type=int, default=None, help="pull request number (optional)")
    rc.add_argument("-o", "--output", default="-")
    po = sub.add_parser("policy", help="evaluate a receipt under a policy (allow / block / needs_acknowledgement), or print the default policy")
    po.add_argument("action", choices=["evaluate", "init", "explain"])
    po.add_argument("--policy", default=None, help="policy file (agentvow-policy/1). In CI take it from the BASE branch, never from the pull request")
    po.add_argument("--receipt", default=None)
    po.add_argument("--result", default=None, help="for `explain`: the JSON that `policy evaluate` printed")
    po.add_argument("--ack", action="append", default=[], help="acknowledgement file (agentvow-ack/1); only counts for exactly this receipt and a listed acknowledger")
    pr_ = sub.add_parser("pilot-report", help="a mechanical evidence report over a directory of receipts (counts, decisions under a policy, reproducibility, coverage, what could not be recreated); no claim about defects prevented")
    pr_.add_argument("--receipts", required=True, help="directory of receipt JSON files (gate artifacts or the control plane's export)")
    pr_.add_argument("--acks", default=None, help="directory of acknowledgement JSON files")
    pr_.add_argument("--policy", default=None)
    pr_.add_argument("--title", default="Agent pull request evidence report")
    pr_.add_argument("--example", action="store_true", help="label the report as built from synthetic data")
    pr_.add_argument("-o", "--output", default="-")
    ini = sub.add_parser("init", help="add the Claude Code hooks (capture after tests, check at stop) to a settings file, with a preview, a confirmation and a backup")
    ini.add_argument("--repo", default=".")
    ini.add_argument("--agent", choices=["claude"], default="claude", help="only Claude Code is supported by this command (GitHub Copilot: the VS Code extension command 'Agentvow: Add the agent hook')")
    ini.add_argument("--shared", action="store_true", help="write .claude/settings.json (committed settings run the hooks for every teammate) instead of the personal .claude/settings.local.json")
    ini.add_argument("--user", action="store_true", help="write ~/.claude/settings.json (all your projects)")
    ini.add_argument("--dry-run", action="store_true", help="show what would change and write nothing")
    ini.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    ini.add_argument("--remove", action="store_true", help="remove the hooks this command added (other settings and hooks are kept)")
    ini.add_argument("--force", action="store_true", help="replace an Agentvow hook that is already set with a different command (default: leave it as it is)")
    ini.add_argument("--no-verify", action="store_true", help="skip the end-to-end self test after writing")
    ai = sub.add_parser("agent-instructions", help="print (or write) instructions that make a chat agent run Agentvow itself and show the verdict in the chat")
    ai.add_argument("--write", metavar="PATH", help="append the block to this file (e.g. .github/copilot-instructions.md); idempotent")
    ph = sub.add_parser("prompt-hook", help="UserPromptSubmit hook: hand the previous turn's sealed verdict to the agent once, as context, so it can state it in chat")
    ph.add_argument("--min", choices=["always", "review"], default="always", help="always: every new verdict; review: only when a claim was contradicted")
    c = sub.add_parser("check", help="check an agent's claims against the repository")
    c.add_argument("--repo", default=".")
    c.add_argument("--base", default=None,
                   help="git ref the agent started from (default: HEAD if the tree has uncommitted changes, else HEAD~1)")
    c.add_argument("--transcript", default="-", help="file with the agent's final message/transcript, or - for stdin")
    c.add_argument("--session", help="Claude Code session .jsonl; its final assistant message is used as the transcript")
    c.add_argument("--recipe", metavar="FILE", help="replay the agent's own declared preconditions (agentvow-recipe/1 JSON): a clean environment built ONLY from its declared pip steps, then its declared test command at base and head")
    c.add_argument("--ci-wait", type=int, default=0, metavar="SECONDS", help="with --ci: wait up to this long for test jobs that are still running (default 0)")
    c.add_argument("--ci", action="store_true", help="also read the project's CI check results for HEAD (GitHub, via the gh CLI)")
    c.add_argument("--html", metavar="PATH", help="write a self-contained visual report (use - for stdout)")
    c.add_argument("--markdown", metavar="PATH", help="write a compact markdown summary (use - for stdout), e.g. for a PR comment")
    c.add_argument("--ci-sha", help="commit to read CI results for (default: HEAD); use the PR head SHA in pull_request workflows")
    c.add_argument("--new-test-failures", choices=["unknown", "review"], default="unknown",
                   help="failing tests that this change added or changed have no baseline: unknown (default, conservative) or review (raise REVIEW REQUIRED; can alert on network-dependent new tests)")
    c.add_argument("--capture", action="store_true", help="with --hook --background-tests: record the agent's Python packages when it stops and run the background tests in a clean environment built from them")
    c.add_argument("--background-tests", action="store_true", help="with --hook: after the hook returns, run the tests in the background and update the result when they finish")
    c.add_argument("--feedback-to-agent", action="store_true",
                   help="hook mode, opt-in: when a claim is CONTRADICTED, ask the agent (once) to revise its answer (decision=block + reason). Off by default: the hook otherwise never blocks")
    c.add_argument("--hook", action="store_true",
                   help="Claude Code Stop-hook mode: read the hook JSON on stdin, check the final message, print a systemMessage; never blocks")
    c.add_argument("--json", action="store_true")
    c.add_argument("--evidence-pack", action="store_true",
                   help="run the tests, measure changed-line coverage, replay from the captured environment when a capsule exists AND from the project's own setup, and add an Evidence pack "
                        "section (receipt, reproducibility, coverage) to the report; informational, verdicts are unchanged")
    c.add_argument("--from-capture", metavar="FILE", default=None,
                   help="with --run-tests: replay the tests in a clean environment built from a portable capture bundle (made by `capture --export`, NOT authenticated). It is accepted only if its content hash equals this checkout's; otherwise nothing is replayed")
    c.add_argument("--from-capsule", action="store_true",
                   help="with --run-tests: replay the tests in a clean environment built from the packages captured by `agentvow capture` for this exact state (fails closed when there is none)")
    c.add_argument("--changed-coverage", action="store_true",
                   help="with --run-tests: also report how many of the changed executable source lines the tests actually ran (installs `coverage` in an environment Agentvow builds; verdicts are not affected)")
    c.add_argument("--run-tests", action="store_true",
                   help="run the tests at --base and HEAD in temporary worktrees (network denied, macOS sandbox)")
    c.add_argument("--python", default=None, help="python used to run tests. Default: the project's own .venv/venv/env if present, else the interpreter running agentvow")
    c.add_argument("--setup", choices=["none", "auto"], default="none",
                   help="auto: build a throwaway virtualenv from the project's declared dependencies (for CI/servers; installs run sandboxed with size/disk guards). Prefer --python with your own venv")
    c.add_argument("--test-timeout", type=int, default=600, help="seconds allowed for each test run (base and head); the whole process group is killed on timeout")
    c.add_argument("--test-cmd", action="append",
                   help="test command; repeat for several suites, optionally 'name=cmd' or 'name@subdir=cmd' to run from a "
                        "subfolder of the repo. {py} is replaced by --python. Default: {py} -m pytest -q -rA -p no:cacheprovider")
    a = ap.parse_args(argv)
    if getattr(a, "base", None) and a.base.startswith("-"):
        ap.error("--base must be a commit or branch name, not an option")
    if a.cmd == "init":
        return run_init(a)
    if a.cmd == "pilot-report":
        from . import pilot_report as pr_mod
        try:
            rcpts, bad = pr_mod.load(a.receipts)
            acks = pr_mod.load_acks(a.acks) if a.acks else []
            pol = json.loads(Path(a.policy).read_text(encoding="utf-8")) if a.policy else None
        except (OSError, ValueError) as e:
            print(f"agentvow pilot-report: {type(e).__name__}: {str(e)[:120]}", file=sys.stderr)
            return 3
        s = pr_mod.summarize(rcpts, pol, acks)
        s["invalid"] = bad
        text = pr_mod.render_markdown(s, a.title, a.example) + (f"\n_{bad} file(s) in the receipts directory were not valid receipts and were skipped._\n" if bad else "")
        if a.output == "-":
            print(text)
        else:
            Path(a.output).write_text(text, encoding="utf-8")
        return 0
    if a.cmd == "receipt":
        from . import policy as policy_mod
        try:
            dec = json.loads(Path(a.decision).read_text(encoding="utf-8"))
            tree = reality.git_tree_hash(Path(a.repo).resolve())
            if not isinstance(dec, dict):
                raise ValueError("the decision file is not a JSON object")
            if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", str(dec.get("commit", ""))):
                # a check that could not collect (no base, too little history) reports its commit as "?"; the receipt is about the commit that was checked out
                dec["commit"] = reality._git(Path(a.repo).resolve(), "rev-parse", "HEAD")
        except (OSError, ValueError, reality.CollectorError) as e:
            print(f"agentvow receipt: {type(e).__name__}: {str(e)[:120]}", file=sys.stderr)
            return 3
        out = json.dumps(policy_mod.build_receipt(dec, a.repo_slug, tree, a.base, a.pr), indent=2) + "\n"
        if a.output == "-":
            print(out, end="")
        else:
            Path(a.output).write_text(out, encoding="utf-8")
        return 0
    if a.cmd == "policy":
        from . import policy as policy_mod
        if a.action == "init":
            print(json.dumps(policy_mod.DEFAULT_POLICY, indent=2))
            return 0
        if a.action == "explain":
            from . import explain as explain_mod
            try:
                res = json.loads(Path(a.result).read_text(encoding="utf-8"))
                if not isinstance(res, dict) or not isinstance(res.get("reasons", []), list):
                    raise ValueError("not an evaluation result")
            except (OSError, ValueError, TypeError) as e:
                print(f"agentvow policy explain: {type(e).__name__}: {str(e)[:120]}", file=sys.stderr)
                return 3
            print(explain_mod.explain(res, [res["receipt_sha"]] if isinstance(res.get("receipt_sha"), str) and res.get("receipt_sha") else (), res.get("acknowledgers") if isinstance(res.get("acknowledgers"), list) else None))
            return 0
        try:
            rcpt = json.loads(Path(a.receipt).read_text(encoding="utf-8"))
            pol = json.loads(Path(a.policy).read_text(encoding="utf-8")) if a.policy else None
            acks = [json.loads(Path(f).read_text(encoding="utf-8")) for f in a.ack]
        except (OSError, ValueError, TypeError) as e:
            print(f"agentvow policy: {type(e).__name__}: {str(e)[:120]}", file=sys.stderr)
            return 3
        res = policy_mod.evaluate(rcpt, pol, acks)
        print(json.dumps(res, indent=2))
        return {"allow": 0, "block": 1, "needs_acknowledgement": 2}[res["decision"]]
    if a.cmd == "agent-instructions":
        return run_agent_instructions(a)
    if a.cmd == "prompt-hook":
        return run_prompt_hook(a)
    if a.cmd == "audit-env":
        from . import audit as audit_mod, recipe as recipe_mod
        rec = None
        if a.recipe:
            try:
                rec = recipe_mod.load(a.recipe)
            except (recipe_mod.RecipeError, OSError) as e:
                print(f"agentvow: recipe not used ({e})", file=sys.stderr)
        cmds, trunc = audit_mod.session_commands(Path(a.session))
        res = audit_mod.audit(cmds, Path(a.repo).resolve(), rec, trunc)
        print(json.dumps({"commands": res.commands_seen, "truncated": res.truncated, "findings": [vars(f) for f in res.findings], "undeclared": len(res.undeclared)}) if a.json else audit_mod.render(res))
        return 1 if res.undeclared else 0
    if a.cmd == "post-test-hook":
        return run_post_test_hook(a)
    if a.cmd == "capture":
        rec, msg = capsule_mod.capture(Path(a.repo), a.python)
        print(("capsule written: " if rec else "no capsule: ") + msg)
        if rec and a.export:
            from . import bundle as bundle_mod
            tgt = Path(a.export)
            if tgt.is_symlink():
                print(f"refusing to write through a symlink: {tgt}", file=sys.stderr)
                return 3
            tgt.write_text(json.dumps(bundle_mod.export(rec), indent=2) + "\n", encoding="utf-8")
            print(f"capture bundle written: {tgt} (unsigned; bound to content hash {rec['git_tree'][:12]})")
        return 0 if rec else 2
    if a.cmd == "finish-turn":
        return run_finish_turn(a)
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
    if getattr(a, "evidence_pack", False):
        a.run_tests = True
        a.changed_coverage = True
        if not a.recipe and capsule_mod.load(repo):
            a.from_capsule = True
        elif not a.recipe and a.setup == "none":
            a.setup = "auto"
    if getattr(a, "from_capture", None) and not a.recipe:
        from . import bundle as bundle_mod
        b, why = bundle_mod.load(a.from_capture)
        cap, why2 = bundle_mod.bind(repo, b) if b else (None, why)
        if cap is None:   # fail closed: a missing, malformed or mismatched bundle never falls back to another environment
            a.run_tests = False
            a._capture_refused = why2
            return _run(a, repo, base, base_how, text)
        spec = (a.test_cmd[0].split() if a.test_cmd else [])
        targv = spec[1:] if spec and spec[0] == "{py}" and len(spec) > 2 and spec[1] == "-m" and spec[2] in ("pytest", "unittest") else ["-m", "pytest", "-q"]
        rec, files = capsule_mod.to_recipe(cap, targv)
        a._capsule = cap
        a.run_tests = True
        return _run_recipe(a, repo, base, base_how, text, rec, files)
    if getattr(a, "from_capsule", False) and not a.recipe:
        cap = capsule_mod.load(repo)
        if cap is None:   # fail closed: no capsule for THIS exact state means no capture-based replay (never fall back to another environment silently)
            a.run_tests = False
            a._capsule_missing = True
            return _run(a, repo, base, base_how, text)
        spec = (a.test_cmd[0].split() if a.test_cmd else [])
        targv = spec[1:] if spec and spec[0] == "{py}" and len(spec) > 2 and spec[1] == "-m" and spec[2] in ("pytest", "unittest") else ["-m", "pytest", "-q"]
        rec, files = capsule_mod.to_recipe(cap, targv)
        a._capsule = cap
        a.run_tests = True
        return _run_recipe(a, repo, base, base_how, text, rec, files)
    if a.recipe:
        from . import recipe as recipe_mod
        try:
            rec = recipe_mod.load(a.recipe)
        except (recipe_mod.RecipeError, OSError) as e:
            print(f"agentvow: recipe not used ({e}); no test run was made", file=sys.stderr)
            a.run_tests = False
            a._recipe_rejected = str(e)[:80]
            return _run(a, repo, base, base_how, text)
        a.run_tests = True
        return _run_recipe(a, repo, base, base_how, text, rec, None)
    if a.run_tests and a.setup == "auto":
        return _run_auto(a, repo, base, base_how, text)
    return _run(a, repo, base, base_how, text)


def _run_recipe(a, repo, base, base_how, text, rec, extra_files):
    """Replay from a recipe (the agent's declaration) or from a capsule (the agent's captured packages): clean environment, then the tests."""
    from . import recipe as recipe_mod
    if True:
        venv_root = Path(tempfile.mkdtemp(prefix="agentvow_env_"))
        try:
            py, notes, aborted = recipe_mod.build_env(repo, rec, venv_root / "venv", venv_root / "home", extra_files=extra_files)
            a.python, a._recipe, a._recipe_notes = py, rec, notes
            if py and not aborted and getattr(a, "changed_coverage", False):
                _ensure_coverage(py, venv_root)
            if aborted or not py:
                print(f"agentvow: recipe environment incomplete ({'; '.join(notes)[:300]})", file=sys.stderr)
            if aborted and py:   # a resource guard stopped the install: the environment is PARTIAL, so tests run in it would report misleading "missing dependency" results
                a.run_tests = False
                a._recipe = None
                a._env_aborted = str(aborted)
            elif not py:   # no environment at all: fail closed (never fall back to the host interpreter)
                a.run_tests = False
                a._recipe = None
                a._recipe_rejected = ("; ".join(notes) or "environment could not be built")[:80]
            d = _run(a, repo, base, base_how, text)
        finally:
            shutil.rmtree(venv_root, ignore_errors=True)
        return d


def _run_auto(a, repo, base, base_how, text):
    if True:
        venv_root = Path(tempfile.mkdtemp(prefix="agentvow_env_"))
        try:
            if getattr(a, "evidence_pack", False):   # the pack's project-native context is built from the repository's own files (baseline.py), here as in the hook path
                from . import baseline
                try:
                    py, rec, notes, aborted = baseline.prepare(repo, venv_root / "venv", venv_root / "home")
                except (OSError, subprocess.SubprocessError, ValueError, recipe_mod_error()) as e:   # an unbuildable environment is a result ("could not be built"), not a tool error
                    py, rec, notes, aborted = None, None, [f"environment setup raised {type(e).__name__}"], None
                a._native = rec
                a._native_info = {"steps": [" ".join(x)[:100] for x in (rec.setup if rec else [])], "env_names": sorted(f"{k}={str(v)[:40]}" for k, v in rec.env.items())[:12] if rec else [],
                                  "setup_notes": [n[:200] for n in notes if "failed" in n or "left out" in n or "not read" in n][:4], "inputs": baseline.input_files(repo)}
            else:
                py, notes, aborted = envsetup.build_env(repo, venv_root / "venv", venv_root / "home")
                if os.environ.get("AGENTVOW_DISCOVER") == "1":   # the sub-projects' own source must win over any installed copy, as the root's does
                    a._local_roots = envsetup.discover(repo)["local_roots"]
            a.python = py
            if py and not aborted and getattr(a, "changed_coverage", False):
                _ensure_coverage(py, venv_root)
            if aborted or not py:
                print(f"agentvow: automatic environment setup incomplete ({'; '.join(notes)[:300]})", file=sys.stderr)
            if aborted and py:   # partial environment (a resource guard stopped the install): do not run tests in it
                a.run_tests = False
                a._env_aborted = str(aborted)
            elif not py and getattr(a, "evidence_pack", False):   # no environment at all: fail closed, never test in the host interpreter
                a.run_tests = False
                a._env_aborted = ("; ".join(notes) or "no environment")[:80]
            d = _run(a, repo, base, base_how, text)
        finally:
            shutil.rmtree(venv_root, ignore_errors=True)
        return d


def _run(a, repo, base, base_how, text):
    if a.python is None:
        a.python = envsetup.default_python(repo)
    a.python = os.path.abspath(os.path.expanduser(a.python))  # relative paths would break once we run inside a worktree
    if a.run_tests and getattr(a, "_recipe", None):
        rec = a._recipe
        targv = list(rec.test)   # make the executed test ids visible (the declared command is otherwise untouched)
        if targv[1] == "pytest":
            targv += [x for x in ("-rA", "-p", "no:cacheprovider") if x not in targv] if "-rA" not in targv else []
        elif targv[1] == "unittest" and "-v" not in targv:
            targv.append("-v")
        collect_test_evidence(repo, base, [("tests", [a.python, *targv], "", {"env_extra": rec.env, "pythonpath_rel": rec.local_roots, "prepare": [[a.python, *p] for p in rec.prepare], "coverage": getattr(a, "changed_coverage", False), "meta": {"recipe_sha256": rec.sha256, "declared_by": "captured environment" if getattr(a, "_capsule", None) else "agent recipe", "runner_supplied": rec.runner_supplied, **({"capsule_python": a._capsule["python_version"], "replay_python": ".".join(map(str, sys.version_info[:3])), "dropped_pins": list(rec.dropped_pins), "capture_source": a._capsule.get("capture_source", "local")} if getattr(a, "_capsule", None) else {})}})], a.test_timeout)
    elif a.run_tests:
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
            nat = getattr(a, "_native", None)
            suites.append((name, cmd.format(py=a.python).split(), sub, {"coverage": getattr(a, "changed_coverage", False),
                                                                       **({"env_extra": nat.env, "pythonpath_rel": [*nat.local_roots, *getattr(a, "_local_roots", [])]} if nat else
                                                                          {"pythonpath_rel": list(a._local_roots)} if getattr(a, "_local_roots", None) else {})}))
        collect_test_evidence(repo, base, suites, a.test_timeout)
    extra = ci.ci_evidence(repo, reality.snapshot(repo), sha=a.ci_sha, wait=a.ci_wait) if a.ci else []
    d = check(repo, base, text, extra, a.new_test_failures)
    if getattr(a, "evidence_pack", False) and a.run_tests:
        from . import pack as pack_mod
        try:
            d.pack = pack_mod.build(a, repo, base, d, collect_test_evidence)
        except Exception as e:   # the pack is additional information; a failure here must never change or hide the verdict
            d.scope += f"; the evidence pack could not be built ({type(e).__name__})"
    d.scope += f"; base: {base_how}"
    if getattr(a, "_capsule", None):
        cap = a._capsule
        d.scope += (f"; tests were replayed in a clean environment built from the {len(cap['packages'])} Python package(s) captured when the agent ran its tests (Python {cap['python_version']} then, "
                    f"{'.'.join(map(str, sys.version_info[:2]))} now; not captured: system packages, services, generated files, secrets)")
    elif getattr(a, "_recipe", None):
        d.scope += f"; tests were replayed from the agent's own declared recipe (sha {a._recipe.sha256})" + (f"; setup problems: {'; '.join(a._recipe_notes)[:160]}" if a._recipe_notes else "")
    if getattr(a, "_capture_refused", None):
        d.scope += f"; the capture bundle was not used and no capture-based replay was made: {a._capture_refused}"
    if getattr(a, "_capsule_missing", False):
        d.scope += "; no environment capsule exists for this exact state (run `agentvow capture` right after the agent's tests, before changing anything), so no capture-based replay was made"
    if getattr(a, "_recipe_rejected", None):
        d.scope += f"; the agent's recipe was rejected ({a._recipe_rejected}), so nothing was replayed"
    if getattr(a, "_env_aborted", None):
        d.scope += (f"; the replay environment could not be built ({a._env_aborted}), so no tests were run; this says nothing about the claim. "
                    "If the environment is simply large, raise the limit with AGENTVOW_MAX_ENV_MB (default 700)")
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
        print(f"agentvow: tool error: {type(e).__name__}: {e}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(run())
