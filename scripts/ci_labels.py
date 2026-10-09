"""Ground truth from independent CI: for AIDev agent PRs that claim 'tests pass', fetch the CI conclusion on the PR head commit.

Read-only GitHub API GETs through `gh` (public repos). Usage: python3 scripts/ci_labels.py [N_per_stratum]
Writes data/ci_labels.csv. Label: ci = failure | success | none (no checks) | error.
"""
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agentmirror_check import claims  # noqa: E402


def gh(path):
    r = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None


def ci_state(owner_repo, sha):
    cr = gh(f"repos/{owner_repo}/commits/{sha}/check-runs?per_page=100")
    runs = (cr or {}).get("check_runs", [])
    st = gh(f"repos/{owner_repo}/commits/{sha}/status")
    concl = [r["conclusion"] for r in runs if r.get("status") == "completed"]
    legacy = (st or {}).get("state") if (st or {}).get("statuses") else None
    if any(c in ("failure", "timed_out", "cancelled", "action_required") for c in concl) or legacy in ("failure", "error"):
        return "failure"
    if concl or legacy == "success":
        return "success" if all(c in ("success", "neutral", "skipped") for c in concl) else "mixed"
    return "none"


def main(n=75):
    pr = pd.read_parquet(ROOT / "data/aidev/pull_request.parquet")
    rp = pd.read_parquet(ROOT / "data/aidev/repository.parquet")
    py = rp[rp.language == "Python"].set_index("id")
    d = pr[pr.repo_id.isin(py.index) & pr.body.notna() & (pr.agent != "OpenAI_Codex")].copy()
    d["tp"] = d.body.map(lambda b: any(c.kind == "tests_pass" for c in claims.extract(b)))
    d = d[d.tp]
    d["merged"] = d.merged_at.notna()
    rows = []
    for merged, g in d.groupby("merged"):
        for _, p in g.sample(min(n, len(g)), random_state=7).iterrows():
            full = py.loc[p.repo_id, "full_name"]
            info = gh(f"repos/{full}/pulls/{int(p.number)}")
            if not info:
                rows.append({"repo": full, "pr": int(p.number), "agent": p.agent, "merged": merged, "ci": "error"}); continue
            sha = info["head"]["sha"]
            rows.append({"repo": full, "pr": int(p.number), "agent": p.agent, "merged": merged, "head": sha,
                         "base": info["base"]["sha"], "ci": ci_state(full, sha)})
    out = pd.DataFrame(rows)
    out.to_csv(ROOT / "data/ci_labels.csv", index=False)
    print(out.groupby(["merged", "ci"]).size().unstack(fill_value=0))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 75)
