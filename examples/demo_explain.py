"""Recording script for the README plain-language demo (assets/demo_explain.cast -> assets/demo_explain.gif and .mp4).

The same throwaway project and the same two kinds of pull request as examples/demo_gate.py (a claim the replay contradicts, and a claim it cannot confirm), but the last step is `agentvow policy explain`: what a
reviewer reads in the check run or the job summary. Real commands of the package named by AGENTVOW_BIN (the 0.4.4 release candidate built from this repository); the decisions are not scripted. Staged for the
recording, not faked: the pacing and simulated typing, the pre-made branches that stand in for agents, working files kept outside the repository, a policy that lists one acknowledger (alice), commands shortened on screen (the real ones also pass
`--python .venv/bin/python` and longer paths), and the lines of the explanation cut to the screen width; only blank lines and the closing "what this does not show" paragraph are left out of the picture.

Usage: python3 examples/demo_explain.py prepare DIR   (the same preparation as demo_gate.py)
       python3 examples/demo_explain.py show DIR
"""
import json
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import demo_gate as G  # noqa: E402

AGENTVOW, BOLD, DIM, GREEN, YELLOW, RED, RESET = G.AGENTVOW, G.BOLD, G.DIM, G.GREEN, G.YELLOW, G.RED, G.RESET
SCENES = [("agent/refactor-f", "block"), ("agent/add-h", "needs_acknowledgement")]


def show(d: Path) -> None:
    out = d.parent / (d.name + "_out")
    os.chdir(d)
    pol = json.loads((out / "policy.json").read_text()); pol["acknowledgers"] = ["alice"]; (out / "policy.json").write_text(json.dumps(pol))   # one listed acknowledger, as a team would have
    for n, (br, _) in enumerate(SCENES, 1):
        claim = next(c for b, c, _ in G.BRANCHES if b == br); short = br.split("/")[1]
        sys.stdout.write("\033[2J\033[H")
        print(f"{BOLD}What a reviewer reads ({n} of {len(SCENES)}){RESET} {DIM}(the check run and the job summary say this){RESET}\n"); time.sleep(0.8 if n > 1 else 1.0)
        print(f"{BOLD}{br}{RESET}  {DIM}\"{claim}\"{RESET}")
        G.type_out(f"git checkout -q {br}"); G.run(["git", "checkout", "-q", br])
        G.type_out("agentvow check --base main --transcript pr.txt --run-tests --json > check.json")
        G.run([AGENTVOW, "check", "--repo", ".", "--base", "main", "--transcript", str(out / f"{short}.txt"), "--run-tests", "--python", ".venv/bin/python", "--json"], stdout=open(out / "check.json", "w"))
        G.type_out("agentvow receipt --decision check.json --repo-slug you/project --repo . -o receipt.json")
        G.run([AGENTVOW, "receipt", "--decision", str(out / "check.json"), "--repo-slug", "you/project", "--repo", ".", "-o", str(out / "receipt.json")])
        G.type_out("agentvow policy evaluate --policy policy.json --receipt receipt.json > result.json")
        r = G.run([AGENTVOW, "policy", "evaluate", "--policy", str(out / "policy.json"), "--receipt", str(out / "receipt.json")]); (out / "result.json").write_text(r.stdout)
        G.type_out("agentvow policy explain --result result.json")
        text = G.run([AGENTVOW, "policy", "explain", "--result", str(out / "result.json")]).stdout
        shown = 0
        for line in text.splitlines():
            if not line.strip() or line.startswith("What this does not show"):
                continue
            color = {"block": RED, "needs_acknowledgement": YELLOW}.get(json.loads(r.stdout)["decision"], "") if shown == 0 else (BOLD if line.startswith("**") else "")
            for w in textwrap.wrap(line.replace("**", ""), 98, subsequent_indent="  ") or [""]:
                print(f"{color}{w}{RESET}"); sys.stdout.flush(); time.sleep(0.07)
            shown += 1
        time.sleep(3.5)
        G.run(["git", "checkout", "-q", "main"])
    time.sleep(1.0)


if __name__ == "__main__":
    {"prepare": G.prepare, "show": show}[sys.argv[1]](Path(sys.argv[2]))
