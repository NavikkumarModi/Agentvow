"""Stage B3 task selection: candidates rejected by Stage B0 for lack of a reconstructable environment, seed 2029, at most 2 per repository, up to 24.
Usage: python3 research/preconditions/stageb3_select.py -> data/preconditions/stageb3_tasks.jsonl"""
import json
import random
from pathlib import Path

D = Path(__file__).resolve().parents[2] / "data" / "preconditions"
rows = [json.loads(l) for l in (D / "stageb_validated.jsonl").read_text().splitlines()]
pool = [r for r in rows if not r["valid"] and r.get("why") in ("no_s1_and_no_ci_recipe", "no_reference_environment") and r.get("target_files")]
random.Random(2029).shuffle(pool)
per, out = {}, []
for r in pool:
    if per.get(r["repo"], 0) >= 2:
        continue
    per[r["repo"]] = per.get(r["repo"], 0) + 1
    out.append({**r, "stratum": "X"})
    if len(out) >= 24:
        break
(D / "stageb3_tasks.jsonl").write_text("\n".join(json.dumps(o) for o in out) + "\n")
print(len(out), "tasks in", len({o["repo"] for o in out}), "repositories")
