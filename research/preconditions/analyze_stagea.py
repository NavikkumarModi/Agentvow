"""Stage A analysis: acceptance criteria and descriptive outputs (docs/research/forecast_grounding/STAGE_A.md)."""
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data" / "preconditions"
sys.path.insert(0, str(ROOT))


def res(r, k):
    return ((r.get(k) or {}).get("evidence") or {}).get("result")


def main():
    runs = [json.loads(l) for l in (D / "stagea_results.jsonl").read_text().splitlines() if l.strip()]
    abl = {j["run"]: j for j in map(json.loads, (D / "stagea_ablation.jsonl").read_text().splitlines())}
    print(f"{len(runs)} runs, cost ${sum(r.get('cost_usd') or 0 for r in runs):.2f}, agent errors {sum(bool(r.get('is_error')) for r in runs)}")
    # criterion 2: artifacts
    need = ["meta.json", "patch.diff", "commands.json", "final.txt", "pipfreeze_agent.txt", "pyversion.txt", "record.json", "repo"]
    miss = [(Path(r["run_dir"]).name, f) for r in runs for f in need if not (Path(r["run_dir"]) / f).exists()]
    print(f"\n[criterion 2] artifact completeness: {len(runs) * len(need) - len(miss)}/{len(runs) * len(need)} files present; missing {miss[:5]}")
    # criterion 1: determinism
    rows = [abl[Path(r["run_dir"]).name] for r in runs if Path(r["run_dir"]).name in abl and abl[Path(r["run_dir"]).name].get("full")]
    agree = [j["full"][0]["result"] == j["full"][1]["result"] for j in rows]
    print(f"[criterion 1] replay determinism: {sum(agree)}/{len(agree)} runs give the same result class twice" + (" -> disagreements: " + str([j['run'] for j, a in zip(rows, agree) if not a]) if not all(agree) else ""))
    # criterion 3: recipes
    rej = [(r["task"], r["recipe_error"]) for r in runs if r.get("recipe_error")]
    print(f"[criterion 3] recipes written {sum(r['recipe_written'] for r in runs)}/{len(runs)}; rejected by the validator: {len(rej)} {rej}")
    # criterion 4: integrity guard
    guard = sum("changed existing repository files" in (((r.get('recipe_replay') or {}).get('evidence') or {}).get('summary') or "") for r in runs)
    print(f"[criterion 4] replays refused because a prepare step changed existing files: {guard}")
    # profile
    print("\n== Accountability profile per run (truth in agent env | zero-config replay | recipe replay)")
    prof = Counter((r["truth_in_agent_env"], res(r, "ladder"), res(r, "recipe_replay") if r.get("recipe_replay") else "no replay") for r in runs)
    for k, v in prof.most_common():
        print(f"  {v:2d}  truth={k[0]:4} zero-config={str(k[1]):12} recipe={k[2]}")
    ladder_ok = sum(res(r, "ladder") == "pass" for r in runs)
    rec_ok = sum(res(r, "recipe_replay") == "pass" for r in runs)
    print(f"  zero-config reproduces {ladder_ok}/{len(runs)}; recipe reproduces {rec_ok}/{len(runs)}; both {sum(res(r,'ladder')=='pass' and res(r,'recipe_replay')=='pass' for r in runs)}; "
          f"recipe only {sum(res(r,'ladder')!='pass' and res(r,'recipe_replay')=='pass' for r in runs)}")
    # necessity
    nec = pad = 0
    pad_items, nec_items = [], []
    for j in abl.values():
        for a in j.get("ablations", []):
            kind = a["label"].split("[")[0].split(" ")[0]
            (pad_items if a["result"] == "pass" else nec_items).append((j["task"][:3], a["label"][:40]))
    print(f"\n== Necessity (declared elements removed one at a time, among recipes that replayed): necessary {len(nec_items)}, padding {len(pad_items)}")
    c = Counter(re.sub(r"^\w+\[\d\] ", "", l)[:32] for _, l in pad_items)
    print("  padding examples:", c.most_common(5))
    print("\n== Replay time (s): full recipe median", sorted(j["full"][0]["seconds"] for j in rows)[len(rows) // 2] if rows else "n/a",
          "| cost per run mean $%.3f" % (sum(r.get('cost_usd') or 0 for r in runs) / len(runs)))
    print("\n== Per-run")
    for r in sorted(runs, key=lambda x: (x["task"], x["rep"])):
        a = abl.get(Path(r["run_dir"]).name, {})
        print(f"  {r['task'][:24]:24} rep{r['rep']} truth={r['truth_in_agent_env']:4} zero-config={str(res(r,'ladder')):12} recipe={str(res(r,'recipe_replay') if r.get('recipe_replay') else r.get('recipe_error','-'))[:14]:14} "
              f"full2x={[x['result'] for x in a.get('full', [])]} necessary={sum(x['result']!='pass' for x in a.get('ablations', []))} padding={sum(x['result']=='pass' for x in a.get('ablations', []))}")


if __name__ == "__main__":
    main()
