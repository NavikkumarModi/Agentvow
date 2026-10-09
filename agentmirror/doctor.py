"""`agentmirror doctor`: check the installation and run the whole hook path end to end, so a live agent test starts from a known-good state."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import reality

OK, WARN, FAIL = "✓", "!", "✗"


def self_test(py: str = sys.executable, camel: bool = False):
    """Run `agentmirror check --hook` on a throwaway repo with a Copilot-style payload (snake_case, or camelCase as Copilot CLI sends). -> (ok, detail)."""
    with tempfile.TemporaryDirectory(prefix="am_doctor_") as t:
        repo = Path(t) / "repo"
        repo.mkdir()
        run = lambda *a: subprocess.run(["git", *reality.GIT_SAFE, "-C", str(repo), *a], capture_output=True, text=True, check=True)
        run("init", "-q")
        run("config", "user.email", "d@example.com")
        run("config", "user.name", "doctor")
        (repo / "a.py").write_text("X = 1\n")
        (repo / "b.py").write_text("import a\n")
        run("add", "-A")
        run("commit", "-qm", "one")
        (repo / "a.py").write_text("X = 2\n")
        run("add", "-A")
        run("commit", "-qm", "two")
        tr = Path(t) / "transcript.jsonl"
        tr.write_text(json.dumps({"role": "assistant", "content": "Changed X. There is no downstream impact."}) + "\n")
        payload = ({"cwd": str(repo), "transcriptPath": str(tr), "sessionId": "doctor", "stopReason": "end_turn"} if camel else
                   {"cwd": str(repo), "transcript_path": str(tr), "session_id": "doctor", "hook_event_name": "Stop"})
        p = subprocess.run([py, "-m", "agentmirror", "check", "--hook"], input=json.dumps(payload), capture_output=True, text=True, timeout=120)
        if p.returncode != 0:
            return False, f"hook exited {p.returncode}: {p.stderr[-200:]}"
        try:
            out = json.loads(p.stdout)
            msg = out["systemMessage"]
        except (ValueError, KeyError):
            return False, f"hook output was not the expected JSON: {p.stdout[:150]!r}"
        if "decision" in out:
            return False, "hook output contains a 'decision' field; it must never block"
        last = repo / ".agentmirror" / "last"
        if not all((last / f).is_file() for f in ("report.html", "decision.json", "decision.sig")):
            return False, "the hook did not write its result files"
        if "REVIEW REQUIRED" not in msg:
            return False, "expected REVIEW REQUIRED for the planted 'no downstream impact' claim; got: " + msg[:120]
        return True, "parsed the payload and transcript, found the planted contradiction, never blocked, wrote sealed result files"


def copilot_agentstop_runs(repo: Path, home: Path | None = None, sessions: int = 12) -> dict | None:
    """Did GitHub Copilot (CLI engine, which VS Code hosts) run an agentStop hook for this repo? Evidence is in the session files
    (~/.copilot/session-state/<id>/events.jsonl: hook.start / hook.end records); VS Code's own logs do not record it. Structure only, no message text."""
    base = Path(os.environ.get("COPILOT_HOME", home or Path.home() / ".copilot")) / "session-state"
    if not base.is_dir():
        return None
    repo = os.path.realpath(repo)
    runs = []
    for d in sorted((x for x in base.iterdir() if x.is_dir()), key=lambda x: x.stat().st_mtime, reverse=True)[:sessions]:
        f = d / "events.jsonl"
        if not f.is_file():
            continue
        starts = {}
        try:
            with f.open(encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if "hook.start" not in line[:60] and "hook.end" not in line[:60]:   # cheap pre-filter, independent of JSON spacing
                        continue
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    data = r.get("data", {})
                    if data.get("hookType") != "agentStop":
                        continue
                    if r["type"] == "hook.start":
                        starts[data.get("hookInvocationId")] = (data.get("input") or {}).get("cwd")
                    elif r["type"] == "hook.end" and os.path.realpath(starts.get(data.get("hookInvocationId")) or "") == repo:
                        out = data.get("output")
                        runs.append({"time": r.get("timestamp"), "success": bool(data.get("success")), "output_keys": sorted(out) if isinstance(out, dict) else []})
        except OSError:
            continue
    return {"count": len(runs), "last": max(runs, key=lambda x: x["time"] or "") if runs else None}


def absolute_command() -> str | None:
    """Full path of the agentmirror executable as a login shell sees it (hooks run with the agent's PATH, which often lacks conda/pyenv/venv dirs)."""
    return shutil.which("agentmirror")


def run_doctor(repo: Path) -> int:
    res = []
    add = lambda status, name, detail="", fix="": res.append((status, name, detail, fix))
    v = sys.version_info
    add(OK if v >= (3, 10) else FAIL, "Python 3.10+", f"{v.major}.{v.minor}.{v.micro}", "install Python 3.10 or newer")
    exe = absolute_command()
    add(OK if exe else WARN, "`agentmirror` on PATH", exe or "not found",
        "run `pip install .` from the AgentMirror folder in an environment that is on PATH")
    if exe and not exe.startswith(("/usr/bin", "/bin", "/usr/local/bin", "/opt/homebrew/bin")):
        add(WARN, "hooks may not find it", f"{exe} is outside the default GUI PATH",
            f"apps launched from the Dock (VS Code) often do not have this directory on PATH: use the full path in hook commands: {exe} check --hook")
    from . import runner
    why = runner.sandbox_problem()
    add(OK if not why else WARN, "test sandbox (macOS sandbox-exec / Linux bubblewrap)", "working" if not why else why,
        "without it AgentMirror refuses to run tests (static checks and CI reading still work)")
    add(OK if shutil.which("git") else FAIL, "git", shutil.which("git") or "not found", "install git")
    gh = shutil.which("gh")
    if gh:
        authed = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True).returncode == 0
        add(OK if authed else WARN, "GitHub CLI (for --ci)", "authenticated" if authed else "installed, not logged in", "run `gh auth login`")
    else:
        add(WARN, "GitHub CLI (for --ci)", "not installed", "optional: needed only for --ci")
    try:
        key = reality._key()
        kp = Path(os.environ.get("AGENTMIRROR_HOME", Path.home() / ".agentmirror")) / "key"
        mode = oct(os.stat(kp).st_mode & 0o777)
        add(OK if mode == "0o600" else WARN, "signing key outside repositories", f"{len(key)} bytes, mode {mode}", "chmod 600 ~/.agentmirror/key")
    except OSError as e:
        add(FAIL, "signing key outside repositories", str(e), "make ~/.agentmirror writable (or set AGENTMIRROR_HOME)")
    repo = repo.resolve()
    if (repo / ".git").exists():
        hooks_dir = repo / ".github" / "hooks"
        found = sorted(hooks_dir.glob("*.json")) if hooks_dir.is_dir() else []
        good = False
        for f in found:
            try:
                data = json.loads(f.read_text())["hooks"]
                entries = [e for ev in ("Stop", "agentStop") for e in data.get(ev, [])]
                if any("agentmirror" in (e.get("command") or e.get("bash") or "") and "--hook" in (e.get("command") or e.get("bash") or "") for e in entries):
                    good = True
                    cmd = next((e.get("command") or e.get("bash")) for e in entries)
                    add(OK, f".github/hooks/{f.name}", f"Stop hook: {cmd}")
                    if not cmd.split()[0].startswith("/"):
                        add(WARN, "hook uses a bare command name", cmd.split()[0],
                            f"if the agent cannot find it, use the full path ({exe or '/path/to/agentmirror'})")
            except Exception as e:
                add(FAIL, f".github/hooks/{f.name}", f"invalid: {e}", "fix the JSON")
        def _has_prompt_hook(f):
            try:
                return "prompt-hook" in json.dumps(json.loads(f.read_text()).get("hooks", {}))
            except Exception:
                return False   # an unreadable file is reported above; never crash the doctor
        has_prompt = any(_has_prompt_hook(f) for f in found)
        if good:
            add(WARN if has_prompt else OK, "experimental chat hook (UserPromptSubmit: tells the agent the last verdict)",
                "ENABLED: one live Copilot session stalled right after its first delivery (cause unproven)" if has_prompt else "not enabled (recommended)",
                "if a chat stalls, remove the UserPromptSubmit entry from the hook file" if has_prompt else "")
        if not good:
            add(WARN, "AgentMirror Stop hook in .github/hooks/", "not present",
                "VS Code command: 'AgentMirror: Add the agent hook to this workspace' (then start a NEW chat session)")
        gi = repo / ".gitignore"
        ignored = gi.exists() and ".agentmirror" in gi.read_text()
        add(OK if ignored else WARN, ".agentmirror/ is git-ignored", "yes" if ignored else "no", "add `.agentmirror/` to .gitignore so results and evidence are not committed")
        last = repo / ".agentmirror" / "last"
        add(OK if (last / "decision.json").exists() else WARN, "a hook has produced a result here before",
            "yes" if (last / "decision.json").exists() else "no result yet",
            "if you ran an agent after adding the hook, the hook did not fire: see docs/LIVE_TESTING.md (probe test)")
        cop = copilot_agentstop_runs(repo)
        if cop is None:
            add(WARN, "Copilot CLI sessions", "no ~/.copilot/session-state found", "only relevant if you use Copilot (VS Code agent chat or the CLI)")
        elif cop["count"]:
            last = cop["last"]
            add(OK if last["success"] else WARN, "Copilot ran the agentStop hook in this repo",
                f"{cop['count']} time(s); last {last['time']}, success={last['success']}",
                "" if last["success"] else "the hook command failed inside Copilot: check the command path (use the full path)")
            add(OK, "Copilot discards extra hook output fields", "only decision/reason are honoured, so the verdict shows in the VS Code extension (status bar/panel), not in Copilot's chat",
                "use --feedback-to-agent if you want Copilot to be asked to revise a contradicted summary")
        else:
            add(WARN, "Copilot ran the agentStop hook in this repo", "no run found in recent sessions",
                "start a NEW chat after adding the hook file (hooks load when a session starts), then re-run doctor")
    else:
        add(WARN, "repository", f"{repo} is not a git repository", "run doctor inside the project you want to check")
    for camel in (False, True):
        try:
            ok, detail = self_test(camel=camel)
            add(OK if ok else FAIL, f"end-to-end hook self-test ({'camelCase: Copilot CLI' if camel else 'snake_case: VS Code/Claude'} payload)", detail,
                "re-run the agent with AGENTMIRROR_DEBUG=1 and share .agentmirror/last/payload_shape.json (structure only)")
        except Exception as e:
            add(FAIL, "end-to-end hook self-test", f"{type(e).__name__}: {e}", "")
    for st, name, detail, fix in res:
        print(f"{st} {name}" + (f": {detail}" if detail else ""))
        if st != OK and fix:
            print(f"    -> {fix}")
    failed = sum(1 for r in res if r[0] == FAIL)
    print("\n" + (f"{failed} problem(s) need fixing before a live test." if failed else "Setup looks right. Live-test steps: docs/LIVE_TESTING.md"))
    return 1 if failed else 0
