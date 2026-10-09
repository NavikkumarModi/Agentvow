"""Stage A ablation + determinism check (docs/research/forecast_grounding/STAGE_A.md).
For every saved run with a valid recipe: replay the full recipe twice (determinism), then once per declared element removed.
Usage: python3 research/preconditions/ablate.py [run_dir ...]  -> data/preconditions/stagea_ablation.jsonl (resumable)"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from agentvow import recipe as recipe_mod  # noqa: E402

D = ROOT / "data" / "preconditions"
OUT = D / "stagea_ablation.jsonl"


def replay(run_dir: Path, base_sha: str, rec_data: dict, label: str):
    tmp = Path(tempfile.mkdtemp(prefix="ablate_"))
    try:
        repo = tmp / "r"
        shutil.copytree(run_dir / "repo", repo, symlinks=True)
        rf = tmp / "recipe.json"
        rf.write_text(json.dumps(rec_data))
        msg = tmp / "m.txt"; msg.write_text("All tests pass.")
        env = {**os.environ, "AGENTVOW_HOME": str(D / "agentvow_home")}
        env.pop("PYTHONPATH", None)
        t0 = time.time()
        p = subprocess.run([sys.executable, "-m", "agentvow.cli", "check", "--repo", str(repo), "--base", base_sha, "--recipe", str(rf),
                            "--transcript", str(msg), "--json"], cwd=ROOT, capture_output=True, text=True, env=env, timeout=1500)
        result, summary = None, ""
        ev = repo / ".agentvow" / "evidence"
        for f in sorted(ev.glob("testrun_*.json")) if ev.exists() else []:
            r = json.loads(f.read_text()); result, summary = r.get("result"), (r.get("summary") or "")[:120]
        return {"label": label, "result": result, "summary": summary, "seconds": round(time.time() - t0), "exit": p.returncode}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def variants(data: dict):
    out = []
    for i, s in enumerate(data.get("setup", [])):
        out.append((f"setup[{i}] {s}", {**data, "setup": [x for j, x in enumerate(data["setup"]) if j != i]}))
    for i, s in enumerate(data.get("prepare", [])):
        out.append((f"prepare[{i}] {s}", {**data, "prepare": [x for j, x in enumerate(data["prepare"]) if j != i]}))
    for k in data.get("env", {}):
        out.append((f"env {k}", {**data, "env": {a: b for a, b in data["env"].items() if a != k}}))
    return out


def main(only=None):
    done = {json.loads(l)["run"] for l in OUT.read_text().splitlines()} if OUT.exists() else set()
    dirs = [Path(a) for a in only] if only else sorted((D / "runs").iterdir())
    for rd in dirs:
        if rd.name in done or not (rd / "meta.json").exists():
            continue
        meta = json.loads((rd / "meta.json").read_text())
        rf = rd / "repo" / ".agentvow-recipe.json"
        row = {"run": rd.name, "task": meta["task"], "rep": meta.get("rep"), "recipe": None}
        try:
            data = json.loads(rf.read_text())
            recipe_mod.parse(data)    # same validator as the verdict path
            row["recipe"] = data
        except Exception as e:
            row["recipe_rejected"] = str(e)[:150]
            with OUT.open("a") as fh:
                fh.write(json.dumps(row) + "\n")
            print(f"{rd.name}: recipe rejected ({row['recipe_rejected'][:60]})", flush=True)
            continue
        row["full"] = [replay(rd, meta["base_sha"], data, "full-1"), replay(rd, meta["base_sha"], data, "full-2")]
        if row["full"][0]["result"] == "pass":
            row["ablations"] = [replay(rd, meta["base_sha"], v, lab) for lab, v in variants(data)]
        with OUT.open("a") as fh:
            fh.write(json.dumps(row) + "\n")
        print(f"{rd.name}: full={[x['result'] for x in row['full']]} ablations={[(a['label'][:22], a['result']) for a in row.get('ablations', [])]}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:] or None)
