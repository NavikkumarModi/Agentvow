"""Recording script for the README gate demo (assets/demo_gate.cast -> assets/demo_gate.gif).

What the gate workflow does on a pull request (`.github/workflows/gate.yml`: check, receipt, policy from the base branch), run by hand on three pull-request branches of a small throwaway
project, with the real `agentvow` command of the released package. Staged for the recording, not faked: the pacing and simulated typing, the three branches (pre-made commits stand in for
agents; their pull-request descriptions are the claims), the working files kept outside the repository and the project's own virtualenv (the commands shown use short names and omit `--python .venv/bin/python`; the real ones use `../out/`), and the one-line
notes in grey, which say what GitHub then does with the decision (shown for real in docs/LIVE_TESTING.md and the screenshot in the README). Nothing about the decisions is scripted.

Usage: python3 examples/demo_gate.py prepare DIR   # build the project and branches once (not recorded)
       python3 examples/demo_gate.py show DIR      # what gets recorded
"""
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

AGENTVOW = os.environ.get("AGENTVOW_BIN", "agentvow")
BOLD, DIM, GREEN, YELLOW, RED, RESET = "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[0m"
TEST = ""   # the real command also passes --python .venv/bin/python (shortened on screen)
BRANCHES = [  # (branch, what the pull request says, new lib.py)
    ("agent/add-g", "I added g(). All tests pass.", "def f():\n    return 1\n\n\ndef g():\n    return 2\n"),
    ("agent/refactor-f", "I simplified f(). All tests pass.", "def f():\n    return 2\n"),
    ("agent/add-h", "I added h(). All 9 tests pass.", "def f():\n    return 1\n\n\ndef h():\n    return 3\n"),
]


def prepare(d: Path) -> None:
    d.mkdir(parents=True, exist_ok=True)
    g = lambda *a: subprocess.run(["git", "-C", str(d), *a], check=True, capture_output=True)
    g("init", "-q", "-b", "main"); g("config", "user.email", "demo@example.com"); g("config", "user.name", "demo")
    (d / ".gitignore").write_text(".venv/\n.agentvow/\n__pycache__/\n.pytest_cache/\n")
    (d / "tests").mkdir(exist_ok=True); (d / "tests" / "__init__.py").write_text("")
    (d / "lib.py").write_text("def f():\n    return 1\n")
    (d / "tests" / "test_lib.py").write_text("from lib import f\n\n\ndef test_f():\n    assert f() == 1\n")
    g("add", "."); g("commit", "-qm", "base")
    subprocess.run([sys.executable, "-m", "venv", str(d / ".venv")], check=True, capture_output=True)
    subprocess.run([str(d / ".venv" / "bin" / "pip"), "install", "-q", "pytest"], check=True, capture_output=True)
    out = d.parent / (d.name + "_out"); out.mkdir(exist_ok=True)
    for br, claim, body in BRANCHES:
        g("checkout", "-q", "-b", br, "main"); (d / "lib.py").write_text(body); g("commit", "-qam", br)
        (out / (br.split("/")[1] + ".txt")).write_text(claim + "\n")
    g("checkout", "-q", "main")
    pol = subprocess.run([AGENTVOW, "policy", "init"], capture_output=True, text=True, check=True).stdout
    (out / "policy.json").write_text(pol)


def type_out(cmd: str) -> None:
    sys.stdout.write(f"{GREEN}${RESET} ")
    for ch in cmd:
        sys.stdout.write(ch); sys.stdout.flush(); time.sleep(0.012)
    sys.stdout.write("\n"); sys.stdout.flush(); time.sleep(0.3)


def run(args, stdout=None):
    env = {**os.environ, "NO_COLOR": "1"}
    if stdout is not None:
        return subprocess.run(args, stdout=stdout, stderr=subprocess.DEVNULL, text=True, env=env)
    return subprocess.run(args, capture_output=True, text=True, env=env)


def show(d: Path) -> None:
    out = d.parent / (d.name + "_out")
    os.chdir(d)
    for n, (br, claim, _) in enumerate(BRANCHES, 1):
        short = br.split("/")[1]
        sys.stdout.write("\033[2J\033[H")   # one screen per pull request
        print(f"{BOLD}The gate on agent pull requests ({n} of {len(BRANCHES)}){RESET} {DIM}(check, receipt, policy: the steps of gate.yml){RESET}\n")
        time.sleep(0.6 if n > 1 else 1.0)
        print(f"{BOLD}{br}{RESET}  {DIM}\"{claim}\"{RESET}")
        type_out(f"git checkout -q {br}")
        run(["git", "checkout", "-q", br])
        type_out("agentvow check --base main --transcript pr.txt --run-tests --json > check.json")
        run([AGENTVOW, "check", "--repo", ".", "--base", "main", "--transcript", str(out / f"{short}.txt"), "--run-tests", "--python", ".venv/bin/python", "--json"], stdout=open(out / "check.json", "w"))
        time.sleep(0.2)
        type_out("agentvow receipt --decision check.json --repo-slug you/project --repo . -o receipt.json")
        run([AGENTVOW, "receipt", "--decision", str(out / "check.json"), "--repo-slug", "you/project", "--repo", ".", "-o", str(out / "receipt.json")])
        type_out("agentvow policy evaluate --policy policy.json --receipt receipt.json")
        r = run([AGENTVOW, "policy", "evaluate", "--policy", str(out / "policy.json"), "--receipt", str(out / "receipt.json")])
        import json
        d_ = json.loads(r.stdout)
        color = {"allow": GREEN, "block": RED}.get(d_["decision"], YELLOW)
        print(f"{color}{BOLD}{d_['decision']}{RESET}"); time.sleep(0.4)
        for x in d_["reasons"]:
            for i, w in enumerate(textwrap.wrap(f"{x['rule']}: {x['text']}", 94)):
                print(f"  {color if i == 0 else DIM}{w}{RESET}"); sys.stdout.flush(); time.sleep(0.12)
        note = {"allow": "required check agentvow/evidence passes; the pull request can merge",
                "block": "required check fails; the merge button is disabled; a contradiction cannot be acknowledged away",
                "needs_acknowledgement": "required check waits; a named person comments /agentvow acknowledge <id>"}[d_["decision"]]
        print(f"{DIM}  -> on GitHub: {note}{RESET}"); sys.stdout.flush(); time.sleep(2.8)
        run(["git", "checkout", "-q", "main"])
    time.sleep(1.5)


if __name__ == "__main__":
    {"prepare": prepare, "show": show}[sys.argv[1]](Path(sys.argv[2]))
