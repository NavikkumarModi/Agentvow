"""Does building the environment with the Python version the repository supports (agentvow/pyversion.py) lower the inconclusive rate? For the repositories where it would pick a different
interpreter than the running one, take one pull request whose replay was inconclusive in the detection study and run the product (`agentvow check --setup auto --run-tests`) twice on the same
machine: AGENTVOW_PYVERSION=0 (running interpreter) and =1 (chosen interpreter). Resumable. Clones third-party repositories and runs their installs and tests inside Agentvow's sandbox.
Usage: python3 research/envsetup/pyversion_experiment.py   -> data/checker_eval/pyversion_experiment.jsonl"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lock_experiment as L  # noqa: E402

ROOT, DATA = L.ROOT, L.DATA
OUT = DATA / "pyversion_experiment.jsonl"
REPOS = ["google/clusterfuzz", "PrefectHQ/marvin", "hud-evals/hud-python", "llama-farm/llamafarm", "ml-struct-bio/cryodrgn"]   # the swaps that are plainly 3.13 -> 3.11 on the machine used


def run(d, t, pyversion):
    home = tempfile.mkdtemp(prefix="pyvexp_home_")
    env = {**os.environ, "AGENTVOW_PYVERSION": "1" if pyversion else "0", "AGENTVOW_HOME": home, "PYTHONPATH": str(ROOT)}
    env.pop("AGENTVOW_LOCK", None)
    start = time.time()
    try:
        p = subprocess.run([sys.executable, "-m", "agentvow", "check", "--repo", str(d), "--base", t["base"], "--run-tests", "--setup", "auto", "--json"], input="All tests pass.\n",
                           capture_output=True, text=True, timeout=L.TIMEOUT, env=env)
        try:
            o = json.loads(p.stdout)
            f = next((x for x in o["findings"] if x["kind"] == "tests_pass"), o["findings"][0])
            return {"verdict": f["verdict"], "why": f["why"][:400], "scope": o.get("scope", "")[:300], "seconds": round(time.time() - start), "stderr": p.stderr[-600:]}
        except (ValueError, KeyError, IndexError):
            return {"verdict": "ERROR", "why": (p.stdout + p.stderr)[-400:], "seconds": round(time.time() - start)}
    except subprocess.TimeoutExpired:
        return {"verdict": "TIMEOUT", "why": "", "seconds": L.TIMEOUT}
    finally:
        shutil.rmtree(home, ignore_errors=True)
        L.sh("git", "clean", "-fdxq", cwd=d)


def main():
    rows = [json.loads(l) for l in (ROOT / "data" / "detection_v2_results_plus.jsonl").read_text().splitlines()]
    sel = {}
    for r in rows:
        if r["repo"] in REPOS and r["repo"] not in sel and (r["head_result"] == "inconclusive" or r["base_result"] == "inconclusive"):
            sel[r["repo"]] = {k: r[k] for k in ("repo", "pr", "head", "base", "agent")}
    done = {(json.loads(l)["repo"], json.loads(l)["pyversion"]) for l in OUT.read_text().splitlines()} if OUT.exists() else set()
    for t in sel.values():
        d = None
        for pv in (False, True):
            if (t["repo"], pv) in done:
                continue
            if d is None:
                d, why = L.prepare(t)
                if d is None:
                    with OUT.open("a") as f:
                        f.write(json.dumps({**t, "pyversion": pv, "verdict": "PREPARE_FAILED", "why": why}) + "\n")
                    break
            rec = {**t, "pyversion": pv, **run(d, t, pv)}
            with OUT.open("a") as f:
                f.write(json.dumps(rec) + "\n")
            print(t["repo"], t["pr"], "new" if pv else "old", rec["verdict"], rec.get("seconds"), flush=True)
            if shutil.disk_usage(ROOT).free < 3 * 1024**3:
                print("disk low; stopping")
                return
        if d is not None:
            shutil.rmtree(d, ignore_errors=True)   # keep the disk free: one clone at a time


if __name__ == "__main__":
    main()
