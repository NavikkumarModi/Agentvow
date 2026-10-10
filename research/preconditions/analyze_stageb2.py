"""Stage B2 (ambient) analysis: reproduces the registered table of docs/research/forecast_grounding/STAGE_B2_RESULTS.md from data/preconditions/stageb2_results.jsonl.
Descriptive only (N = 32). All contexts use the scoped target command; denominators are all 32 tasks (runs without a replay count as not reproduced)."""
import json
import math
import re
from collections import Counter
from pathlib import Path

D = Path(__file__).resolve().parents[2] / "data" / "preconditions"


def wilson(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def res(r, k):
    return ((r.get(k) or {}).get("evidence") or {}).get("result")


def main():
    rows = [json.loads(l) for l in (D / "stageb2_results.jsonl").read_text().splitlines() if l.strip()]
    n = len(rows)
    print(f"{n} runs, cost ${sum(r.get('cost_usd') or 0 for r in rows):.2f}; truth in agent env pass {sum(r.get('truth_in_agent_env') == 'pass' for r in rows)}; "
          f"agent-made claim {sum(r.get('statement') == 'agent' for r in rows)}; recipes written {sum(bool(r.get('recipe_written')) for r in rows)}; "
          f"recipe rejected {sum(bool(r.get('recipe_error')) for r in rows)}")
    for label, key in (("zero-config ladder", "ladder"), ("recipe, scoped command", "recipe_scoped_replay"), ("recipe, own command", "recipe_replay"), ("pip freeze control", "freeze_replay")):
        k = sum(res(r, key) == "pass" for r in rows); lo, hi = wilson(k, n)
        print(f"{label:28s} {k}/{n} = {100 * k / n:.0f}% [{100 * lo:.0f}, {100 * hi:.0f}]   {dict(Counter(res(r, key) or 'none' for r in rows))}")
    print("paired (ladder pass, scoped recipe pass):", dict(Counter((res(r, 'ladder') == 'pass', res(r, 'recipe_scoped_replay') == 'pass') for r in rows)))
    why = Counter()
    for r in rows:
        if res(r, "recipe_scoped_replay") != "pass":
            summ = json.dumps(r.get("recipe_scoped_replay") or {}) + (r.get("recipe_error") or "")
            why["rejected by the validator" if r.get("recipe_error") else "no module named pytest" if "No module named pytest" in summ else "no recipe replay" if not r.get("recipe_scoped_replay") else "other (" + (re.search(r"missing dependency[^:]*: (\w+)", summ).group(1) if re.search(r"missing dependency[^:]*: (\w+)", summ) else res(r, "recipe_scoped_replay")) + ")"] += 1
    print("why the scoped recipe replay did not pass:", dict(why))


if __name__ == "__main__":
    main()
