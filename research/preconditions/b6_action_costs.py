"""Fresh measurement of per-action wall-clock cost for the two verification contexts on the Stage B6 attempts (see docs/research/forecast_grounding/ACTION_COST_PLAN.md).
NOT B6 data: B6 recorded no per-action timings. Each context is run once per attempt from the saved patch; the whole action (environment build + test run) is timed.
Usage: python3 research/preconditions/b6_action_costs.py [max]  -> data/preconditions/b6_action_costs.jsonl (resumable)"""
import json
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["B6"] = "1"   # same harness settings as the study (3 GB replay limit, B6 paths)
import stageb_run as sb  # noqa: E402
import run_pilot as rp  # noqa: E402
from agentvow import envsetup  # noqa: E402

D = ROOT / "data" / "preconditions"
OUT = D / "b6_action_costs.jsonl"


def norm(n):
    return re.sub(r"[-_.]+", "-", n).lower()


def timed(repo, base_sha, msg, extra):
    t = time.time()
    r = rp.replay(repo, base_sha, msg, extra)
    ev = r.get("evidence") or {}
    return {"seconds": round(time.time() - t, 1), "result": ev.get("result"), "counts": ev.get("counts"), "exit": r.get("exit")}


def measure(c, r):
    tmp = Path(tempfile.mkdtemp(prefix="actcost_"))
    rec = {"repo": r["repo"], "pr": r["pr"]}
    try:
        rd = Path(r["run_dir"])
        status = (rd / "status.txt").read_text()
        unt = [l[3:] for l in status.splitlines() if l.startswith("??") and not l[3:].startswith((".agentvow", ".pytest_cache", "__pycache__")) and not l[3:].endswith((".pyc", ".json"))]
        if unt:
            return {**rec, "skipped": f"untracked files not in the saved patch: {unt[:2]}"}
        repo, base_sha = sb.prepare(c, tmp)
        if repo is None:
            return {**rec, "skipped": base_sha}
        if (rd / "patch.diff").read_text().strip() and sb.sh(["git", "apply", "--whitespace=nowarn", str(rd / "patch.diff")], repo).returncode:
            return {**rec, "skipped": "patch did not apply"}
        msg = tmp / "m.txt"; msg.write_text((rd / "final.txt").read_text())
        files = c["target_files"]
        rec["repo_context"] = timed(repo, base_sha, msg, ["--run-tests", "--setup", "auto", "--test-cmd", "{py} -m " + sb.test_cmd(files), "--test-timeout", "600"])
        own = norm(str(envsetup._project_name(repo) or ""))
        keep = [l for l in (rd / "pipfreeze_agent.txt").read_text().splitlines()
                if l and not l.startswith("-e") and " @ " not in l and not l.lower().startswith("pip==") and not (own and norm(re.split(r"[=<>!~ \[]", l, maxsplit=1)[0]) == own)]
        (repo / ".agentvow-freeze.txt").write_text("\n".join(keep) + "\n")
        env = {}
        try:
            env = {k: v for k, v in (json.loads(rd.joinpath("recipe.json").read_text() or "{}").get("env", {}) or {}).items() if k not in ("HOME", "TMPDIR", "TEMP", "TMP", "PATH") and not k.startswith("PYTHON")}
        except (ValueError, OSError):
            pass
        (repo / ".agentvow-freeze-recipe.json").write_text(json.dumps({"schema": "agentvow-recipe/1", "setup": ["pip install -r .agentvow-freeze.txt"], "test": "pytest -q " + " ".join(files), "env": env}))
        rec["capture_context"] = timed(repo, base_sha, msg, ["--recipe", str(repo / ".agentvow-freeze-recipe.json"), "--test-timeout", "600"])
        rec["valid"] = bool(r.get("truth_in_agent_env") == "pass" and r.get("base_fails_in_agent_env"))
        rec["registered"] = {"repo": ((r.get("ladder") or {}).get("evidence") or {}).get("result"), "capture": ((r.get("freeze_replay") or {}).get("evidence") or {}).get("result")}
        return rec
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(limit=60):
    rows = [json.loads(l) for l in (D / "stageb6_results.jsonl").read_text().splitlines() if l.strip()]
    tasks = {(j["repo"], j["pr"]): j for j in map(json.loads, (D / "stageb6_tasks.jsonl").read_text().splitlines())}
    done = {(j["repo"], j["pr"]) for j in map(json.loads, OUT.read_text().splitlines())} if OUT.exists() else set()
    n = 0
    for r in rows:
        k = (r["repo"], r["pr"])
        if k in done or not r.get("run_dir") or n >= limit:
            continue
        if shutil.disk_usage(D).free < 3.5 * 1024**3:
            print("disk low; stopping", flush=True); break
        res = measure(tasks[k], r); n += 1
        OUT.open("a").write(json.dumps(res) + "\n")
        print(f"[{n}] {k[0]}#{k[1]}: " + (res.get("skipped") or f"repo {res['repo_context']['seconds']}s {res['repo_context']['result']} | capture {res['capture_context']['seconds']}s {res['capture_context']['result']} | registered {res['registered']}"), flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 60)
