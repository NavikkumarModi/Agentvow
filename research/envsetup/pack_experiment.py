"""How often does the pull-request gate's own environment path end UNKNOWN? The gate and the evidence pack build the environment from the repository's CI workflows, Dockerfiles and setup files
(baseline.prepare), while the zero-config ladder (envsetup.build_env) used in the detection study reads a fixed set of places. For the repositories of the discovery experiment, run the same pull
request through both on the same machine: `agentvow check --run-tests --setup auto` (ladder) and the same with `--evidence-pack` (project-native environment). Resumable.
Clones third-party repositories and runs their installs and tests inside Agentvow's sandbox (network allowed for installs only); needs several GB of disk.
Usage: python3 research/envsetup/pack_experiment.py [max_repos=5]   -> data/checker_eval/pack_experiment.jsonl"""
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
OUT = DATA / "pack_experiment.jsonl"
REPOS = ["ArcadeAI/arcade-mcp", "FalkorDB/QueryWeaver", "crewAIInc/crewAI", "elementary-data/dbt-data-reliability", "google/clusterfuzz"]   # the same five as the discovery experiment


def run(d, t, pack):
    home = tempfile.mkdtemp(prefix="pyvexp_home_")
    env = {**os.environ, "AGENTVOW_HOME": home, "PYTHONPATH": str(ROOT)}
    for k in ("AGENTVOW_LOCK", "AGENTVOW_PYVERSION", "AGENTVOW_DISCOVER"):
        env.pop(k, None)
    start = time.time()
    try:
        p = subprocess.run([sys.executable, "-m", "agentvow", "check", "--repo", str(d), "--base", t["base"], "--run-tests", "--setup", "auto", *(["--evidence-pack"] if pack else []), "--json"], input="All tests pass.\n",
                           capture_output=True, text=True, timeout=L.TIMEOUT, env=env)
        try:
            o = json.loads(p.stdout)
            f = next((x for x in o["findings"] if x["kind"] == "tests_pass"), o["findings"][0])
            return {"verdict": f["verdict"], "why": f["why"][:400], "scope": o.get("scope", "")[:300], "seconds": round(time.time() - start), "stderr": p.stderr[-600:], "pack": json.dumps(o.get("pack"))[:3000] if pack else None}
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
    done = {(json.loads(l)["repo"], json.loads(l)["pack"]) for l in OUT.read_text().splitlines()} if OUT.exists() else set()
    for t in list(sel.values())[: int(sys.argv[1]) if len(sys.argv) > 1 else 99]:
        d = None
        for pk in (False, True):
            if (t["repo"], pk) in done:
                continue
            if d is None:
                d, why = L.prepare(t)
                if d is None:
                    with OUT.open("a") as f:
                        f.write(json.dumps({**t, "pack": pk, "verdict": "PREPARE_FAILED", "why": why}) + "\n")
                    break
            rec = {**t, "pack": pk, **run(d, t, pk)}
            with OUT.open("a") as f:
                f.write(json.dumps(rec) + "\n")
            print(t["repo"], t["pr"], "pack" if pk else "ladder", rec["verdict"], rec.get("seconds"), flush=True)
            if shutil.disk_usage(ROOT).free < 3 * 1024**3:
                print("disk low; stopping")
                return
        if d is not None:
            shutil.rmtree(d, ignore_errors=True)   # keep the disk free: one clone at a time


if __name__ == "__main__":
    main()
