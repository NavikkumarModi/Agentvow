"""Stage B phase 1 (docs/research/forecast_grounding/STAGE_B.md section 2): structural candidates from merged AIDev Python PRs. Read-only GitHub API.
Seed fixed here: SEED = 2028. Usage: python3 research/preconditions/stageb_candidates.py [n_sample=2600]  -> data/preconditions/stageb_cands.jsonl (resumable)"""
import json
import random
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data"
OUT = D / "preconditions" / "stageb_cands.jsonl"
SEED = 2028
MAX_LINES, MAX_FILES, MAX_MB = 200, 6, 300


def gh(path):
    for attempt in range(3):
        r = subprocess.run(["gh", "api", path], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return json.loads(r.stdout)
        if "rate limit" in (r.stderr or "").lower():
            time.sleep(120)
            continue
        return None
    return None


def is_test(f):
    low = f.lower()
    base = low.split("/")[-1]
    return base.startswith("test_") or base.endswith("_test.py") or "/tests/" in "/" + low or "/test/" in "/" + low


def used_before():
    seen = set()
    for name, rk, pk in (("ci_study.jsonl", "repo", "pr"), ("detection_v2_screen.jsonl", "repo", "pr")):
        p = D / name
        if p.exists():
            for l in p.read_text().splitlines():
                try:
                    j = json.loads(l); seen.add((j[rk], int(j[pk])))
                except Exception:
                    pass
    for name in ("detection_sample.csv", "local_coverage_sample.csv", "detection_v2_sample.csv"):
        p = D / name
        if p.exists():
            d = pd.read_csv(p); seen |= set(zip(d.repo, d.pr.astype(int)))
    return seen


sizes = {}


def mb(repo):
    if repo not in sizes:
        j = gh(f"repos/{repo}")
        sizes[repo] = (j["size"] / 1024) if j else None
    return sizes[repo]


def screen(row):
    repo, n = row["repo"], row["pr"]
    files = gh(f"repos/{repo}/pulls/{n}/files?per_page=100")
    if files is None:
        return {**row, "ok": False, "why": "api_files"}
    py = [f for f in files if f["filename"].endswith(".py")]
    tests = [f["filename"] for f in py if is_test(f["filename"]) and f["status"] != "removed"]
    src = [f["filename"] for f in py if not is_test(f["filename"])]
    lines = sum(f["additions"] + f["deletions"] for f in files)
    out = {**row, "n_files": len(files), "lines": lines, "test_files": tests, "src_files": src}
    if not tests or not src:
        return {**out, "ok": False, "why": "no_test_and_src"}
    if lines > MAX_LINES or len(files) > MAX_FILES:
        return {**out, "ok": False, "why": "too_big"}
    size = mb(repo)
    if size is None or size >= MAX_MB:
        return {**out, "ok": False, "why": "repo_size"}
    info = gh(f"repos/{repo}/pulls/{n}")
    if not info:
        return {**out, "ok": False, "why": "api_pr"}
    return {**out, "ok": True, "base": info["base"]["sha"], "head": info["head"]["sha"], "title": info.get("title", ""), "body": (info.get("body") or "")[:3000], "mb": round(size, 1)}


def main(n_sample=2600):
    pr = pd.read_parquet(D / "aidev" / "pull_request.parquet")
    rp = pd.read_parquet(D / "aidev" / "repository.parquet").set_index("id")
    py = rp[rp.language == "Python"]
    d = pr[pr.repo_id.isin(py.index) & pr.merged_at.notna()].copy()
    d["repo"] = [py.loc[i, "full_name"] for i in d.repo_id]
    seen = used_before()
    d = d[[(r, int(n)) not in seen for r, n in zip(d.repo, d.number)]]
    rows = [{"repo": r.repo, "pr": int(r.number), "agent": r.agent} for r in d.itertuples()]
    random.Random(SEED).shuffle(rows)
    rows = rows[:n_sample]
    done = {(j["repo"], j["pr"]) for j in map(json.loads, OUT.read_text().splitlines())} if OUT.exists() else set()
    todo = [r for r in rows if (r["repo"], r["pr"]) not in done]
    print(f"pool {len(d)}; sample {len(rows)}; to screen {len(todo)}; seed {SEED}", file=sys.stderr)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("a") as fh, ThreadPoolExecutor(6) as ex:
        for i, res in enumerate(ex.map(screen, todo), 1):
            fh.write(json.dumps(res) + "\n"); fh.flush()
            if i % 200 == 0:
                print(f"{i}/{len(todo)}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2600)
