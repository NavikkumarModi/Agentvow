"""E3: replay the valid B6 runs under the strong reconstruction baseline (strong_baseline.py), from the saved patch, with the same scoped target command, sandbox and 3 GB size limit as the registered B6 replay.
Derivation uses the BASE commit checkout (before the agent's patch). Runs whose agent created untracked files that the patch lacks cannot be rebuilt and are recorded as not re-runnable.
Usage: python3 research/preconditions/b6_strong_baseline.py   (resumable; writes data/preconditions/stageb6_strong.jsonl)"""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["CAPTURE"] = "1"; os.environ["B6"] = "1"; os.environ["AGENTVOW_MAX_ENV_MB"] = "3072"
import stageb_run as sb  # noqa: E402
import run_pilot as rp  # noqa: E402
import strong_baseline as sbl  # noqa: E402
from agentvow import envsetup  # noqa: E402

D = ROOT / "data" / "preconditions"
PRODUCT = os.environ.get("PRODUCT") == "1"   # use the product baseline (agentvow/baseline.py) instead of the research one, only for runs whose derivation differs (stageb6_product_baseline_check.json)
OUT = D / ("stageb6_product_replay.jsonl" if PRODUCT else "stageb6_strong.jsonl")
envsetup.MAX_VENV = 3 * 1024**3


def main():
    rows = [json.loads(l) for l in (D / "stageb6_results.jsonl").read_text().splitlines()]
    tasks = {(j["repo"], j["pr"]): j for j in map(json.loads, (D / "stageb6_tasks.jsonl").read_text().splitlines())}
    valid = [r for r in rows if r.get("truth_in_agent_env") == "pass" and r.get("base_fails_in_agent_env")]
    done = {(j["repo"], j["pr"]) for j in map(json.loads, OUT.read_text().splitlines())} if OUT.exists() else set()
    only = None
    if PRODUCT:
        only = {x["run"] for x in json.loads((D / "stageb6_product_baseline_check.json").read_text()) if not x["same"]}
    for r in valid:
        key = (r["repo"], r["pr"])
        if key in done or (only is not None and f"{r['repo']}#{r['pr']}" not in only):
            continue
        if shutil.disk_usage(D).free < 3.5 * 1024**3:
            print("low disk; stopping", flush=True); return
        c = tasks[key]; rd = Path(r["run_dir"])
        old_capture = ((r.get("freeze_replay") or {}).get("evidence") or {}).get("result")
        old_ladder = ((r.get("ladder") or {}).get("evidence") or {}).get("result")
        rec = {"repo": r["repo"], "pr": r["pr"], "capture_b6": old_capture, "ladder_b6": old_ladder}
        status = (rd / "status.txt").read_text()
        unt = [l[3:] for l in status.splitlines() if l.startswith("??") and not l[3:].startswith((".agentvow", ".pytest_cache", "__pycache__")) and not l[3:].endswith((".pyc", ".json"))]
        if unt:
            rec["strong"] = "not_rerunnable"; rec["why"] = f"untracked files not in the patch: {unt[:2]}"
        else:
            tmp = Path(tempfile.mkdtemp(prefix="strong_"))
            try:
                repo, base_sha = sb.prepare(c, tmp)
                if repo is None:
                    rec["strong"] = "not_rerunnable"; rec["why"] = "base checkout failed"
                else:
                    if PRODUCT:
                        from agentvow import baseline
                        ps, pe, notes = baseline.derive(repo)
                        data = {"schema": "agentvow-recipe/1", "setup": ps, "test": "pytest -q " + " ".join(c["target_files"]), "env": pe}
                    else:
                        data, notes = sbl.derive_strong(repo, c["target_files"])
                    rec["recipe_setup"] = data["setup"]; rec["env_keys"] = sorted(data["env"]); rec["notes"] = notes
                    if sb.sh(["git", "apply", "--whitespace=nowarn", str(rd / "patch.diff")], repo).returncode:
                        rec["strong"] = "not_rerunnable"; rec["why"] = "patch did not apply"
                    else:
                        (repo / ".strong-recipe.json").write_text(json.dumps(data))
                        msg = tmp / "m.txt"; msg.write_text((rd / "final.txt").read_text())
                        new = rp.replay(repo, base_sha, msg, ["--recipe", str(repo / ".strong-recipe.json"), "--test-timeout", "600"])
                        ev = new.get("evidence") or {}
                        rec["strong"] = ev.get("result") or "none"; rec["summary"] = str(ev.get("summary"))[:200]
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
        OUT.open("a").write(json.dumps(rec) + "\n")
        print(f"{r['repo']}#{r['pr']}: ladder {old_ladder} | capture {old_capture} | strong {rec['strong']} ({len(rec.get('recipe_setup', []))} setup lines)", flush=True)


if __name__ == "__main__":
    main()
