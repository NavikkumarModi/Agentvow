"""CI-claim study data collection (see docs/research/CI_CLAIM_STUDY.md). Read-only GitHub API via gh. Resumable.
Usage: python3 scripts/ci_study.py [per_agent=300] [workers=8]  -> data/ci_study.jsonl
"""
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agentmirror import claims  # noqa: E402

OUT = ROOT / "data" / "ci_study.jsonl"


def gh(path):
    r = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        return None
    return json.loads(r.stdout)


def fetch(row):
    repo, n = row["repo"], row["pr"]
    out = dict(row)
    info = gh(f"repos/{repo}/pulls/{n}")
    if not info:
        return {**out, "status": "error_pr"}
    sha = info["head"]["sha"]
    out.update(head=sha, commits=info.get("commits"), state=info.get("state"), merged_api=info.get("merged"))
    cr = gh(f"repos/{repo}/commits/{sha}/check-runs?per_page=100")
    if cr is None:
        return {**out, "status": "error_checks"}
    runs = cr.get("check_runs", [])
    if cr.get("total_count", 0) > len(runs):
        return {**out, "status": "truncated", "total_runs": cr.get("total_count")}
    out["status"] = "ok"
    out["jobs"] = [[r.get("name", ""), r.get("status"), r.get("conclusion")] for r in runs]
    return out


def main(per_agent=300, workers=8):
    pr = pd.read_parquet(ROOT / "data/aidev/pull_request.parquet")
    rp = pd.read_parquet(ROOT / "data/aidev/repository.parquet").set_index("id")
    py = rp[rp.language == "Python"]
    d = pr[pr.repo_id.isin(py.index) & pr.body.notna() & (pr.body.str.strip() != "")].copy()
    d["tp"] = d.body.map(lambda b: any(c.kind == "tests_pass" for c in claims.extract(b)))
    d = d[d.tp]
    print("claiming PRs by agent:", d.agent.value_counts().to_dict(), file=sys.stderr)
    sample = pd.concat([g.sample(min(per_agent, len(g)), random_state=2026) for _, g in d.groupby("agent")])
    rows = [{"repo": py.loc[r.repo_id, "full_name"], "pr": int(r.number), "agent": r.agent, "merged": bool(pd.notna(r.merged_at))}
            for r in sample.itertuples()]
    done = set()
    if OUT.exists():
        done = {(j["repo"], j["pr"]) for j in map(json.loads, OUT.read_text().splitlines() if OUT.stat().st_size else [])}
    todo = [r for r in rows if (r["repo"], r["pr"]) not in done]
    print(f"sample {len(rows)}, already done {len(done)}, to fetch {len(todo)}", file=sys.stderr)
    with OUT.open("a") as fh, ThreadPoolExecutor(workers) as ex:
        for i, res in enumerate(ex.map(fetch, todo), 1):
            fh.write(json.dumps(res) + "\n"); fh.flush()
            if i % 100 == 0:
                print(f"{i}/{len(todo)}", file=sys.stderr)


if __name__ == "__main__":
    main(*[int(x) for x in sys.argv[1:]])
