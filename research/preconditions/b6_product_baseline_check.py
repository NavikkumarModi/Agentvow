"""0.3.0 item 1 check: the product's baseline (agentvow/baseline.py, no PyYAML) must derive the same setup as the research baseline used for E3 (strong_baseline.py), on the 22 valid B6 tasks at their base commits.
Where the derived setup and environment are identical, the registered E3 replay result stands (same inputs; same-day determinism only); where they differ, the difference is printed and the task is replayed.
Usage: python3 research/preconditions/b6_product_baseline_check.py"""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["CAPTURE"] = "1"; os.environ["B6"] = "1"
import stageb_run as sb  # noqa: E402
import strong_baseline as sbl  # noqa: E402
from agentvow import baseline, recipe as recipe_mod  # noqa: E402

D = ROOT / "data" / "preconditions"


def main():
    rows = [json.loads(l) for l in (D / "stageb6_results.jsonl").read_text().splitlines()]
    tasks = {(j["repo"], j["pr"]): j for j in map(json.loads, (D / "stageb6_tasks.jsonl").read_text().splitlines())}
    valid = [r for r in rows if r.get("truth_in_agent_env") == "pass" and r.get("base_fails_in_agent_env")]
    same = diff = 0
    out = []
    for r in valid:
        c = tasks[(r["repo"], r["pr"])]
        tmp = Path(tempfile.mkdtemp(prefix="pbc_"))
        try:
            repo, _ = sb.prepare(c, tmp)
            if repo is None:
                print(f"{r['repo']}#{r['pr']}: base checkout failed"); continue
            old, _ = sbl.derive_strong(repo, c["target_files"])
            s, e, notes = baseline.derive(repo)
            old_s = [" ".join(x) for x in recipe_mod.parse({"schema": recipe_mod.SCHEMA, "setup": old["setup"], "test": "python -m pytest -q"}).setup]
            new_s = [" ".join(x) for x in recipe_mod.parse({"schema": recipe_mod.SCHEMA, "setup": s, "test": "python -m pytest -q"}).setup]
            ok = old_s == new_s and old["env"] == e
            same += ok; diff += not ok
            out.append({"run": f"{r['repo']}#{r['pr']}", "same": ok, "research_setup": old["setup"], "product_setup": s, "research_env": old["env"], "product_env": e})
            print(f"{r['repo']}#{r['pr']}: {'identical' if ok else 'DIFFERENT'} ({len(s)} setup lines)", flush=True)
            if not ok:
                print("   research:", old["setup"], old["env"]); print("   product :", s, e)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    (D / "stageb6_product_baseline_check.json").write_text(json.dumps(out, indent=1))
    print(f"identical derivations {same}, different {diff}, of {same + diff}")


if __name__ == "__main__":
    main()
