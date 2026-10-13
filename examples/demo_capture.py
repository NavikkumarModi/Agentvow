"""Recording script for the README demo (assets/demo.cast -> assets/demo.gif).

Everything shown is a real run of the installed `agentvow` command on a small throwaway project: a real virtualenv with pytest, a real commit the "agent" made,
a real `agentvow capture`, a real sandboxed replay and a real changed-line coverage measurement. Staged for the recording, not faked: the pacing and simulated typing
of the two commands, the one-line "agent" scene (a pre-made commit stands in for a live agent), and the line wrapping of the report text so it fits the terminal.

Usage: python3 examples/demo_capture.py prepare DIR   # build the project once (network, not recorded)
       python3 examples/demo_capture.py show DIR      # what gets recorded
"""
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

AGENTVOW = os.environ.get("AGENTVOW_BIN", "agentvow")
BOLD, DIM, GREEN, YELLOW, RESET = "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[0m"


def prepare(d: Path) -> None:
    d.mkdir(parents=True, exist_ok=True)
    g = lambda *a: subprocess.run(["git", "-C", str(d), *a], check=True, capture_output=True)
    g("init", "-q", "-b", "main"); g("config", "user.email", "demo@example.com"); g("config", "user.name", "demo")
    (d / ".gitignore").write_text(".venv/\n.agentvow/\n__pycache__/\n")
    (d / "tests").mkdir(exist_ok=True)
    (d / "fetch.py").write_text("def fetch(url):\n    return {'url': url, 'ok': True}\n")
    (d / "tests" / "test_fetch.py").write_text("from fetch import fetch\n\n\ndef test_fetch():\n    assert fetch('x')['ok']\n")
    g("add", "."); g("commit", "-qm", "base")
    subprocess.run([sys.executable, "-m", "venv", str(d / ".venv")], check=True, capture_output=True)
    subprocess.run([str(d / ".venv" / "bin" / "pip"), "install", "-q", "pytest"], check=True, capture_output=True)
    (d / "fetch.py").write_text(
        "import time\n\n\ndef fetch(url, retries=3, jitter=False):\n    for attempt in range(retries):\n        result = {'url': url, 'ok': True}\n"
        "        if result['ok']:\n            return result\n        delay = 2 ** attempt\n        if jitter:\n            delay += 0.5\n        time.sleep(delay)\n    return {'url': url, 'ok': False}\n")
    g("commit", "-qam", "add retry to fetch")


def type_out(cmd: str) -> None:
    sys.stdout.write(f"{GREEN}${RESET} ")
    for ch in cmd:
        sys.stdout.write(ch); sys.stdout.flush(); time.sleep(0.018)
    sys.stdout.write("\n"); sys.stdout.flush(); time.sleep(0.4)


def show(d: Path) -> None:
    os.chdir(d)
    env = {**os.environ, "NO_COLOR": "1"}
    print(f"{BOLD}An agent just added a retry to fetch() and said:{RESET}\n  {DIM}\"I added retries to fetch(). All tests pass.\"{RESET}\n")
    time.sleep(1.2)
    print(f"{DIM}# right after the agent ran its tests, record the environment it used{RESET}")
    type_out(f"{AGENTVOW} capture --repo .")
    sys.stdout.write(subprocess.run([AGENTVOW, "capture", "--repo", "."], capture_output=True, text=True, env=env).stdout); sys.stdout.flush(); time.sleep(1.0)
    print(f"\n{DIM}# check the claim: replay the tests in a clean sandbox built from those packages{RESET}")
    type_out(f"echo \"I added retries to fetch(). All tests pass.\" | {AGENTVOW} check --transcript - --base HEAD~1 --run-tests --from-capsule --changed-coverage")
    p = subprocess.run([AGENTVOW, "check", "--repo", ".", "--transcript", "-", "--base", "HEAD~1", "--run-tests", "--from-capsule", "--changed-coverage"],
                       input="I added retries to fetch(). All tests pass.", capture_output=True, text=True, env=env)
    for line in p.stdout.splitlines():
        if line.startswith(("AGENTVOW", "Scope of this check", "This tool informs")) or not line.strip():
            continue
        if line.startswith("   evidence:"):
            continue
        color = YELLOW if line.strip().startswith("unknown:") else (BOLD if line.startswith(("STATUS", "✓")) else "")
        for w in textwrap.wrap(line, 98, subsequent_indent="   ") or [""]:
            print(f"{color}{w}{RESET}"); sys.stdout.flush(); time.sleep(0.12)
    time.sleep(2.5)


if __name__ == "__main__":
    {"prepare": prepare, "show": show}[sys.argv[1]](Path(sys.argv[2]))
