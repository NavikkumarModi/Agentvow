"""Verify every pilot task BEFORE any agent run (pre-registration): fails at the start, passes with the reference solution in E_agent,
and its reference recipe replays as intended in a clean sandbox environment. Usage: python3 research/preconditions/verify_tasks.py"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TASKS = ROOT / "data" / "preconditions" / "tasks"
E = ROOT / "data" / "preconditions" / "e_agent"
sys.path.insert(0, str(ROOT))


def sh(cmd, cwd, env=None, timeout=600):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env, timeout=timeout)


def agent_env(extra=None):
    env = {**os.environ, "PATH": f"{E}/bin:{os.environ['PATH']}", "VIRTUAL_ENV": str(E)}
    env.pop("PYTHONPATH", None)
    env.update(extra or {})
    return env


def git_init(repo):
    for c in (["init", "-q", "-b", "main"], ["config", "user.email", "t@t"], ["config", "user.name", "t"], ["add", "-A"], ["commit", "-qm", "base"]):
        sh(["git", *c], repo)


def main():
    rows = []
    for d in sorted(TASKS.iterdir()):
        meta = json.loads((d / "meta.json").read_text())
        tmp = Path(tempfile.mkdtemp(prefix="pilotverify_"))
        repo = tmp / "r"
        shutil.copytree(d / "repo", repo)
        git_init(repo)
        a = sh([str(E / "bin/python"), "-m", "pytest", "-q", "-x"], repo, agent_env())
        initial_fails = a.returncode != 0
        for rel in (d / "solution").rglob("*"):
            if rel.is_file():
                dst = repo / rel.relative_to(d / "solution"); dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(rel, dst)
        for p in meta["prep"]:
            sh(p.split(), repo, agent_env())
        b = sh([str(E / "bin/python"), "-m", "pytest", "-q"], repo, agent_env((meta["ref_recipe"] or {}).get("env")))
        solved_in_agent_env = b.returncode == 0
        # clean replay of the reference recipe (generated files are NOT carried: they are untracked/ignored state)
        rec = tmp / "recipe.json"
        rec.write_text(json.dumps({"schema": "agentvow-recipe/1", **meta["ref_recipe"]}))
        msg = tmp / "m.txt"; msg.write_text("All tests pass.")
        env = {**os.environ, "AGENTVOW_HOME": str(tmp / "home")}
        env.pop("PYTHONPATH", None)
        c = sh([sys.executable, "-m", "agentvow.cli", "check", "--repo", str(repo), "--base", "HEAD", "--recipe", str(rec), "--transcript", str(msg), "--json"], ROOT, env, 900)
        result = None
        for f in (repo / ".agentvow" / "evidence").glob("testrun_*.json") if (repo / ".agentvow" / "evidence").exists() else []:
            result = json.loads(f.read_text()).get("result")
        replay_ok = result == "pass"
        expected_replay = not meta["inexpressible"]
        ok = initial_fails and solved_in_agent_env and (replay_ok == expected_replay)
        rows.append((meta["id"], initial_fails, solved_in_agent_env, result, expected_replay, ok))
        print(f"{'OK ' if ok else 'BAD'} {meta['id']:26} initial_fails={initial_fails} solved_in_E_agent={solved_in_agent_env} replay_result={result} expected_replay_pass={expected_replay}", flush=True)
        shutil.rmtree(tmp, ignore_errors=True)
    bad = [r for r in rows if not r[-1]]
    print(f"\n{len(rows) - len(bad)}/{len(rows)} tasks verified")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
