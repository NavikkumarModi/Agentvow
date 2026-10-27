"""Retrospective replay of existing Agentvow results through a candidate evidence->action mapping.
Advisory only: nothing here enforces anything. Reads local data files; prints markdown tables.
Usage: python3 research/autonomy/retro_policy.py"""
import collections
import csv
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data"

# Candidate mapping P0: the verdict alone. The only states these datasets carry
# (they predate the provenance fields, so partial_capture / harness_warning are not testable here).
P0 = {"CONTRADICTED": "stop", "UNKNOWN": "escalate", "NOT_CONTRADICTED": "continue", "SUPPORTED_BY_PRIOR_EVIDENCE": "continue"}


def planted():
    rows = list(csv.DictReader(open(DATA / "planted_faults_v5.csv")))
    # P1: P0, but "continue" is withheld when the comparison left tests uncomparable (the PR's own new tests carry the signal)
    out = {"P0": collections.Counter(), "P1": collections.Counter()}
    for r in rows:
        broke = r["oracle_break"] == "1"
        a0 = P0[r["verdict"]]
        a1 = "escalate" if a0 == "continue" and int(r["uncomparable"]) > 0 else a0
        for name, a in (("P0", a0), ("P1", a1)):
            out[name][("break" if broke else "no-break", a)] += 1
    return len(rows), out


def real():
    rows = [json.loads(l) for l in open(DATA / "detection_v2_results_plus.jsonl")]
    c = collections.Counter((r["ci_outcome"], P0[r["verdict"]]) for r in rows)
    claimed = collections.Counter((r["ci_outcome"], P0[r["verdict"]]) for r in rows if r["claimed"])
    return len(rows), c, claimed


def table(counter, truths):
    acts = ["continue", "escalate", "stop"]
    lines = ["| truth | " + " | ".join(acts) + " |", "|---|" + "---|" * len(acts)]
    for t in truths:
        lines.append(f"| {t} | " + " | ".join(str(counter.get((t, a), 0)) for a in acts) + " |")
    return "\n".join(lines)


if __name__ == "__main__":
    n, out = planted()
    print(f"## Planted faults v5 ({n} variants)\n")
    for k, v in out.items():
        print(f"**{k}**\n\n" + table(v, ["break", "no-break"]) + "\n")
    n, c, cl = real()
    print(f"## Real agent PRs, detection v2 plus ({n} PRs; truth = the repository's CI outcome, a noisy proxy)\n")
    print("all PRs\n\n" + table(c, ["CONTRADICTED", "SUPPORTED"]) + "\n")
    print("PRs where the agent claimed tests pass\n\n" + table(cl, ["CONTRADICTED", "SUPPORTED"]))
