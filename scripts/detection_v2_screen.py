"""Detection study v2, stage 1: screen NEW agent PRs for CI outcome (see docs/research/DETECTION_V2_PREREG.md). Read-only GitHub API. Resumable.
Usage: python3 scripts/detection_v2_screen.py [per_agent=250] [workers=6]  -> data/detection_v2_screen.jsonl
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from agentvow import claims  # noqa: E402
from ci_study import fetch  # noqa: E402

OUT = ROOT / "data" / "detection_v2_screen.jsonl"
PRIOR = ROOT / "data" / "ci_study.jsonl"


def main(per_agent=250, workers=6):
    pr = pd.read_parquet(ROOT / "data/aidev/pull_request.parquet")
    rp = pd.read_parquet(ROOT / "data/aidev/repository.parquet").set_index("id")
    py = rp[rp.language == "Python"]
    d = pr[pr.repo_id.isin(py.index) & pr.body.notna() & (pr.body.str.strip() != "")].copy()
    d["tp"] = d.body.map(lambda b: any(c.kind == "tests_pass" for c in claims.extract(b)))
    d = d[d.tp]
    seen = {(j["repo"], j["pr"]) for j in map(json.loads, PRIOR.read_text().splitlines() if PRIOR.exists() else [])}
    d["repo"] = [py.loc[i, "full_name"] for i in d.repo_id]
    d = d[[(r, int(n)) not in seen for r, n in zip(d.repo, d.number)]]
    print("fresh claiming PRs by agent:", d.agent.value_counts().to_dict(), file=sys.stderr)
    sample = pd.concat([g.sample(min(per_agent, len(g)), random_state=2027) for _, g in d.groupby("agent")])
    rows = [{"repo": r.repo, "pr": int(r.number), "agent": r.agent, "merged": bool(pd.notna(r.merged_at))} for r in sample.itertuples()]
    done = set()
    if OUT.exists() and OUT.stat().st_size:
        done = {(j["repo"], j["pr"]) for j in map(json.loads, OUT.read_text().splitlines())}
    todo = [r for r in rows if (r["repo"], r["pr"]) not in done]
    print(f"sample {len(rows)}, already done {len(done)}, to fetch {len(todo)}", file=sys.stderr)
    with OUT.open("a") as fh, ThreadPoolExecutor(workers) as ex:
        for i, res in enumerate(ex.map(fetch, todo), 1):
            fh.write(json.dumps(res) + "\n"); fh.flush()
            if i % 100 == 0:
                print(f"{i}/{len(todo)}", file=sys.stderr)


if __name__ == "__main__":
    main(*[int(x) for x in sys.argv[1:]])
