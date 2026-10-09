"""Pilot analysis exactly as pre-registered (docs/research/forecast_grounding/PRECONDITIONS_PREREG.md). Usage: python3 research/preconditions/analyze_pilot.py"""
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

RES = Path(__file__).resolve().parents[2] / "data" / "preconditions" / "pilot_results.jsonl"


def wilson(k, n, z=1.96):
    if not n:
        return (0, 0)
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def fmt(k, n):
    lo, hi = wilson(k, n)
    return f"{k}/{n}" + (f" = {100 * k / n:.0f}% [{100 * lo:.0f}, {100 * hi:.0f}]" if n else "")


def res(r, key):
    return ((r.get(key) or {}).get("evidence") or {}).get("result")


def determinate(r, key):
    v = (r.get(key) or {}).get("verdict")
    return v is not None and v != "UNKNOWN"


def sufficient(r):
    """Recipe replay reproduces the agent-environment result (pass/pass or fail/fail)."""
    rr = res(r, "recipe_replay")
    return rr is not None and rr in ("pass", "fail") and rr == r["truth_in_agent_env"]


def taxonomy(r):
    s = (((r.get("recipe_replay") or {}).get("evidence") or {}).get("summary") or "").lower()
    if "missing dependency" in s:
        return "missing package (undeclared dependency)"
    if "filenotfound" in s or "no such file" in s:
        return "missing file (generated/untracked)"
    if "keyerror" in s:
        return "missing environment variable"
    if "typeerror" in s or "attributeerror" in s or "importerror" in s:
        return "version drift / API mismatch"
    return "other/unclassified: " + s[:60]


def main():
    rows = [json.loads(l) for l in RES.read_text().splitlines() if l.strip()]
    print(f"{len(rows)} runs; tasks {len({r['task'] for r in rows})}; cost ${sum(r.get('cost_usd') or 0 for r in rows):.2f}; "
          f"errors {sum(bool(r.get('is_error')) for r in rows)}; agent exit!=0 {sum(r.get('agent_exit') != 0 for r in rows)}")
    by = defaultdict(list)
    for r in rows:
        by[r["cond"]].append(r)
    print("\n== Basics by condition")
    for c in sorted(by):
        g = by[c]
        print(f"  {c}: n={len(g)} | claim made {fmt(sum(r['claim_made'] for r in g), len(g))} | truth in agent env {fmt(sum(r['truth_in_agent_env']=='pass' for r in g), len(g))} | "
              f"tests edited {sum(r['tests_modified'] for r in g)} | recipe written {sum(r['recipe_written'] for r in g)} | recipe invalid {sum(bool(r.get('recipe_error')) for r in g)}")
    print("\n== Accountability (determinate tests-pass verdict)  [primary]")
    for c in sorted(by):
        g = by[c]
        print(f"  {c}: zero-config ladder {fmt(sum(determinate(r, 'ladder') for r in g), len(g))}" +
              (f" | agent's recipe {fmt(sum(determinate(r, 'recipe_replay') for r in g), len(g))}" if c != "C0" else ""))
    print("\n== Sufficiency of the declared preconditions  [primary]  (C1/C2; recipe replay reproduces the agent-environment result)")
    for c in ("C1", "C2"):
        g = by.get(c, [])
        print(f"  {c}: {fmt(sum(sufficient(r) for r in g), len(g))}")
    print("  paired, same agent output: ladder replay reproduces truth in " + ", ".join(
        f"{c} {fmt(sum(res(r, 'ladder') == r['truth_in_agent_env'] for r in by.get(c, [])), len(by.get(c, [])))}" for c in sorted(by)))
    print("\n== By trap type (C1+C2 recipe sufficiency | ladder replay reproduces, all conditions)")
    traps = sorted({r["trap"] for r in rows})
    for t in traps:
        rc = [r for r in rows if r["trap"] == t and r["cond"] != "C0"]
        ra = [r for r in rows if r["trap"] == t]
        print(f"  {t:22} recipe {fmt(sum(sufficient(r) for r in rc), len(rc)):18} | ladder {fmt(sum(res(r, 'ladder') == r['truth_in_agent_env'] for r in ra), len(ra))}")
    print("\n== Hidden state per run, by condition (mean count)")
    for c in sorted(by):
        g = by[c]
        print(f"  {c}: undeclared installs/env/system (session audit) {sum(len(r['audit']['undeclared']) for r in g) / len(g):.2f} | ambient undeclared imports {sum(len(r['ambient_undeclared']) for r in g) / len(g):.2f}")
    print("\n== Failure taxonomy of insufficient recipe replays")
    bad = [r for r in rows if r["cond"] != "C0" and r.get("recipe_replay") and not sufficient(r)]
    for k, v in Counter(taxonomy(r) for r in bad).most_common():
        print(f"  {v}  {k}")
    missing = [r for r in rows if r["cond"] != "C0" and not r["recipe_written"]]
    print(f"  (+ {len(missing)} C1/C2 runs wrote no recipe: {[r['task'][:3] + r['cond'] for r in missing]})")
    print("\n== Per-run table")
    for r in sorted(rows, key=lambda x: (x["task"], x["cond"])):
        print(f"  {r['task'][:24]:24} {r['cond']} claim={int(r['claim_made'])} truth={r['truth_in_agent_env']:4} ladder={str(res(r,'ladder')):12} recipe={str(res(r,'recipe_replay')):12} undecl={len(r['audit']['undeclared'])} ambient={len(r['ambient_undeclared'])}")


if __name__ == "__main__":
    main()
