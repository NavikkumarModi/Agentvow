"""Stage B4 task selection: the Stage B0 candidates without a reconstructable environment that Stage B3 did NOT use, seed 2030, at most 2 per repository, up to 24.
Usage: python3 research/preconditions/stageb4_select.py -> data/preconditions/stageb4_tasks.jsonl"""
import json
import random
from pathlib import Path

D = Path(__file__).resolve().parents[2] / "data" / "preconditions"
used = {(j["repo"], j["pr"]) for j in map(json.loads, (D / "stageb3_tasks.jsonl").read_text().splitlines())}
rows = [json.loads(l) for l in (D / "stageb_validated.jsonl").read_text().splitlines()]
pool = [r for r in rows if not r["valid"] and r.get("why") in ("no_s1_and_no_ci_recipe", "no_reference_environment") and r.get("target_files") and (r["repo"], r["pr"]) not in used]
random.Random(2030).shuffle(pool)
per, out = {}, []
for r in pool:
    if per.get(r["repo"], 0) >= 2:
        continue
    per[r["repo"]] = per.get(r["repo"], 0) + 1
    out.append({**r, "stratum": "X"})
    if len(out) >= 24:
        break
(D / "stageb4_tasks.jsonl").write_text("\n".join(json.dumps(o) for o in out) + "\n")
print(len(out), "tasks in", len({o["repo"] for o in out}), "repositories (pool", len(pool), ")")
