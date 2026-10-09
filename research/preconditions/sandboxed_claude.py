"""S0 (STAGE_B.md section 0.2): run the agent itself under the macOS sandbox. Writes are limited to the task directory, its virtualenv, scratch and
Claude's own state; credential directories are unreadable; network stays allowed (pip and the API need it).
Residual (documented): the agent needs Claude's own credentials, so those stay reachable from the agent's own child processes."""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from agentvow import runner  # noqa: E402


def profile(task_dir: Path, venv_dir: Path, scratch: Path) -> str:
    home = Path.home()
    rw = [task_dir, venv_dir, scratch, home / ".claude", Path("/dev"), Path(tempfile.gettempdir()).resolve(), Path(f"/private/tmp/claude-{os.getuid()}")]   # the last: Claude's own shell-tool working folder
    allowed = "".join(f'(subpath "{os.path.realpath(p)}")' for p in rw)
    lit = f'(regex #"^/private/tmp/claude-[0-9a-f]+-cwd$")(literal "{home}/.claude.json")(literal "{home}/.claude.json.lock")(regex #"^{home}/\\.claude\\.json\\..*")'
    # read-deny credential stores, EXCEPT what Claude itself needs (its own ~/.claude is allowed above)
    deny = runner._deny_reads().replace(f'(deny file-read* (subpath "{os.path.realpath(home / ".claude")}"))', "").replace(f'(deny file-read* (literal "{os.path.realpath(home / ".claude")}"))', "")
    deny = "".join(f'(deny file-read* (subpath "{os.path.realpath(home / d)}"))' for d in (".ssh", ".aws", ".gnupg", ".config/gh", ".config/gcloud", ".docker", ".kube", ".npmrc", ".netrc", ".pypirc", ".git-credentials",
                                                                                               "Documents", "Desktop", "Downloads", "Pictures", "Movies", "Music", "Library/Mail", "Library/Messages",
                                                                                               "Library/Safari", "Library/Cookies", "Library/Application Support/Google", "Library/Application Support/Firefox",
                                                                                               "Library/Application Support/AddressBook", "Library/Calendars"))   # NOT Library/Keychains: Claude's own login lives there (documented residual)
    return f'(version 1)(allow default){deny}(deny file-write*)(allow file-write* {allowed}{lit}(subpath "/private/var/folders"))'


def run_claude(args: list, cwd: Path, venv: Path, scratch: Path, env: dict, timeout: int = 600):
    return subprocess.run(["sandbox-exec", "-p", profile(cwd, venv, scratch), "claude", *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)


if __name__ == "__main__":
    task = Path(tempfile.mkdtemp(prefix="s0task_")); venv = Path(tempfile.mkdtemp(prefix="s0venv_")); scratch = Path(tempfile.mkdtemp(prefix="s0scr_"))
    env = {**os.environ}
    probe = Path.home() / "agentvow_s0_probe.txt"
    probe.unlink(missing_ok=True)
    prompt = sys.argv[1] if len(sys.argv) > 1 else "Reply with exactly: ok"
    p = run_claude(["-p", prompt, "--output-format", "json", "--setting-sources", "project", "--max-budget-usd", "0.5", "--permission-mode", "acceptEdits",
                    "--allowedTools", "Bash", "Read", "Write", "--disallowedTools", "WebFetch", "WebSearch"], task, venv, scratch, env)
    print("exit", p.returncode)
    print((p.stdout or p.stderr)[:600])
    print("home probe exists:", probe.exists())
    for d in (task, venv, scratch):
        shutil.rmtree(d, ignore_errors=True)
