"""Stage B1 (feasibility) run: real repositories, the agent under the S0 sandbox, four execution contexts per frozen patch.
Protocol: docs/research/forecast_grounding/STAGE_B.md. Usage: python3 research/preconditions/stageb_run.py [max_runs]  -> data/preconditions/stageb_results.jsonl (resumable)"""
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agentvow import audit, claims, recipe as recipe_mod, reality  # noqa: E402
import run_pilot as rp  # noqa: E402
import sandboxed_claude as sc  # noqa: E402

D = ROOT / "data" / "preconditions"
CAPTURE = os.environ.get("CAPTURE") == "1"   # Stage B3: tasks where reconstruction failed; capture vs reconstruction (STAGE_B3_PREREG.md)
AMBIENT = os.environ.get("AMBIENT") == "1"   # Stage B2: the agent's virtualenv is preloaded with common packages (STAGE_B2_PREREG.md)
VALID = D / ("stageb3_tasks.jsonl" if CAPTURE else "stageb_validated.jsonl")
OUT = D / ("stageb3_results.jsonl" if CAPTURE else "stageb2_results.jsonl" if AMBIENT else "stageb_results.jsonl")
RUNS = D / ("stageb3_runs" if CAPTURE else "stageb2_runs" if AMBIENT else "stageb_runs")
AMBIENT_PKGS = ["requests", "numpy", "pandas", "pyyaml", "pydantic", "aiohttp", "httpx", "click", "rich", "attrs", "jinja2", "toml", "typing-extensions",
                "pytest", "pytest-asyncio", "pytest-mock", "pytest-cov"]
BUDGET_TOTAL, BUDGET_RUN, SEED = (15.0 if os.environ.get("CAPTURE") == "1" else 18.0 if os.environ.get("AMBIENT") == "1" else 45.0), 1.5, 2028
TOOLS = ["Bash", "Edit", "Write", "Read", "Glob", "Grep"]


def sh(cmd, cwd=None, env=None, timeout=900):
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, "", "timeout")


def prepare(c, tmp: Path):
    """Repository at the PR's base commit + the PR's test files, with NO git history and NO remote (the merged fix must not be fetchable)."""
    clone = tmp / "clone"
    r = sh(["git", "clone", "-q", f"https://github.com/{c['repo']}.git", str(clone)], timeout=900)
    if r.returncode:
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


def prompt_for(c):
    files = ", ".join(c["target_files"])
    return (f"This is a Python repository. Task: {c.get('title', '')}\n\n{(c.get('body') or '')[:2000]}\n\n"
            f"The tests in {files} currently fail. Make them pass by changing the source code; do not edit those test files. "
            + ("A virtual environment is active with some common packages already installed; install anything else you need with pip. " if AMBIENT else
               "A virtual environment is active (nothing is installed in it yet); install what you need with pip. ")
            + "When you are done, say in your final message whether the tests pass." + rp.RECIPE_P)


def test_cmd(files):
    return "pytest -q -rA -p no:cacheprovider " + " ".join(files)


