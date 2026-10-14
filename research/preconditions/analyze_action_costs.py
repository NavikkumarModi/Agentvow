"""Policy simulation over the measured per-action costs (docs/research/forecast_grounding/ACTION_COST_PLAN.md): decision rules are fixed in that file.
Usage: python3 research/preconditions/analyze_action_costs.py"""
import json
import statistics as st
from pathlib import Path

D = Path(__file__).resolve().parents[2] / "data" / "preconditions"


def rows():
    return [json.loads(l) for l in (D / "b6_action_costs.jsonl").read_text().splitlines() if l.strip()]


def policy(rec, order):
    """-> (seconds, g1_answer, contexts_run). G1 answer: 'reproduced' if any tried context passes, else 'not shown' (after trying every context the policy allows)."""
    ctx = {"repo": rec["repo_context"], "capture": rec["capture_context"]}
    secs, ran = 0.0, []
    for name in order:
        c = ctx[name]; secs += c["seconds"]; ran.append(name)
        if c["result"] == "pass":
            return secs, "reproduced", ran
    return secs, "not shown", ran


def summarize(label, rs):
    n = len(rs)
    if not n:
        print(f"{label}: no rows"); return {}
    out = {}
    pols = {"repository-first": ("repo", "capture"), "capture-first": ("capture", "repo"), "always-both": ("repo", "capture")}
    both_answer = [("reproduced" if any(r[k]["result"] == "pass" for k in ("repo_context", "capture_context")) else "not shown") for r in rs]
    print(f"\n{label} (n = {n})")
    for name, order in pols.items():
        if name == "always-both":
            secs = [r["repo_context"]["seconds"] + r["capture_context"]["seconds"] for r in rs]; ans = both_answer; g2 = n
        else:
            res = [policy(r, order) for r in rs]; secs = [x[0] for x in res]; ans = [x[1] for x in res]
            g2 = sum(1 for x in res if len(x[2]) == 2)
        wrong = sum(a != b for a, b in zip(ans, both_answer))
        out[name] = {"median": st.median(secs), "mean": st.mean(secs), "total": sum(secs), "g1_differs_from_always_both": wrong, "g2_credited": g2}
        print(f"  {name:17s} median {st.median(secs):7.1f}s  mean {st.mean(secs):7.1f}s  total {sum(secs):8.0f}s  G1 answer differs from always-both in {wrong}/{n}; G2 (both contexts) credited in {g2}/{n}")
    base = out["repository-first"]["median"]; cf = out["capture-first"]["median"]
    out["median_saving_capture_first_vs_repository_first"] = (base - cf) / base if base else 0.0
    print(f"  median saving, capture-first vs repository-first: {100 * out['median_saving_capture_first_vs_repository_first']:.0f}%")
    return out


def main():
    R = rows()
    measured = [r for r in R if "repo_context" in r and "capture_context" in r]
    skipped = [r for r in R if r.get("skipped")]
    print(f"attempts with a saved run directory {len(R)}; measured both contexts {len(measured)} ({100 * len(measured) // max(1, len(R))}% of those; 39 are measurable at most, 40 attempted); skipped {len(skipped)}: {[ (r['repo'].split('/')[1], r['skipped'][:50]) for r in skipped][:6]}")
    for k in ("repo_context", "capture_context"):
        s = [r[k]["seconds"] for r in measured]
        print(f"{k}: seconds min {min(s):.0f} median {st.median(s):.0f} max {max(s):.0f}; results {dict(__import__('collections').Counter(r[k]['result'] for r in measured))}")
    agree = sum(1 for r in measured if r["registered"]["repo"] == r["repo_context"]["result"]) , sum(1 for r in measured if r["registered"]["capture"] == r["capture_context"]["result"])
    print(f"re-measurement agrees with the registered B6 result: repo {agree[0]}/{len(measured)}, capture {agree[1]}/{len(measured)} (package indexes and the day differ, so this is a drift check, not an error check)")
    a = summarize("ALL measurable attempts (operational cost)", measured)
    v = summarize("the VALID runs only (the study's comparison population)", [r for r in measured if r.get("valid")])
    cover = len(measured) / 39
    sav = a.get("median_saving_capture_first_vs_repository_first", 0)
    print("\nDECISION (rules fixed in ACTION_COST_PLAN.md):")
    if cover < 0.8:
        print(f"  coverage {100 * cover:.0f}% < 80%: INSTRUMENT MORE (timings missing for too many attempts)")
    elif sav >= 0.25 and a["capture-first"]["g1_differs_from_always_both"] == 0 and a["repository-first"]["g1_differs_from_always_both"] == 0:
        print(f"  median saving {100 * sav:.0f}% >= 25% with no change in the G1 answer: PROCEED to a pre-registered ordering study (the saving counts only for G1, not G2)")
    elif sav < 0.10:
        print(f"  median saving {100 * sav:.0f}% < 10%: STOP pursuing adaptive ordering for now")
    else:
        print(f"  median saving {100 * sav:.0f}% between 10% and 25% (or the G1 answer changed): INCONCLUSIVE")


if __name__ == "__main__":
    main()
