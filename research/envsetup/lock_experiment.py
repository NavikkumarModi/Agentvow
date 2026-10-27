"""Does installing from the repository's own lock file lower the share of inconclusive replays? For pull requests of repositories that ship a lock file and whose replay was inconclusive in the
detection study, run the product (`agentvow check --setup auto --run-tests`) twice on the same machine: AGENTVOW_LOCK=0 (the old ladder) and AGENTVOW_LOCK=1 (pins first). Resumable.
This clones third-party repositories and runs their installs and tests inside Agentvow's sandbox (network allowed for installs only); it needs several GB of disk and hours of time.
Usage: python3 research/envsetup/lock_experiment.py [max_prs_per_repo=2]   -> data/checker_eval/lock_experiment.jsonl"""
import collections
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "checker_eval"
OUT = DATA / "lock_experiment.jsonl"
CLONES = ROOT / "data" / "lock_clones"
TIMEOUT = 40 * 60


def sh(*a, cwd=None, timeout=900, env=None):
    return subprocess.run(a, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)


def prepare(t):
    d = CLONES / t["repo"].replace("/", "__")
    if not d.exists():
        CLONES.mkdir(parents=True, exist_ok=True)
        p = sh("git", "clone", "-q", "--no-checkout", "--filter=blob:none", f"https://github.com/{t['repo']}.git", str(d), timeout=1800)
        if p.returncode:
            return None, "clone failed: " + p.stderr[-150:]
    sh("git", "fetch", "-q", "origin", f"pull/{t['pr']}/head", cwd=d, timeout=900)
    p = sh("git", "checkout", "-q", "-f", t["head"], cwd=d, timeout=900)
    if p.returncode:
        return None, "checkout failed: " + p.stderr[-150:]
    if sh("git", "cat-file", "-e", t["base"] + "^{commit}", cwd=d).returncode:
        sh("git", "fetch", "-q", "origin", t["base"], cwd=d, timeout=900)
    sh("git", "clean", "-fdxq", cwd=d)
    return d, ""


def run(d, t, lock):
    home = tempfile.mkdtemp(prefix="lockexp_home_")
    env = {**os.environ, "AGENTVOW_LOCK": "1" if lock else "0", "AGENTVOW_HOME": home, "PYTHONPATH": str(ROOT)}
    start = time.time()
    try:
        p = subprocess.run([sys.executable, "-m", "agentvow", "check", "--repo", str(d), "--base", t["base"], "--run-tests", "--setup", "auto", "--json"], input="All tests pass.\n",
                           capture_output=True, text=True, timeout=TIMEOUT, env=env)
        try:
            o = json.loads(p.stdout)
            f = next((x for x in o["findings"] if x["kind"] == "tests_pass"), o["findings"][0])
            return {"verdict": f["verdict"], "why": f["why"][:400], "scope": o.get("scope", "")[:300], "stderr": p.stderr[-400:], "seconds": round(time.time() - start)}
        except (ValueError, KeyError, IndexError):
            return {"verdict": "ERROR", "why": (p.stdout + p.stderr)[-400:], "seconds": round(time.time() - start)}
    except subprocess.TimeoutExpired:
        return {"verdict": "TIMEOUT", "why": "", "seconds": TIMEOUT}
    finally:
        shutil.rmtree(home, ignore_errors=True)
        sh("git", "clean", "-fdxq", cwd=d)


def main():
    per = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    targets = json.loads((DATA / "lock_targets.json").read_text())
    cnt, sel = collections.Counter(), []
    for t in targets:
        if cnt[t["repo"]] < per:
            cnt[t["repo"]] += 1
            sel.append(t)
    done = {(json.loads(l)["repo"], json.loads(l)["pr"], json.loads(l)["lock"]) for l in OUT.read_text().splitlines()} if OUT.exists() else set()
    for t in sel:
        d = None
        for lock in (False, True):
            if (t["repo"], t["pr"], lock) in done:
                continue
            if d is None:
                d, why = prepare(t)
                if d is None:
                    with OUT.open("a") as f:
                        f.write(json.dumps({**t, "lock": lock, "verdict": "PREPARE_FAILED", "why": why}) + "\n")
                    break
            rec = {**t, "lock": lock, **run(d, t, lock)}
            with OUT.open("a") as f:
                f.write(json.dumps(rec) + "\n")
            print(t["repo"], t["pr"], "lock" if lock else "old ", rec["verdict"], rec.get("seconds"), flush=True)
            if shutil.disk_usage(ROOT).free < 3 * 1024**3:
                print("disk low; stopping")
                return


if __name__ == "__main__":
    main()