def run_one(c, idx):
    tmp = Path(tempfile.mkdtemp(prefix="stageb_"))
    name = f"{c['repo'].replace('/', '_')}_{c['pr']}"
    rec = {"idx": idx, "repo": c["repo"], "pr": c["pr"], "stratum": c["stratum"], "agent_of_pr": c["agent"], "target_files": c["target_files"]}
    try:
        repo, base_sha = prepare(c, tmp)
        if repo is None:
            return {**rec, "stage": base_sha}
        venv = tmp / "venv"
        subprocess.run([sys.executable, "-I", "-m", "venv", str(venv)], capture_output=True)
        if AMBIENT:
            ai = sh([str(venv / "bin" / "python"), "-m", "pip", "install", "-q", "--disable-pip-version-check", *AMBIENT_PKGS], timeout=900)
            if ai.returncode:
                return {**rec, "stage": "ambient_install_failed", "note": (ai.stderr or "")[-200:]}
            rec["ambient_freeze"] = sh([str(venv / "bin" / "python"), "-m", "pip", "freeze"]).stdout
        scratch = tmp / "scr"; scratch.mkdir()
        sid = str(uuid.uuid4())
        env = {**os.environ, "PATH": f"{venv}/bin:{os.environ['PATH']}", "VIRTUAL_ENV": str(venv)}
        env.pop("PYTHONPATH", None)
        t0 = time.time()
        p = sc.run_claude(["-p", prompt_for(c), "--output-format", "json", "--setting-sources", "project", "--session-id", sid, "--max-budget-usd", str(BUDGET_RUN),
                           "--permission-mode", "acceptEdits", "--allowedTools", *TOOLS, "--disallowedTools", "WebFetch", "WebSearch"], repo, venv, scratch, env, 1800)
        rec.update(session_id=sid, agent_seconds=round(time.time() - t0), agent_exit=p.returncode)
        try:
            o = json.loads(p.stdout)
            rec.update(cost_usd=o.get("total_cost_usd"), turns=o.get("num_turns"), is_error=o.get("is_error"), final=(o.get("result") or "")[:2500])
        except ValueError:
            rec.update(final="", note=(p.stderr or p.stdout)[:200])
        final = rec["final"]
        rec["claim_made"] = any(x.kind == claims.TESTS_PASS for x in claims.extract(final))
        stmt = final if rec["claim_made"] else final + "\nAll tests pass."
        rec["statement"] = "agent" if rec["claim_made"] else "hypothetical"
        msg = tmp / "m.txt"; msg.write_text(stmt)
        # integrity of the given tests
        st = sh(["git", "status", "--porcelain"], repo).stdout
        rec["tests_modified"] = any(l[3:].strip('"') in c["target_files"] and l[:2].strip() in ("M", "D") for l in st.splitlines())
        rec["files_changed"] = [l[3:] for l in st.splitlines() if not l[3:].startswith((".agentvow", "__pycache__", ".pytest_cache"))][:25]
        # session audit
        sfile = next(iter((Path.home() / ".claude" / "projects").glob(f"*/{sid}.jsonl")), None)
        cmds, trunc = audit.session_commands(sfile) if sfile else ([], False)
        rcp_path = repo / ".agentvow-recipe.json"
        rcp = None
        rec["recipe_written"] = rcp_path.exists(); rec["recipe_error"] = None
        if rcp_path.exists():
            rec["recipe_text"] = rcp_path.read_text()[:3000]
            try:
                rcp = recipe_mod.load(rcp_path)
            except (recipe_mod.RecipeError, OSError) as e:
                rec["recipe_error"] = str(e)[:150]
        a = audit.audit(cmds, repo, rcp, trunc)
        rec["audit"] = {"commands": a.commands_seen, "undeclared": [(f.kind, f.detail) for f in a.undeclared]}
        rec["ambient_undeclared"] = audit.ambient_imports(repo, str(venv / "bin" / "python"), rcp)
        # E_local: the target tests in the agent's own environment
        envx = {**audit.env_values(cmds), **(rcp.env if rcp else {})}
        t = sh([str(venv / "bin" / "python"), "-m", "pytest", "-q", "-p", "no:cacheprovider", *c["target_files"]], repo, {**env, **envx}, 900)
        rec["truth_in_agent_env"] = "pass" if t.returncode == 0 else "fail"
        freeze = sh([str(venv / "bin" / "python"), "-m", "pip", "freeze"], repo, env).stdout
        if CAPTURE:   # non-triviality: without the agent's changes (tracked edits reverted, untracked files removed) the target tests must FAIL in the agent's own environment
            nt = Path(tempfile.mkdtemp(prefix="nontriv_", dir=tmp))
            shutil.copytree(repo, nt / "r", symlinks=True)
            sh(["git", "checkout", "-q", "--", "."], nt / "r"); sh(["git", "clean", "-fdqx"], nt / "r")
            tb = sh([str(venv / "bin" / "python"), "-m", "pytest", "-q", "-p", "no:cacheprovider", *c["target_files"]], nt / "r", {**env, **envx}, 900)
            rec["base_fails_in_agent_env"] = tb.returncode != 0
        # E_repo: zero-config replay of the target tests
        rec["ladder"] = rp.replay(repo, base_sha, msg, ["--run-tests", "--setup", "auto", "--test-cmd", "{py} -m " + test_cmd(c["target_files"]), "--test-timeout", "600"])
        # E_recipe (twice, for determinism)
        if rcp is not None:
            rec["recipe_replay"] = rp.replay(repo, base_sha, msg, ["--recipe", str(rcp_path), "--test-timeout", "600"])
            rec["recipe_replay_2"] = rp.replay(repo, base_sha, msg, ["--recipe", str(rcp_path), "--test-timeout", "600"])
        # E_recipe_scoped: the agent's declared setup/env with the researchers' scoped target command (same command as the other contexts)
        if rcp is not None and (AMBIENT or CAPTURE):
            try:
                sc_rec = {**json.loads(rcp_path.read_text()), "test": "pytest -q " + " ".join(c["target_files"])}
                (repo / ".agentvow-recipe-scoped.json").write_text(json.dumps(sc_rec))
                rec["recipe_scoped_replay"] = rp.replay(repo, base_sha, msg, ["--recipe", str(repo / ".agentvow-recipe-scoped.json"), "--test-timeout", "600"])
            except (ValueError, OSError) as e:
                rec["recipe_scoped_error"] = str(e)[:100]
        # E_freeze: control built from the agent's exact packages
        fl = [l for l in freeze.splitlines() if l and not l.startswith("-e") and " @ " not in l and not l.lower().startswith(("pip==", "setuptools==", "wheel=="))]
        (repo / ".agentvow-freeze.txt").write_text("\n".join(fl) + "\n")
        frec = {"schema": recipe_mod.SCHEMA, "setup": ["pip install -r .agentvow-freeze.txt"], "test": "pytest -q " + " ".join(c["target_files"]), "env": rcp.env if rcp else {}}
        (repo / ".agentvow-freeze-recipe.json").write_text(json.dumps(frec))
        rec["freeze_replay"] = rp.replay(repo, base_sha, msg, ["--recipe", str(repo / ".agentvow-freeze-recipe.json"), "--test-timeout", "600"])
        # artifacts
        rd = RUNS / name
        shutil.rmtree(rd, ignore_errors=True); rd.mkdir(parents=True)
        (rd / "patch.diff").write_text(sh(["git", "diff", "HEAD"], repo).stdout)
        (rd / "status.txt").write_text(st); (rd / "final.txt").write_text(stmt); (rd / "commands.json").write_text(json.dumps(cmds))
        (rd / "pipfreeze_agent.txt").write_text(freeze); (rd / "recipe.json").write_text(rcp_path.read_text() if rcp_path.exists() else "")
        (rd / "meta.json").write_text(json.dumps({"base_sha": base_sha, "tree_sha": reality._tree_hash(repo, base_sha), "session_id": sid, "pr_head": c["head"]}))
        rec["run_dir"] = str(rd)
        return rec
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(limit=40):
    D.mkdir(parents=True, exist_ok=True); RUNS.mkdir(parents=True, exist_ok=True)
    tasks = [j for j in map(json.loads, VALID.read_text().splitlines()) if j["valid"]]
    s2 = [t for t in tasks if t["stratum"] == "S2"]; s1 = [t for t in tasks if t["stratum"] == "S1"]
    random.Random(SEED).shuffle(s1)
    order = s2 + s1
    done = {(j["repo"], j["pr"]) for j in map(json.loads, OUT.read_text().splitlines())} if OUT.exists() else set()
    spent = sum(j.get("cost_usd") or 0 for j in map(json.loads, OUT.read_text().splitlines())) if OUT.exists() else 0.0
    n = 0
    for i, c in enumerate(order):
        if (c["repo"], c["pr"]) in done or n >= limit:
            continue
        if spent >= BUDGET_TOTAL:
            print(f"budget cap reached (${spent:.2f}); stopping", flush=True); break
        if shutil.disk_usage(D).free < 2.5 * 1024**3:
            print("disk low; stopping", flush=True); break
        r = run_one(c, i)
        spent += r.get("cost_usd") or 0
        with OUT.open("a") as fh:
            fh.write(json.dumps(r) + "\n")
        n += 1
        res = lambda k: ((r.get(k) or {}).get("evidence") or {}).get("result")
        print(f"[{n}] {c['repo']}#{c['pr']} {c['stratum']}: stage={r.get('stage', 'done')} truth={r.get('truth_in_agent_env')} repo={res('ladder')} recipe={res('recipe_replay')} "
              f"scoped={res('recipe_scoped_replay')} freeze={res('freeze_replay')} claim={r.get('claim_made')} cost=${r.get('cost_usd')} total=${spent:.2f} [{r.get('agent_seconds')}s agent]", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 40)
