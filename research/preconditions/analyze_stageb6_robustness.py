"""Stage B6 robustness analyses (post-hoc, the open items of the paper's final adversarial review): (a) a reproduction must have >= 1 executed passing test; (b) repository-level
cluster bootstrap and leave-one-repository-out, and the repository spread of the capture-only runs. Descriptive; N is small. Usage: python3 research/preconditions/analyze_stageb6_robustness.py"""
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

D = Path(__file__).resolve().parents[2] / "data" / "preconditions"


def ev(r, k):
    return (r.get(k) or {}).get("evidence") or {}


def reproduced(r, k, strict):
    e = ev(r, k)
    return e.get("result") == "pass" and (not strict or (e.get("counts") or {}).get("passed", 0) >= 1)


def wilson(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return round(100 * (c - h) / d), round(100 * (c + h) / d)


def main():
    R = [json.loads(l) for l in (D / "stageb6_results.jsonl").read_text().splitlines() if l.strip()]
    V = [r for r in R if r.get("truth_in_agent_env") == "pass" and r.get("base_fails_in_agent_env")]
    n = len(V)
    print(f"valid runs {n} in {len({r['repo'] for r in V})} repositories; repository sizes {sorted(Counter(r['repo'] for r in V).values(), reverse=True)}")
    for strict in (False, True):
        c = [reproduced(r, "freeze_replay", strict) for r in V]; t = [reproduced(r, "ladder", strict) for r in V]
        b = sum(x and not y for x, y in zip(c, t)); cc = sum(y and not x for x, y in zip(c, t)); both = sum(x and y for x, y in zip(c, t))
        print(f"\n{'STRICT (>= 1 executed passing test)' if strict else 'as registered (result == pass)'}: capture {sum(c)}/{n} {wilson(sum(c), n)} | reconstruction {sum(t)}/{n} {wilson(sum(t), n)} | both {both}, capture-only {b}, reconstruction-only {cc}, neither {n - both - b - cc} | lead {100 * (b - cc) / n:.0f} points")
    odd = [(r["repo"], r["pr"], ev(r, k).get("counts"), ev(r, k).get("summary", "")[:60]) for r in V for k in ("ladder", "freeze_replay") if ev(r, k).get("result") == "pass" and (ev(r, k).get("counts") or {}).get("passed", 0) < 1]
    print("passes without an executed passing test:", odd)
    c = [reproduced(r, "freeze_replay", True) for r in V]; t = [reproduced(r, "ladder", True) for r in V]
    by = defaultdict(list)
    for r, x, y in zip(V, c, t):
        by[r["repo"]].append((x, y))
    only = Counter(r["repo"] for r, x, y in zip(V, c, t) if x and not y)
    print(f"\ncapture-only runs by repository: {dict(only)} ({len(only)} repositories)")
    pos = sum(1 for k, v in by.items() if sum(x and not y for x, y in v) > sum(y and not x for x, y in v)); neg = sum(1 for k, v in by.items() if sum(y and not x for x, y in v) > sum(x and not y for x, y in v))
    print(f"repositories with a net capture advantage: {pos}; net reconstruction advantage: {neg}; of {len(by)}")
    rng = random.Random(20261014); repos = list(by); caps, recs, leads = [], [], []
    for _ in range(20000):
        sample = [rng.choice(repos) for _ in repos]
        runs = [p for k in sample for p in by[k]]
        m = len(runs)
        cap = sum(x for x, _ in runs) / m; rec = sum(y for _, y in runs) / m
        caps.append(cap); recs.append(rec); leads.append(sum(x and not y for x, y in runs) / m - sum(y and not x for x, y in runs) / m)
    pc = lambda a, q: sorted(a)[int(q * len(a))]
    print(f"\nrepository-level cluster bootstrap (20000 resamples of {len(repos)} repositories, seed fixed): capture rate 95% interval {100 * pc(caps, .025):.0f}-{100 * pc(caps, .975):.0f}%, reconstruction {100 * pc(recs, .025):.0f}-{100 * pc(recs, .975):.0f}%, net lead {100 * pc(leads, .025):.0f}-{100 * pc(leads, .975):.0f} points; resamples with lead <= 0: {100 * sum(l <= 0 for l in leads) / len(leads):.2f}%")
    out = []
    for k in repos:
        runs = [p for kk in repos if kk != k for p in by[kk]]; m = len(runs)
        out.append((sum(x for x, _ in runs) / m, (sum(x and not y for x, y in runs) - sum(y and not x for x, y in runs)) / m, k))
    print(f"leave-one-repository-out: capture rate {100 * min(o[0] for o in out):.0f}-{100 * max(o[0] for o in out):.0f}%, net lead {100 * min(o[1] for o in out):.0f}-{100 * max(o[1] for o in out):.0f} points (smallest lead when leaving out {min(out, key=lambda o: o[1])[2]})")
    print("\nauthor family of valid PRs:", dict(Counter(r.get("agent_of_pr") for r in V)))


if __name__ == "__main__":
    main()
