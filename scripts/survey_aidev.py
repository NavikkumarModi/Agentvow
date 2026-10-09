"""Claim-frequency survey over AIDev-pop PR bodies (Python repos only).

Usage: python3 scripts/survey_aidev.py [data/aidev]
Reports, per agent: PR count, share with any checkable claim, and per-claim-type rates, plus
rates for candidate phrasings the extractor does not cover yet.
"""
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agentmirror import claims  # noqa: E402

CANDIDATES = {
    "no_breaking_changes": re.compile(r"\b(?:no|without|non)[- ](?:breaking|behaviou?ral|functional) (?:changes?|impact)\b|\bbackward[s]?[- ]compatib|\bno functional change", re.I),
    "tests_added_or_updated": re.compile(r"\b(?:add(?:ed|s)?|updat(?:ed|es)?|new) (?:unit |regression )?tests?\b", re.I),
    "tests_pass_variants": re.compile(r"\b(?:pytest|tests?|ci|checks?|lint\w*)\b[^.\n]{0,40}\b(?:pass(?:ed|es|ing)?|green|succe\w+)\b", re.I),
    "refactor_only": re.compile(r"\b(?:pure |purely )?refactor(?:ing)?\b[^.\n]{0,40}\bno (?:behaviou?r|logic) change", re.I),
    "no_other_usages": re.compile(r"\b(?:no|not) other (?:usages?|callers?|uses)\b|\bonly (?:used|referenced) (?:in|by)\b", re.I),
}


def main(d="data/aidev"):
    d = Path(d)
    pr = pd.read_parquet(d / "pull_request.parquet")
    rp = pd.read_parquet(d / "repository.parquet")
    py = rp[rp["language"] == "Python"]
    df = pr[pr["repo_id"].isin(py["id"]) & pr["body"].notna() & (pr["body"].str.strip() != "")].copy()
    print(f"Python-repo PRs with a body: {len(df)} (repos: {df['repo_id'].nunique()}); all-language PRs: {len(pr)}")
    rows = []
    for agent, g in df.groupby("agent"):
        ex = [claims.extract(b) for b in g["body"]]
        r = {"agent": agent, "n": len(g),
             "any_checkable": sum(any(c.kind != "unchecked" for c in e) for e in ex) / len(g),
             "no_downstream_impact": sum(any(c.kind == claims.NO_IMPACT for c in e) for e in ex) / len(g),
             "tests_pass": sum(any(c.kind == claims.TESTS_PASS for c in e) for e in ex) / len(g),
             "generic_unchecked": sum(any(c.kind == "unchecked" for c in e) for e in ex) / len(g)}
        for name, pat in CANDIDATES.items():
            r[name] = g["body"].str.contains(pat).mean()
        rows.append(r)
    out = pd.DataFrame(rows).set_index("agent")
    pd.set_option("display.width", 200)
    print((out.drop(columns="n").mul(100).round(1)).assign(n=out["n"]).to_string())
    merged = df["merged_at"].notna()
    print(f"\nmerged share: {merged.mean():.1%}")
    print("tests_pass claim rate  merged vs unmerged:",
          f"{df[merged]['body'].map(lambda b: any(c.kind == claims.TESTS_PASS for c in claims.extract(b))).mean():.1%}",
          f"{df[~merged]['body'].map(lambda b: any(c.kind == claims.TESTS_PASS for c in claims.extract(b))).mean():.1%}")


if __name__ == "__main__":
    main(*sys.argv[1:])
