"""E2: replay the valid B6 captures inside a Linux container (see docs/strategy/PRODUCT_EXPLORATION_2026-10.md section 9). Runs INSIDE the container; the repository is mounted read-only at /src, the
saved run data read-only at /data (a copy of data/preconditions with the files this script needs), and results are written to /out/stageb6_linux.jsonl. Uses only the standard library and the product itself.
Usage (inside): python3 /src/research/preconditions/b6_linux_replay.py"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SRC, DATA, OUT = Path("/src"), Path("/data"), Path("/out/stageb6_linux.jsonl")
os.environ["AGENTVOW_MAX_ENV_MB"] = "3072"
sys.path.insert(0, str(SRC))


def norm(n):
    return re.sub(r"[-_.]+", "-", n).lower()


def sh(cmd, cwd=None, timeout=900):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def prepare(c, tmp: Path):
    """Port of stageb_run.prepare: the repository at the PR's base commit plus the PR's test files, with no git history, committed as one baseline commit."""
    clone = tmp / "clone"
    if sh(["git", "clone", "-q", f"https://github.com/{c['repo']}.git", str(clone)], timeout=900).returncode:
        return None, "clone_failed"
    sh(["git", "fetch", "-q", "origin", f"pull/{c['pr']}/head"], clone, timeout=300)
    if sh(["git", "checkout", "-q", c["base"]], clone).returncode:
        return None, "base_unavailable"
    for f in c["target_files"]:
        body = sh(["git", "show", f"{c['head']}:{f}"], clone).stdout
        (clone / f).parent.mkdir(parents=True, exist_ok=True)
        (clone / f).write_text(body)
    repo = tmp / "repo"
    shutil.copytree(clone, repo, symlinks=True, ignore=shutil.ignore_patterns(".git"))
    shutil.rmtree(clone, ignore_errors=True)
    for cmd in (["init", "-q", "-b", "main"], ["config", "user.email", "t@t"], ["config", "user.name", "t"], ["add", "-A"], ["commit", "-qm", "task baseline"]):
        sh(["git", *cmd], repo)
    return repo, sh(["git", "rev-parse", "HEAD"], repo).stdout.strip()


def main():
    rows = [json.loads(l) for l in (DATA / "stageb6_results.jsonl").read_text().splitlines()]
    tasks = {(j["repo"], j["pr"]): j for j in map(json.loads, (DATA / "stageb6_tasks.jsonl").read_text().splitlines())}
    valid = [r for r in rows if r.get("truth_in_agent_env") == "pass" and r.get("base_fails_in_agent_env") and ((r.get("freeze_replay") or {}).get("evidence") or {}).get("result") == "pass"]
    done = {(j["repo"], j["pr"]) for j in map(json.loads, OUT.read_text().splitlines())} if OUT.exists() else set()
    from agentvow import envsetup
    envsetup.MAX_VENV = 3 * 1024**3
    for r in valid:
        key = (r["repo"], r["pr"])
        if key in done:
            continue
        c = tasks[key]
        rd = DATA / "stageb6_runs" / f"{r['repo'].replace('/', '_')}_{r['pr']}"
        rec = {"repo": r["repo"], "pr": r["pr"], "macos": "pass"}
        status = (rd / "status.txt").read_text()
        unt = [l[3:] for l in status.splitlines() if l.startswith("??") and not l[3:].startswith((".agentvow", ".pytest_cache", "__pycache__")) and not l[3:].endswith((".pyc", ".json"))]
        if unt:
            rec["linux"] = "not_rerunnable"; rec["why"] = "untracked files not in the patch"
        else:
            tmp = Path(tempfile.mkdtemp(prefix="lx_"))
            try:
                repo, base = prepare(c, tmp)
                if repo is None:
                    rec["linux"] = "not_rerunnable"; rec["why"] = base
                else:
                    if sh(["git", "-C", str(repo), "apply", "--whitespace=nowarn", str(rd / "patch.diff")]).returncode:
                        rec["linux"] = "not_rerunnable"; rec["why"] = "patch failed"
                    else:
                        own = norm(str(envsetup._project_name(repo) or ""))
                        keep = [l for l in (rd / "pipfreeze_agent.txt").read_text().splitlines()
                                if l and not l.startswith("-e") and " @ " not in l and not l.lower().startswith("pip==") and not (own and norm(re.split(r"[=<>!~ \[]", l, maxsplit=1)[0]) == own)]
                        (repo / ".linux-freeze.txt").write_text("\n".join(keep) + "\n")
                        try:
                            env = json.loads(r.get("recipe_text") or "{}").get("env", {}) if r.get("recipe_text") else {}
                        except ValueError:
                            env = {}
                        env = {k: v for k, v in env.items() if k not in ("HOME", "TMPDIR", "TEMP", "TMP", "PATH") and not k.startswith("PYTHON")}
                        (repo / ".linux-recipe.json").write_text(json.dumps({"schema": "agentvow-recipe/1", "setup": ["pip install -r .linux-freeze.txt"], "test": "pytest -q " + " ".join(c["target_files"]), "env": env}))
                        msg = tmp / "m.txt"; msg.write_text((rd / "final.txt").read_text())
                        # the checkout is detached at base with the patch applied as uncommitted changes, like the macOS re-replays
                        p = subprocess.run([sys.executable, "-m", "agentvow.cli", "check", "--repo", str(repo), "--base", base, "--transcript", str(msg), "--json", "--recipe", str(repo / ".linux-recipe.json"), "--test-timeout", "600"],
                                           cwd=str(SRC), capture_output=True, text=True, timeout=1800, env={**os.environ, "AGENTVOW_HOME": str(tmp / "home")})
                        try:
                            o = json.loads(p.stdout)
                            f = next(x for x in o["findings"] if x["kind"] == "tests_pass")
                            # the registered comparison is on the TEST RESULT of the replay (as in B6 and the macOS re-replays), not on the claim verdict (a claimed count that differs makes the verdict UNKNOWN)
                            evs = sorted((repo / ".agentvow" / "evidence").glob("testrun_*.json"), key=lambda q: q.stat().st_mtime)
                            e = json.loads(evs[-1].read_text()) if evs else {}
                            ev = e.get("evidence", e)
                            rec["linux"] = ev.get("result") or "none"
                            rec["verdict"] = f["verdict"]; rec["counts"] = ev.get("counts"); rec["summary"] = str(ev.get("summary", ""))[:200]; rec["hint"] = str(ev.get("hint", ""))[:200]
                            rec["failed"] = [str(x)[:100] for x in (ev.get("failed_ids") or [])[:3]]; rec["why"] = str(f.get("why", ""))[:200]
                        except (ValueError, StopIteration, KeyError):
                            rec["linux"] = "error"; rec["why"] = (p.stdout + p.stderr)[-300:]
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
        OUT.open("a").write(json.dumps(rec) + "\n")
        print(f"{key}: macos pass | linux {rec['linux']} {rec.get('why', '')[:100]}", flush=True)


if __name__ == "__main__":
    main()
