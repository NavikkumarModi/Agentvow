"""Stage B1 (feasibility) analysis. Descriptive only: N < 40, the S2 stratum has 2 tasks (docs/research/forecast_grounding/STAGE_B.md section 11)."""
import json
import math
import sys
from collections import Counter
from pathlib import Path

D = Path(__file__).resolve().parents[2] / "data" / "preconditions"


def wilson(k, n, z=1.96):
    if not n:
        return (0, 0)
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def fmt(k, n):
    lo, hi = wilson(k, n)
    return f"{k}/{n}" + (f" = {100 * k / n:.0f}% [{100 * lo:.0f}, {100 * hi:.0f}]" if n else "")


def res(r, k):
    return ((r.get(k) or {}).get("evidence") or {}).get("result")


def main():
    rows = [json.loads(l) for l in (D / "stageb_results.jsonl").read_text().splitlines() if l.strip()]
    done = [r for r in rows if r.get("stage") == "done" or "truth_in_agent_env" in r]
    bad = [r for r in rows if r not in done]
    print(f"{len(rows)} runs ({len(done)} completed, {len(bad)} failed to set up: {[ (r['repo'], r.get('stage')) for r in bad]}); repos {len({r['repo'] for r in done})}; cost ${sum(r.get('cost_usd') or 0 for r in rows):.2f}; "
          f"agent errors {sum(bool(r.get('is_error')) for r in done)}; median agent seconds {sorted(r.get('agent_seconds', 0) for r in done)[len(done) // 2]}")
    print("strata:", dict(Counter(r["stratum"] for r in done)))
    n = len(done)
    print(f"\n== Agent side: claim made {fmt(sum(r['claim_made'] for r in done), n)} | truth in agent env {fmt(sum(r['truth_in_agent_env']=='pass' for r in done), n)} | "
          f"given tests edited {sum(r['tests_modified'] for r in done)} | recipe written {sum(r['recipe_written'] for r in done)}/{n} | recipe rejected {sum(bool(r.get('recipe_error')) for r in done)}")
    print("\n== Reproduction of the agent's result (target tests pass) by context")
    for label, key in (("repository-only replay (zero-config)", "ladder"), ("agent's recipe replay", "recipe_replay"), ("agent's pip-freeze replay (control)", "freeze_replay")):
        base = [r for r in done if r["truth_in_agent_env"] == "pass" and (key != "recipe_replay" or r.get("recipe_replay"))]
        print(f"  {label:38} {fmt(sum(res(r, key) == 'pass' for r in base), len(base))}")
    for s in ("S1", "S2"):
        g = [r for r in done if r["stratum"] == s]
        print(f"  [{s}] repo {fmt(sum(res(r,'ladder')=='pass' for r in g), len(g))} | recipe {fmt(sum(res(r,'recipe_replay')=='pass' for r in g), len(g))} | freeze {fmt(sum(res(r,'freeze_replay')=='pass' for r in g), len(g))}")
    print("\n== Accountability profile (truth | repo-only | recipe | freeze)")
    for k, v in Counter((r["truth_in_agent_env"], res(r, "ladder"), res(r, "recipe_replay") if r.get("recipe_replay") else "no-recipe-replay", res(r, "freeze_replay")) for r in done).most_common():
        print(f"  {v:2d}  {k}")
    both = sum(res(r, "ladder") == "pass" and res(r, "recipe_replay") == "pass" for r in done)
    rec_only = [r for r in done if res(r, "ladder") != "pass" and res(r, "recipe_replay") == "pass"]
    rep_only = [r for r in done if res(r, "ladder") == "pass" and res(r, "recipe_replay") != "pass"]
    print(f"  recipe-only reproduces: {len(rec_only)} | repo-only reproduces: {len(rep_only)} | both: {both}  (paired discordance; descriptive)")
    det = [r for r in done if r.get("recipe_replay_2")]
    print(f"\n== Recipe replay determinism (twice): {fmt(sum(res(r,'recipe_replay') == res(r,'recipe_replay_2') for r in det), len(det))}")
    print("\n== Where the recipe replay did not reproduce")
    for r in done:
        if r["truth_in_agent_env"] == "pass" and res(r, "recipe_replay") != "pass":
            print(f"  {r['repo']}#{r['pr']} [{r['stratum']}] recipe={res(r,'recipe_replay')} rejected={r.get('recipe_error')} repo-only={res(r,'ladder')} freeze={res(r,'freeze_replay')} :: {((r.get('recipe_replay') or {}).get('evidence') or {}).get('summary','')[:90]}")
    print("\n== Hidden state (session audit undeclared env/system/installs):", sum(len(r['audit']['undeclared']) > 0 for r in done), "runs with any;",
          "| noisy 'ambient imports' measure (transitive deps): runs with any", sum(len(r.get('ambient_undeclared', [])) > 0 for r in done))
    print("\n== Per-run")
    for r in sorted(done, key=lambda x: (x["stratum"], x["repo"])):
        print(f"  {r['repo'][:34]:34}#{r['pr']:<5} {r['stratum']} truth={r['truth_in_agent_env']:4} repo={str(res(r,'ladder')):12} recipe={str(res(r,'recipe_replay')):12} freeze={str(res(r,'freeze_replay')):12} cost=${r.get('cost_usd') or 0:.2f}")


if __name__ == "__main__":
    main()
