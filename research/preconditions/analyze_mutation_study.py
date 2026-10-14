"""Analysis of the mutation study per docs/research/forecast_grounding/MUTATION_STUDY_PREREG.md sections 4-5 (rules fixed there). Usage: python3 research/preconditions/analyze_mutation_study.py"""
import json
import random
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

D = Path(__file__).resolve().parents[2] / "data" / "preconditions"
SEED = 20261015


def main():
    R = [json.loads(l) for l in (D / "mutation_study.jsonl").read_text().splitlines() if l.strip()]
    print(f"run records {len(R)} (valid runs of B3-B6 considered)")
    ran = [r for r in R if not r.get("excluded")]
    print("by stage:", {s: (sum(1 for r in R if r['stage'] == s), sum(1 for r in ran if r['stage'] == s)) for s in ("stageb3", "stageb4", "stageb5", "stageb6")}, "(considered, ran)")
    reasons = Counter(("untracked files" if "untracked" in r["excluded"] else "no candidate mutants" if "no candidate" in r["excluded"] else "baseline: " + r["excluded"].split(";")[0][:70]) for r in R if r.get("excluded"))
    print("excluded:", dict(reasons))
    M = []
    for r in ran:
        for m in r.get("mutants") or []:
            M.append({**m, "stage": r["stage"], "repo": r["repo"], "pr": r["pr"], "cov_ok": not r.get("coverage_note")})
    print(f"runs that ran {len(ran)}; with >=1 sampled mutant {sum(1 for r in ran if r.get('mutants'))}; enumerated {sum(r.get('candidates_enumerated', 0) for r in ran)}; sampled {len(M)}")
    print("outcomes:", dict(Counter(m["outcome"] for m in M)))
    valid = [m for m in M if m["outcome"] in ("killed", "survived", "timeout")]
    nocov = [m for m in valid if not m["cov_ok"]]
    valid = [m for m in valid if m["cov_ok"]]
    print(f"valid mutants (killed/survived/timeout) with executed-line labels: {len(valid)}; without labels (coverage unavailable) {len(nocov)}")
    Rr = [m for m in valid if m["executed"]]
    S = [m for m in Rr if m["outcome"] == "survived"]
    Un = [m for m in valid if not m["executed"]]
    print(f"R (valid, executed) = {len(Rr)} from {len({(m['stage'], m['repo'], m['pr']) for m in Rr})} runs in {len({m['repo'] for m in Rr})} repositories; S (survived) = {len(S)}; timeouts among R: {sum(m['outcome'] == 'timeout' for m in Rr)}")
    print(f"S/R = {100 * len(S) / max(1, len(Rr)):.1f}%")
    print(f"not executed: {len(Un)} valid mutants, survived {sum(m['outcome'] == 'survived' for m in Un)}; killed-though-not-executed {sum(m['outcome'] != 'survived' for m in Un)} (should be ~0)")
    allS = [m for m in valid if m["outcome"] == "survived"]
    print(f"survivors total {len(allS)}: on executed lines {len(S)} ({100 * len(S) / max(1, len(allS)):.0f}%, information beyond coverage), on unexecuted lines {len(allS) - len(S)}")
    by = defaultdict(list)
    for m in Rr:
        by[m["repo"]].append(m["outcome"] == "survived")
    repos = list(by)
    rng = random.Random(SEED)
    rates = []
    for _ in range(20000):
        smp = [x for rp in (rng.choice(repos) for _ in repos) for x in by[rp]]
        rates.append(sum(smp) / len(smp))
    rates.sort()
    lo, hi = rates[int(.025 * len(rates))], rates[int(.975 * len(rates))]
    print(f"repository-level cluster bootstrap (20,000 resamples of {len(repos)} repositories): S/R 95% interval {100 * lo:.1f}-{100 * hi:.1f}%")
    loo = [(sum(x for rp2 in repos if rp2 != rp for x in by[rp2]) / sum(len(by[rp2]) for rp2 in repos if rp2 != rp), rp) for rp in repos]
    print(f"leave-one-repository-out S/R range {100 * min(loo)[0]:.1f}-{100 * max(loo)[0]:.1f}% (lowest when leaving out {min(loo)[1]}, highest {max(loo)[1]})")
    print("S by repository:", dict(Counter(m["repo"].split('/')[1] for m in S).most_common(8)))
    print("S by operator family:", dict(Counter(m["operator"].split('/')[-1].split('_')[0] for m in S).most_common(8)), "| R by family:", dict(Counter(m["operator"].split('/')[-1].split('_')[0] for m in Rr).most_common(8)))
    ms = [r["mutation_s"] for r in ran if r.get("mutation_s") is not None]
    ratio = [r["mutation_s"] / max(r["baseline_s"], 0.1) for r in ran if r.get("mutation_s") is not None and r.get("baseline_s") is not None]
    print(f"mutation-step time per run: median {st.median(ms):.0f}s, max {max(ms):.0f}s; ratio to one baseline test run: median {st.median(ratio):.0f}x; runs hitting the time cap: {sum(1 for r in ran if r.get('time_cap_hit'))}")
    print("per-stage S/R:", {s: f"{sum(m['outcome'] == 'survived' for m in Rr if m['stage'] == s)}/{sum(1 for m in Rr if m['stage'] == s)}" for s in ("stageb3", "stageb4", "stageb5", "stageb6")})
    json.dump({"survivors_executed": S}, open(D / "mutation_survivors_executed.json", "w"), indent=1)
    sup = len(Rr) >= 100 and len({(m['stage'], m['repo'], m['pr']) for m in Rr}) >= 10 and len({m['repo'] for m in Rr}) >= 8
    print("\nDATA SUFFICIENCY (>=100 valid executed mutants, >=10 runs, >=8 repositories):", "met" if sup else "NOT met")


if __name__ == "__main__":
    main()
