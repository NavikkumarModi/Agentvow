"""Detection study v2 analysis exactly as pre-registered (docs/research/DETECTION_V2_PREREG.md). Usage: python3 scripts/detection_v2_analyze.py"""
import json
import math
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "data" / "detection_v2_results.jsonl"


def wilson(k, n, z=1.96):
    if not n:
        return (0.0, 0.0)
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def fmt(k, n):
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {100 * k / n:.0f}% [{100 * lo:.0f}, {100 * hi:.0f}]" if n else "0/0"


def klass(row, review):
    v = row["verdict_review" if review else "verdict"]; st = row["status_review" if review else "status"]
    if v == "CONTRADICTED":
        return "CONTRADICTED"
    if st == "REVIEW REQUIRED":
        return "REVIEW"
    if v in ("SUPPORTED_BY_PRIOR_EVIDENCE", "NOT_CONTRADICTED"):
        return "SUPPORTED/NOT_CONTRADICTED"
    return "UNKNOWN"


def main():
    rows = [json.loads(l) for l in RES.read_text().splitlines() if l.strip()]
    df = pd.DataFrame(rows)
    print(f"PRs with a result row: {len(df)} in {df.repo.nunique()} repos")
    print("\n== Q3 funnel (all selected PRs, by CI group)")
    print(pd.crosstab(df.stage, df.group).to_string())
    done = df[df.stage == "done"].copy()
    done["usable"] = done.usable_base.fillna(False)
    print(f"\nran (stage=done): {len(done)}; usable (base had passing tests): {int(done.usable.sum())}")
    for g in ("ci_failed", "ci_passed"):
        tot = (df.group == g).sum(); u = int(done[done.group == g].usable.sum())
        print(f"  {g}: reached a usable run {fmt(u, tot)}")
    u = done[done.usable].copy()
    for review in (False, True):
        u["k"] = [klass(r, review) for _, r in u.iterrows()]
        print(f"\n== Detector config: {'--new-test-failures review' if review else 'default (unknown)'}  (usable runs only)")
        for g in ("ci_failed", "ci_passed"):
            s = u[u.group == g]
            print(f"  {g} n={len(s)} repos={s.repo.nunique()}: {dict(Counter(s.k))}")
        f = u[u.group == "ci_failed"]; c = u[u.group == "ci_passed"]
        print(f"  Q1 recall: CONTRADICTED {fmt((f.k == 'CONTRADICTED').sum(), len(f))}; any alert (CONTRADICTED or REVIEW) {fmt(f.k.isin(['CONTRADICTED', 'REVIEW']).sum(), len(f))}; "
              f"miss (SUPPORTED/NOT_CONTRADICTED) {fmt((f.k == 'SUPPORTED/NOT_CONTRADICTED').sum(), len(f))}")
        print(f"  Q2 false alert on CI-passed controls: {fmt(c.k.isin(['CONTRADICTED', 'REVIEW']).sum(), len(c))}")
        fr = f[f.k.isin(['CONTRADICTED', 'REVIEW'])].repo.nunique()
        print(f"  repository level (CI-failed): {fr} of {f.repo.nunique()} repos with at least one alert")
    print("\n== Strata (default config, usable only): real claim in PR body vs hypothetical statement")
    u["k"] = [klass(r, False) for _, r in u.iterrows()]
    print(pd.crosstab([u.group, u.claimed], u.k).to_string())
    print("\n== Why CI-failed PRs did not produce a usable run (note field, first 60 chars)")
    nf = df[(df.group == "ci_failed") & ~df.index.isin(u.index)]
    print(Counter((r.get("stage"), str(r.get("note") or r.get("head_hint") or r.get("setup_notes") or "")[:60]) for _, r in nf.iterrows()).most_common(12))


if __name__ == "__main__":
    main()
