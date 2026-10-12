"""Stage B6 analysis per STAGE_B6_PREREG.md: every denominator is printed; capture failures stay distinct outcomes. Usage: python3 research/preconditions/analyze_stageb6.py"""
import json
import math
import re
from collections import Counter
from pathlib import Path

D = Path(__file__).resolve().parents[2] / "data" / "preconditions"


def wil(k, n, z=1.96):
    if not n:
        return (0, 0)
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return round(100 * (c - h) / d), round(100 * (c + h) / d)


def res(r, k):
    return ((r.get(k) or {}).get("evidence") or {}).get("result")


def why(r):
    s = str(((r.get("freeze_replay") or {}).get("evidence") or {}).get("summary") or "") + str(((r.get("freeze_replay") or {}).get("scope") or ""))
    s = re.sub(r"/private\S+|/var/\S+", "<p>", s)
    for key, label in (("too heavy", "environment too heavy"), ("could not be built", "environment not built"), ("isolation failure", "isolation guard"), ("missing dependency", "missing dependency"),
                       ("No module named pytest", "pytest missing"), ("1 error", "collection error"), ("ImportError", "import error")):
        if key in s:
            return label
    return "other: " + s[:50]


def main():
    R = [json.loads(l) for l in (D / "stageb6_results.jsonl").read_text().splitlines() if l.strip()]
    A = len(R)
    setup_fail = [r for r in R if r.get("stage") not in (None, "done")]
    ran = [r for r in R if "truth_in_agent_env" in r]
    P = [r for r in ran if r["truth_in_agent_env"] == "pass"]
    V = [r for r in P if r.get("base_fails_in_agent_env")]
    n = len(V)
    print(f"A attempted {A}; setup failures (clone/base unavailable) {len(setup_fail)}; ran {len(ran)}; agent errors {sum(bool(r.get('is_error')) for r in ran)}; cost ${sum(r.get('cost_usd') or 0 for r in R):.2f}")
    print(f"P agent's tests pass in its own environment {len(P)}; V valid (also fail on the baseline without the changes) {n}; trivial {len(P) - n}; not solved {len(ran) - len(P)}")
    for label, k in (("E_repo (zero-config)", "ladder"), ("E_capture (fuller, 3 GB)", "freeze_replay"), ("E_recipe scoped", "recipe_scoped_replay")):
        p = sum(res(r, k) == "pass" for r in V)
        itt = sum(res(r, k) == "pass" for r in R)
        pp = sum(res(r, k) == "pass" for r in P)
        print(f"{label:26s} reproduced / V {p}/{n} = {100 * p // max(1, n)}% {wil(p, n)} | / P {pp}/{len(P)} | / A (intention to treat) {itt}/{A} | outcomes on V {dict(Counter(res(r, k) or 'none' for r in V))}")
    b = sum(res(r, "freeze_replay") == "pass" and res(r, "ladder") != "pass" for r in V)
    c = sum(res(r, "ladder") == "pass" and res(r, "freeze_replay") != "pass" for r in V)
    both = sum(res(r, "ladder") == "pass" and res(r, "freeze_replay") == "pass" for r in V)
    print(f"paired on V: both {both}, capture-only (b) {b}, repo-only (c), {c}, neither {n - both - b - c}; net paired lead (b-c)/V = {100 * (b - c) / max(1, n):.0f} points")
    rc = 100 * sum(res(r, "freeze_replay") == "pass" for r in V) / max(1, n)
    lead = 100 * (b - c) / max(1, n)
    rr = 100 * sum(res(r, "ladder") == "pass" for r in V) / max(1, n)
    if n < 20:
        verdict = "UNDERPOWERED (fewer than 20 valid runs): no reading"
    elif rc >= 70 and lead >= 15:
        verdict = "SUPPORTED"
    elif rc <= rr + 10 or lead < 10:
        verdict = "NO INCREMENTAL VALUE (stop)"
    else:
        verdict = "INCONCLUSIVE"
    print("pre-registered reading:", verdict)
    print("capture outcomes on V, distinct classes:", dict(Counter("pass" if res(r, "freeze_replay") == "pass" else why(r) for r in V)))


if __name__ == "__main__":
    main()
