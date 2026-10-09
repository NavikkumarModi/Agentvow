"""Stage B phase 2 = validity screen B0 (docs/research/forecast_grounding/STAGE_B.md section 2). NO agent runs.
A candidate is VALID only if a reference environment reproduces the PR's target tests at its head (S1: zero-config ladder; S2: CI-derived recipe), the same
tests FAIL at the base once the PR's test files are applied (the task is non-trivial), and the head result is the same twice (determinism).
Quota-driven: candidates are processed in a seeded random order until 30 valid S1 and 30 valid S2 tasks (<= 2 per repository) exist or candidates run out.
Usage: python3 research/preconditions/stageb_validate.py  -> data/preconditions/stageb_validated.jsonl (resumable)"""
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agentvow import envsetup, recipe as recipe_mod, runner  # noqa: E402
import ci_recipe  # noqa: E402

D = ROOT / "data" / "preconditions"
CANDS, OUT = D / "stageb_cands.jsonl", D / "stageb_validated.jsonl"
WORK = D / "stageb_work"
SEED, QUOTA, PER_REPO = 2028, 30, 2
MIN_FREE = 2.5 * 1024**3


def sh(cmd, cwd=None, timeout=600):
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, "", "timeout")


def target_run(wt, py, files, env_extra=None):
    argv = [py, "-m", "pytest", "-q", "-rA", "-p", "no:cacheprovider", *files]
    r = runner.run_tests(wt, argv, timeout=300, write=False, env_extra=env_extra)
    return r["result"], r.get("counts", {}), (r.get("summary") or "")[:120]


def validate(repo_dir: Path, c: dict) -> dict:
    out = {**c, "valid": False, "stratum": None, "why": None}
    n = c["pr"]
    sh(["git", "fetch", "-q", "origin", f"pull/{n}/head"], repo_dir, 180)
    base, head = c["base"], c["head"]
    if sh(["git", "cat-file", "-e", head], repo_dir).returncode or sh(["git", "cat-file", "-e", base], repo_dir).returncode:
        return {**out, "why": "commits_unavailable"}
    wtd = WORK / f"{c['repo'].replace('/', '_')}_{n}"
    shutil.rmtree(wtd, ignore_errors=True)
    wtd.mkdir(parents=True)
    hw, bw = wtd / "head", wtd / "base"
    try:
        sh(["git", "worktree", "add", "--detach", "-f", str(hw), head], repo_dir)
        sh(["git", "worktree", "add", "--detach", "-f", str(bw), base], repo_dir)
        files = [f for f in c["test_files"] if (hw / f).is_file()]
        if not files:
            return {**out, "why": "no_test_files_at_head"}
        out["target_files"] = files
        # --- S1: zero-config ladder at head
        venv1, home1 = wtd / "venv1", wtd / "home1"
        py, notes, aborted = envsetup.build_env(hw, venv1, home1)
        env_py, extra, stratum, rec_data = None, None, None, None
        if py and not aborted:
            res, counts, summ = target_run(hw, py, files)
            out["s1"] = {"result": res, "counts": counts, "summary": summ}
            if res == "pass" and counts.get("passed"):
                env_py, stratum = py, "S1"
        shutil.rmtree(venv1, ignore_errors=True)
        # --- S2: CI-derived recipe (only when S1 failed for a dependency-like reason)
        if env_py is None:
            wf = {p.name: p.read_text() for p in (hw / ".github" / "workflows").glob("*.y*ml")} if (hw / ".github" / "workflows").is_dir() else {}
            rec_data, cnotes = ci_recipe.derive(wf)
            out["ci_notes"] = cnotes[:4]
            if rec_data is None:
                return {**out, "why": "no_s1_and_no_ci_recipe"}
            try:
                rec = recipe_mod.parse(rec_data)
            except recipe_mod.RecipeError as e:
                return {**out, "why": f"ci_recipe_refused: {str(e)[:60]}"}
            venv2, home2 = wtd / "venv2", wtd / "home2"
            py2, n2, ab2 = recipe_mod.build_env(hw, rec, venv2, home2)
            if not py2 or ab2:
                return {**out, "why": "ci_env_failed: " + "; ".join(n2)[:80]}
            res, counts, summ = target_run(hw, py2, files, rec.env)
            out["s2"] = {"result": res, "counts": counts, "summary": summ}
            if res == "pass" and counts.get("passed"):
                env_py, extra, stratum = py2, rec.env, "S2"
                out["reference_recipe"] = {k: rec_data[k] for k in ("setup", "env")}
        if env_py is None:
            return {**out, "why": "no_reference_environment"}
        # --- determinism at head
        res2, counts2, _ = target_run(hw, env_py, files, extra)
        if res2 != "pass" or counts2.get("passed") != (out.get("s1") or out.get("s2"))["counts"].get("passed"):
            return {**out, "stratum": stratum, "why": "nondeterministic_at_head"}
        # --- non-triviality: at base with the PR's test files applied the target tests must not pass
        for f in files:
            (bw / f).parent.mkdir(parents=True, exist_ok=True)
            (bw / f).write_text(sh(["git", "show", f"{head}:{f}"], repo_dir).stdout)
        resb, countsb, summb = target_run(bw, env_py, files, extra)
        out["base_with_tests"] = {"result": resb, "counts": countsb, "summary": summb}
        if resb == "pass":
            return {**out, "stratum": stratum, "why": "tests_already_pass_at_base"}
        if resb == "inconclusive" and "missing dependency" in summb:
            return {**out, "stratum": stratum, "why": "base_env_missing_dependency"}
        return {**out, "valid": True, "stratum": stratum, "why": None}
    finally:
        for w in (hw, bw):
            sh(["git", "worktree", "remove", "--force", str(w)], repo_dir)
        shutil.rmtree(wtd, ignore_errors=True)


