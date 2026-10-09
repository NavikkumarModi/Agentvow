"""Analysis for docs/research/CI_CLAIM_STUDY.md (as pre-registered)."""
import json
import math
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agentvow.ci import TEST_JOB, TEST_JOB_V1  # noqa: E402

BAD = {"failure", "timed_out", "cancelled", "action_required"}


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"),) * 2
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def outcome(r, drop_cancelled=False, rx=TEST_JOB_V1):
    if r["status"] != "ok":
        return "EXCLUDED_" + r["status"]
    runs = [(n, c) for n, s, c in r["jobs"] if s == "completed"]
    if not runs and not r["jobs"]:
        return "NO_CI"
    tests = [(n, c) for n, c in runs if rx.search(n) and c not in ("neutral", "skipped")]
    bad = BAD - ({"cancelled", "timed_out"} if drop_cancelled else set())
    if any(c in bad for _, c in tests):
        return "CONTRADICTED"
    if any(c == "success" for _, c in tests):
        return "SUPPORTED"
    return "NO_TEST_JOB"


def fmt(k, n):
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {100 * k / n:.1f}% [{100 * lo:.1f}, {100 * hi:.1f}]" if n else "0/0"


def main():
    rows = [json.loads(l) for l in (ROOT / "data/ci_study.jsonl").read_text().splitlines()]
    df = pd.DataFrame(rows)
    df["outcome"] = [outcome(r) for r in rows]
    print("N sampled:", len(df), "| excluded:", df.outcome.str.startswith("EXCLUDED").sum(), df[df.outcome.str.startswith("EXCLUDED")].outcome.value_counts().to_dict())
    d = df[~df.outcome.str.startswith("EXCLUDED")]
    print("\nRQ1 overall outcome shares (n=%d):" % len(d))
    for o in ("CONTRADICTED", "SUPPORTED", "NO_TEST_JOB", "NO_CI"):
        print(f"  {o:13s} {fmt((d.outcome == o).sum(), len(d))}")
    j = d[d.outcome.isin(["CONTRADICTED", "SUPPORTED"])]
    print(f"  judgeable {fmt(len(j), len(d))}; CONTRADICTED among judgeable {fmt((j.outcome == 'CONTRADICTED').sum(), len(j))}")
    print("\nRQ2 by agent (n, judgeable share, contradicted among judgeable):")
    for a, g in d.groupby("agent"):
        jj = g[g.outcome.isin(["CONTRADICTED", "SUPPORTED"])]
        print(f"  {a:13s} n={len(g):3d} | judgeable {fmt(len(jj), len(g))} | contradicted {fmt((jj.outcome == 'CONTRADICTED').sum(), len(jj))} | no_ci {fmt((g.outcome == 'NO_CI').sum(), len(g))}")
    print("\nby merged:")
    for m, g in d.groupby("merged"):
        jj = g[g.outcome.isin(["CONTRADICTED", "SUPPORTED"])]
        print(f"  merged={m!s:5s} n={len(g):3d} | judgeable {fmt(len(jj), len(g))} | contradicted {fmt((jj.outcome == 'CONTRADICTED').sum(), len(jj))}")
    print("\nSensitivity (a) single-commit PRs only:")
    s = d[d.commits == 1]; sj = s[s.outcome.isin(["CONTRADICTED", "SUPPORTED"])]
    print(f"  n={len(s)} | judgeable {fmt(len(sj), len(s))} | contradicted {fmt((sj.outcome == 'CONTRADICTED').sum(), len(sj))}")
    print("Sensitivity (b) excluding cancelled/timed-out as failures:")
    o2 = pd.Series([outcome(r, True) for r in rows], index=df.index); d2 = df.assign(o2=o2)[~df.outcome.str.startswith("EXCLUDED")]
    j2 = d2[d2.o2.isin(["CONTRADICTED", "SUPPORTED"])]
    print(f"  judgeable {fmt(len(j2), len(d2))} | contradicted {fmt((j2.o2 == 'CONTRADICTED').sum(), len(j2))}")
    print("\nPOST-HOC (declared after RQ4): classifier v2 on the same data")
    o3 = pd.Series([outcome(r, False, TEST_JOB) for r in rows], index=df.index)
    d3 = df.assign(o3=o3)[~df.outcome.str.startswith("EXCLUDED")]
    for o in ("CONTRADICTED", "SUPPORTED", "NO_TEST_JOB", "NO_CI"):
        print(f"  {o:13s} {fmt((d3.o3 == o).sum(), len(d3))}")
    j3 = d3[d3.o3.isin(["CONTRADICTED", "SUPPORTED"])]
    print(f"  judgeable {fmt(len(j3), len(d3))}; CONTRADICTED among judgeable {fmt((j3.o3 == 'CONTRADICTED').sum(), len(j3))}")
    for a, g in d3.groupby("agent"):
        jj = g[g.o3.isin(["CONTRADICTED", "SUPPORTED"])]
        if len(jj):
            print(f"    {a:13s} judgeable {len(jj)}/{len(g)} | contradicted {fmt((jj.o3 == 'CONTRADICTED').sum(), len(jj))}")
    for m, g in d3.groupby("merged"):
        jj = g[g.o3.isin(["CONTRADICTED", "SUPPORTED"])]
        print(f"    merged={m!s:5s} contradicted {fmt((jj.o3 == 'CONTRADICTED').sum(), len(jj))}")
    df.to_csv(ROOT / "data/ci_study_outcomes.csv", index=False)


if __name__ == "__main__":
    main()
