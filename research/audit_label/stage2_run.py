"""Stage 2 of the audit study (docs/research/AUDIT_STUDY_PREREG.md; owner authorisation 2026-10-28: sandboxed installs and test runs of these open-source repositories): run the frozen audit, `agentvow check --setup auto
--run-tests`, on the pull requests that change Python files and carry a tests, lint or impact claim, and record every finding. One pull request at a time (the disk is small): shallow partial clone into the session scratch folder at the
pull request's head, the pull request's base commit as --base, a fresh AGENTVOW_HOME per run, the clone deleted afterwards. The product's own sandbox and environment-size guard decide what can run; a run that cannot run is a result
(UNKNOWN, and a reach observation), not an error. Resumable. Output: data/audit/stage2.jsonl.
Usage: python3 research/audit_label/stage2_run.py [--limit N] [--only ITEM ...]"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "audit" / "stage2.jsonl"
SCRATCH = Path(os.environ.get("AUDIT_SCRATCH", "/private/tmp/claude-501/-Users-navikkumarmodi-Agentvow/a2f1ab05-5ca4-480e-95ed-6086282ef66a/scratchpad/stage2"))
KINDS = {"tests_pass", "lint_clean", "backward_compatible", "no_downstream_impact"}
TIMEOUT = 40 * 60
MIN_FREE = 1.2 * 1024**3


def sh(*a, cwd=None, timeout=900, env=None):
    return subprocess.run(a, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)


def gh_cached(path):
    key = ROOT / "data" / "audit" / "api" / (path.replace("/", "_").replace("?", "_") + ".json")
    return json.loads(key.read_text()) if key.exists() else None


def targets():
    rows = json.loads((ROOT / "data/audit/score_stage1.json").read_text())["rows"]
    items = {}
    for f in sorted(glob.glob(str(ROOT / "docs/research/audit_data/items/*.json"))):
        items[Path(f).stem] = json.load(open(f))
    out = []
    for key in sorted({r["item"] for r in rows if r["step_a"] == "CLAIM" and r["kind"] in KINDS}):
        it = items[key]
        o, r = it["repo"].split("/")
        files = gh_cached(f"repos/{o}/{r}/pulls/{it['number']}/files?per_page=100")
        pr = gh_cached(f"repos/{o}/{r}/pulls/{it['number']}")
        if isinstance(files, list) and isinstance(pr, dict) and "base" in pr and any(f["filename"].endswith(".py") for f in files):
            out.append({"item": key, "repo": it["repo"], "number": it["number"], "base": pr["base"]["sha"], "head": pr["head"]["sha"], "message": it["message"]})
    return out


def run_one(t):
    SCRATCH.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(SCRATCH).free
    rec = {"item": t["item"], "repo": t["repo"], "number": t["number"], "free_gb_before": round(free / 1024**3, 2)}
    if free < MIN_FREE:
        return {**rec, "outcome": "skipped_low_disk"}
    d = SCRATCH / t["item"]
    shutil.rmtree(d, ignore_errors=True)
    home = tempfile.mkdtemp(prefix="s2home_", dir=SCRATCH)
    start = time.time()
    try:
        p = sh("git", "clone", "-q", "--no-checkout", "--filter=blob:none", f"https://github.com/{t['repo']}.git", str(d), timeout=1200)
        if p.returncode:
            return {**rec, "outcome": "clone_failed", "why": p.stderr[-200:]}
        sh("git", "fetch", "-q", "origin", f"pull/{t['number']}/head", cwd=d, timeout=900)
        p = sh("git", "checkout", "-q", "-f", t["head"], cwd=d, timeout=900)
        if p.returncode:
            return {**rec, "outcome": "checkout_failed", "why": p.stderr[-200:]}
        if sh("git", "cat-file", "-e", t["base"] + "^{commit}", cwd=d).returncode:
            sh("git", "fetch", "-q", "origin", t["base"], cwd=d, timeout=900)
        msg = Path(home) / "message.txt"
        msg.write_text(t["message"])
        env = {**os.environ, "AGENTVOW_HOME": home, "PYTHONPATH": str(ROOT)}
        try:
            p = subprocess.run([sys.executable, "-m", "agentvow", "check", "--repo", str(d), "--base", t["base"], "--transcript", str(msg), "--run-tests", "--setup", "auto", "--json"],
                               capture_output=True, text=True, timeout=TIMEOUT, env=env)
        except subprocess.TimeoutExpired:
            return {**rec, "outcome": "timeout", "seconds": round(time.time() - start)}
        try:
            o = json.loads(p.stdout)
        except ValueError:
            return {**rec, "outcome": "no_json", "exit": p.returncode, "why": (p.stdout + p.stderr)[-300:], "seconds": round(time.time() - start)}
        return {**rec, "outcome": "ran", "exit": p.returncode, "status": o.get("status"), "seconds": round(time.time() - start), "scope": str(o.get("scope", ""))[:300],
                "findings": [{"claim": f.get("claim"), "kind": f.get("kind"), "verdict": f.get("verdict"), "attention": f.get("attention"), "why": str(f.get("why", ""))[:400]} for f in o.get("findings", [])],
                "stderr": p.stderr[-300:]}
    finally:
        shutil.rmtree(d, ignore_errors=True)
        shutil.rmtree(home, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args(argv)
    done = {json.loads(l)["item"] for l in OUT.read_text().splitlines()} if OUT.exists() else set()
    n = 0
    for t in targets():
        if a.only and t["item"] not in a.only:
            continue
        if t["item"] in done:
            continue
        if a.limit is not None and n >= a.limit:
            break
        rec = run_one(t)
        with OUT.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        n += 1
        print(t["item"], t["repo"], rec["outcome"], rec.get("status"), rec.get("seconds"), flush=True)


if __name__ == "__main__":
    main()