def main():
    cands = [j for j in map(json.loads, CANDS.read_text().splitlines()) if j.get("ok")]
    random.Random(SEED).shuffle(cands)
    done = {(j["repo"], j["pr"]): j for j in map(json.loads, OUT.read_text().splitlines())} if OUT.exists() else {}
    per_repo, quota = {}, {"S1": 0, "S2": 0}
    for j in done.values():
        if j["valid"]:
            quota[j["stratum"]] += 1; per_repo[j["repo"]] = per_repo.get(j["repo"], 0) + 1
    print(f"{len(cands)} structural candidates in {len({c['repo'] for c in cands})} repos; already valid {quota}", flush=True)
    WORK.mkdir(parents=True, exist_ok=True)
    by_repo = {}
    for c in cands:
        by_repo.setdefault(c["repo"], []).append(c)
    for repo, items in by_repo.items():
        if min(quota.values()) >= QUOTA or shutil.disk_usage(D).free < MIN_FREE:
            if shutil.disk_usage(D).free < MIN_FREE:
                print("disk low; stopping", flush=True)
            break
        todo = [c for c in items if (c["repo"], c["pr"]) not in done]
        if not todo or per_repo.get(repo, 0) >= PER_REPO:
            continue
        rd = WORK / repo.replace("/", "_")
        shutil.rmtree(rd, ignore_errors=True)
        r = sh(["git", "clone", "-q", f"https://github.com/{repo}.git", str(rd)], timeout=900)
        if r.returncode:
            for c in todo:
                res = {**c, "valid": False, "why": "clone_failed"}
                OUT.open("a").write(json.dumps(res) + "\n")
            continue
        try:
            for c in todo:
                if per_repo.get(repo, 0) >= PER_REPO:
                    break
                t0 = time.time()
                try:
                    res = validate(rd, c)
                except Exception as e:
                    res = {**c, "valid": False, "why": f"error: {type(e).__name__}: {e}"[:120]}
                res["seconds"] = round(time.time() - t0)
                with OUT.open("a") as fh:
                    fh.write(json.dumps(res) + "\n")
                if res["valid"]:
                    quota[res["stratum"]] += 1; per_repo[repo] = per_repo.get(repo, 0) + 1
                print(f"{repo}#{c['pr']}: {'VALID ' + res['stratum'] if res['valid'] else res['why']}  [{res['seconds']}s]  quota={quota}", flush=True)
        finally:
            shutil.rmtree(rd, ignore_errors=True)
    print("done", quota, flush=True)


if __name__ == "__main__":
    main()
