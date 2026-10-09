"""Analysis of the detection study (docs/research/DETECTION_STUDY.md): does the local run catch PRs whose CI test jobs failed?

Usage: python3 scripts/detection_analyze.py [data/detection_results.jsonl]
Groups: ci_failed (a CI test job failed on the head commit) and ci_passed (controls). Verdicts come from the shipped decision logic.
Reports run coverage, detection (CONTRADICTED among CI-failing PRs that ran), misses, unknowns, false alarms among controls, and why
tests could not run. Descriptive only; PRs cluster in repositories.
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent


def main(path):
    d = pd.DataFrame([json.loads(l) for l in Path(path).read_text().splitlines()])
    print(len(d), "PRs,", d.repo.nunique(), "repos | stage:", d.stage.value_counts().to_dict())
    d["res"] = d.apply(lambda r: r.verdict or "none" if r.stage == "done" else f"not run ({r.stage})", axis=1)
    print(pd.crosstab(d.group, d.res).to_string())
    dn = d[d.stage == "done"]
    print("\nhead_result by group:")
    print(pd.crosstab(dn.group, dn.head_result).to_string())
    f, p = dn[dn.group == "ci_failed"], dn[dn.group == "ci_passed"]
    miss = f.verdict.isin(["NOT_CONTRADICTED", "SUPPORTED_BY_PRIOR_EVIDENCE"])
    print(f"\nDETECTION among CI-failing PRs that ran: CONTRADICTED {(f.verdict == 'CONTRADICTED').sum()}/{len(f)} | "
          f"missed (NOT_CONTRADICTED/SUPPORTED) {miss.sum()} | UNKNOWN {(f.verdict == 'UNKNOWN').sum()}")
    print(f"FALSE ALARMS among CI-passing controls that ran: CONTRADICTED {(p.verdict == 'CONTRADICTED').sum()}/{len(p)}")
    def cause(r):
        s = str(r.head_summary)
        if r.head_result == "pass":
            return "ran, all passed"
        if "missing dependency" in s:
            return "environment: missing dependency"
        if "timeout" in s:
            return "environment: timeout"
        if r.head_result == "fail":
            return "ran, some failed"
        return "inconclusive: " + (str(r.head_hint)[:50] or s[:50])
    dn = dn.assign(cause=dn.apply(cause, axis=1))
    print("\nwhy tests did or did not give results:")
    print(pd.crosstab(dn.cause, dn.group).to_string())
    print("\nCONTRADICTED verdicts (inspect each by hand):")
    c = dn[dn.verdict == "CONTRADICTED"]
    print(c[["repo", "pr", "group", "why"]].assign(why=lambda x: x.why.str[:200]).to_string(index=False) if len(c) else "  none")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "data/detection_results.jsonl"))
