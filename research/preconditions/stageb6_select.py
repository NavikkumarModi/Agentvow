"""Stage B6 task selection: ALL structural candidates not used in B1-B5, drawn at random (seed 2032, at most 2 per repository, 40 tasks) WITHOUT looking at any earlier
zero-config / reconstruction result. Target tests = the PR's Python test files. Usage: python3 research/preconditions/stageb6_select.py -> data/preconditions/stageb6_tasks.jsonl"""
import json
import random
from pathlib import Path

D = Path(__file__).resolve().parents[2] / "data" / "preconditions"
used = set()
for f in ("stageb_results", "stageb3_results", "stageb4_results", "stageb5_results"):
    used |= {(j["repo"], j["pr"]) for j in map(json.loads, (D / f"{f}.jsonl").read_text().splitlines())}
cands = [j for j in map(json.loads, (D / "stageb_cands.jsonl").read_text().splitlines()) if j.get("ok") and (j["repo"], j["pr"]) not in used]
pool = [c for c in cands if [t for t in c["test_files"] if t.endswith(".py")]]
random.Random(2032).shuffle(pool)
per, out = {}, []
for c in pool:
    if per.get(c["repo"], 0) >= 2:
        continue
    per[c["repo"]] = per.get(c["repo"], 0) + 1
    out.append({**c, "target_files": [t for t in c["test_files"] if t.endswith(".py")], "stratum": "X", "valid": False})
    if len(out) >= 40:
        break
(D / "stageb6_tasks.jsonl").write_text("\n".join(json.dumps(o) for o in out) + "\n")
print(len(out), "tasks in", len({o["repo"] for o in out}), "repositories (pool", len(pool), ")")
