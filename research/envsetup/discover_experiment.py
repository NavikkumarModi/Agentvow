"""Does discovering dependencies beyond the repository root (envsetup.discover: sub-projects, requirements files in sub-folders, test-like extras and groups, the sub-projects on the import path) lower
the inconclusive rate? For the repositories the classification found to declare their dependencies where the ladder does not read (docs/research/INCONCLUSIVE_CLASSIFICATION.md), take one pull request whose
replay was inconclusive in the detection study and run the product (`agentvow check --setup auto --run-tests`) twice on the same machine: AGENTVOW_DISCOVER unset (the old ladder) and =1. Resumable.
Clones third-party repositories and runs their installs and tests inside Agentvow's sandbox (network allowed for installs only); needs several GB of disk.
Usage: python3 research/envsetup/discover_experiment.py [max_repos=17]   -> data/checker_eval/discover_experiment.jsonl"""
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
OUT = DATA / "discover_experiment.jsonl"
CAUSES = ("no root project to install: dependencies live elsewhere or nowhere declared", "declared in a place the ladder does not read")
REPOS = [r for r, v in json.loads((DATA / "classify_inconclusive.json").read_text()).items() if v["cause"] in CAUSES]


def run(d, t, discover):
    home = tempfile.mkdtemp(prefix="pyvexp_home_")
    env = {**os.environ, "AGENTVOW_HOME": home, "PYTHONPATH": str(ROOT)}
    env.pop("AGENTVOW_LOCK", None); env.pop("AGENTVOW_PYVERSION", None); env.pop("AGENTVOW_DISCOVER", None)
    if discover:
        env["AGENTVOW_DISCOVER"] = "1"
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
    done = {(json.loads(l)["repo"], json.loads(l)["discover"]) for l in OUT.read_text().splitlines()} if OUT.exists() else set()
    for t in list(sel.values())[: int(sys.argv[1]) if len(sys.argv) > 1 else 99]:
        d = None
        for dv in (False, True):
            if (t["repo"], dv) in done:
                continue
            if d is None:
                d, why = L.prepare(t)
                if d is None:
                    with OUT.open("a") as f:
                        f.write(json.dumps({**t, "discover": dv, "verdict": "PREPARE_FAILED", "why": why}) + "\n")
                    break
            rec = {**t, "discover": dv, **run(d, t, dv)}
            with OUT.open("a") as f:
                f.write(json.dumps(rec) + "\n")
            print(t["repo"], t["pr"], "new" if dv else "old", rec["verdict"], rec.get("seconds"), flush=True)
            if shutil.disk_usage(ROOT).free < 3 * 1024**3:
                print("disk low; stopping")
                return
        if d is not None:
            shutil.rmtree(d, ignore_errors=True)   # keep the disk free: one clone at a time


if __name__ == "__main__":
    main()
