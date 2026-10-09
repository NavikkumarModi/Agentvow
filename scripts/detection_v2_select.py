"""Detection study v2, stage 2: select the PRs to reproduce (rules in docs/research/DETECTION_V2_PREREG.md).
Usage: python3 scripts/detection_v2_select.py  -> data/detection_v2_sample.csv
"""
import json
import random
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from agentvow.ci import TEST_JOB  # noqa: E402
from ci_study_analyze import outcome  # noqa: E402

SCREEN = ROOT / "data" / "detection_v2_screen.jsonl"
OUT = ROOT / "data" / "detection_v2_sample.csv"
MAX_MB, PER_REPO = 300, 3


def repo_mb(repo, cache={}):
    if repo not in cache:
        r = subprocess.run(["gh", "api", f"repos/{repo}", "--jq", ".size"], capture_output=True, text=True)
        cache[repo] = int(r.stdout) / 1024 if r.returncode == 0 and r.stdout.strip().isdigit() else None
    return cache[repo]


def main():
    rows = [json.loads(l) for l in SCREEN.read_text().splitlines() if l.strip()]
    for r in rows:
        r["o"] = outcome(r, False, TEST_JOB)
        r.setdefault("claimed", True)
    df = pd.DataFrame(rows)
    print("screened:", len(df), df.o.value_counts().to_dict(), file=sys.stderr)
    j = df[df.o.isin(["CONTRADICTED", "SUPPORTED"])].copy()
    j["mb"] = [repo_mb(r) for r in j.repo]
    j = j[j.mb.notna() & (j.mb < MAX_MB)]
    print("judged and < %d MB:" % MAX_MB, j.o.value_counts().to_dict(), "repos", j.repo.nunique(), file=sys.stderr)
    rng = random.Random(2027)
    pick = []
    for repo, g in j.groupby("repo"):
        bad = g[g.o == "CONTRADICTED"].to_dict("records"); rng.shuffle(bad)
        pick += [{**b, "group": "ci_failed"} for b in bad[:PER_REPO]]
    nfail = len(pick)
    failed_repos = {p["repo"] for p in pick}
    good = j[j.o == "SUPPORTED"].to_dict("records"); rng.shuffle(good)
    ctrl, per = [], {}
    for g in sorted(good, key=lambda x: x["repo"] not in failed_repos):   # same repositories first
        if len(ctrl) >= nfail:
            break
        if per.get(g["repo"], 0) < PER_REPO:
            ctrl.append({**g, "group": "ci_passed"}); per[g["repo"]] = per.get(g["repo"], 0) + 1
    out = pd.DataFrame(pick + ctrl)[["repo", "pr", "agent", "group", "o", "claimed", "merged", "mb"]].rename(columns={"o": "outcome", "mb": "size_mb"})
    out.to_csv(OUT, index=False)
    print(f"selected {nfail} CI-failed + {len(ctrl)} controls in {out.repo.nunique()} repos -> {OUT}", file=sys.stderr)
    print(out.group.value_counts().to_dict(), out.agent.value_counts().to_dict(), "claimed:", out.claimed.value_counts().to_dict(), file=sys.stderr)


if __name__ == "__main__":
    main()
