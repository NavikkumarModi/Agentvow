"""Secondary check of MUTATION_STUDY_PREREG.md section 4: for each survivor on an executed line, run the project's FULL test suite on the mutant. 'Killed by other tests' means the suite
shows a failure that its clean baseline did not (the claimed target tests were not the only tests that could notice the change). Only runs whose full suite finishes within 180 s at baseline
are checked; the others are reported as not checked. Same sandbox, environment rebuild and per-run cap rules as the study. Usage: python3 research/preconditions/mutation_full_suite.py"""
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["B6"] = "1"
os.environ["AGENTVOW_MAX_ENV_MB"] = "3072"
import stageb_run as sb  # noqa: E402
from agentvow import envsetup, recipe as recipe_mod, runner  # noqa: E402

D = ROOT / "data" / "preconditions"
OUT = D / "mutation_full_suite.jsonl"
CR = "/tmp/mutvenv/bin/cosmic-ray"
SUITE_LIMIT = 180


def norm(n):
    return re.sub(r"[-_.]+", "-", n).lower()


def run_suite(cmd, repo, timeout):
    t = time.time()
    try:
        p = subprocess.run(cmd, cwd=repo, shell=True, capture_output=True, text=True, timeout=timeout)
        out, rc, to = p.stdout + p.stderr, p.returncode, False
    except subprocess.TimeoutExpired as e:
        out, rc, to = (e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")), 124, True
    failed = set(re.findall(r"^(?:FAILED|ERROR) (\S+)", re.sub(r"\x1b\[[0-9;]*m", "", out), re.M))
    return {"rc": rc, "timeout": to, "failed": failed, "seconds": round(time.time() - t, 1), "tail": out[-200:]}


def process(stage, repo_name, pr, survivors, task, run_dir):
    tmp = Path(tempfile.mkdtemp(prefix="mfull_")).resolve()
    scratch = Path(tempfile.mkdtemp(prefix="am", dir=runner.scratch_base())).resolve()
    (scratch / "h").mkdir(); (scratch / "t").mkdir()
    try:
        rd = Path(run_dir)
        repo, _ = sb.prepare(task, tmp)
        if repo is None:
            return [{"note": "could not rebuild", "survivor": s} for s in survivors]
        repo = repo.resolve()
        patch = (rd / "patch.diff").read_text()
        if patch.strip() and sb.sh(["git", "apply", "--whitespace=nowarn", str(rd / "patch.diff")], repo).returncode:
            return [{"note": "patch did not apply", "survivor": s} for s in survivors]
        own = norm(str(envsetup._project_name(repo) or ""))
        keep = [l for l in (rd / "pipfreeze_agent.txt").read_text().splitlines()
                if l and not l.startswith("-e") and " @ " not in l and not l.lower().startswith("pip==") and not (own and norm(re.split(r"[=<>!~ \[]", l, maxsplit=1)[0]) == own)]
        (repo / ".agentvow-freeze.txt").write_text("\n".join(keep) + "\n")
        rcp = recipe_mod.parse({"schema": "agentvow-recipe/1", "setup": ["pip install -r .agentvow-freeze.txt"], "test": "pytest -q", "env": {}})
        py, notes, aborted = recipe_mod.build_env(repo, rcp, tmp / "venv", tmp / "home")
        if not py or aborted:
            return [{"note": f"environment not built ({aborted})", "survivor": s} for s in survivors]
        pp = ":".join([f"{repo}/src", str(repo), *[str(repo / x) for x in rcp.local_roots]])
        inner = ["env", f"HOME={scratch}/h", f"TMPDIR={scratch}/t", "PYTHONDONTWRITEBYTECODE=1", f"PYTHONPATH={pp}", py, "-m", "pytest", "-q", "--tb=no", "-rfE", "--continue-on-collection-errors", "-p", "no:cacheprovider"]
        cmd = shlex.join(runner.wrap(inner, repo, scratch))
        b1 = run_suite(cmd, repo, SUITE_LIMIT + 60)
        if b1["timeout"] or b1["seconds"] > SUITE_LIMIT:
            return [{"note": f"full suite too slow ({b1['seconds']} s > {SUITE_LIMIT} s)", "survivor": s, "baseline_s": b1["seconds"]} for s in survivors]
        if b1["rc"] not in (0, 1):
            return [{"note": f"full suite did not run tests at baseline (pytest exit code {b1['rc']})", "survivor": s, "baseline_s": b1["seconds"]} for s in survivors]
        b2 = run_suite(cmd, repo, SUITE_LIMIT + 60)
        base_failed = b1["failed"] | b2["failed"]
        res = []
        for s in survivors:
            f = repo / s["file"]; orig = f.read_bytes()
            sh = subprocess.run([CR, "apply", s["file"], s["operator"], str(s["occurrence"])], cwd=repo, capture_output=True, text=True, timeout=60)
            if f.read_bytes() == orig:
                res.append({"survivor": s, "note": "mutation did not apply", "baseline_s": b1["seconds"]}); continue
            m = run_suite(cmd, repo, int(max(60, 5 * b1["seconds"])))
            f.write_bytes(orig)
            new = sorted(m["failed"] - base_failed)
            outcome = "killed_by_full_suite" if (new or m["timeout"] or (m["rc"] not in (0, 1) and not m["failed"])) else "survived_full_suite"
            res.append({"survivor": s, "outcome": outcome, "new_failures": new[:5], "n_new_failures": len(new), "timeout": m["timeout"], "rc": m["rc"], "baseline_s": b1["seconds"], "baseline_failed_n": len(base_failed)})
        return res
    finally:
        shutil.rmtree(tmp, ignore_errors=True); shutil.rmtree(scratch, ignore_errors=True)


def main():
    S = json.load(open(D / "mutation_survivors_executed.json"))["survivors_executed"]
    by = defaultdict(list)
    for s in S:
        by[(s["stage"], s["repo"], s["pr"])].append(s)
    done = {(j["stage"], j["repo"], j["pr"]) for j in map(json.loads, OUT.read_text().splitlines())} if OUT.exists() else set()
    t_all = time.time()
    for (stage, repo_name, pr), items in by.items():
        if (stage, repo_name, pr) in done:
            continue
        if time.time() - t_all > 3 * 3600 or shutil.disk_usage(D).free < 4 * 1024**3:
            print("cap or disk reached; stopping", flush=True); return
        r = next(x for x in map(json.loads, (D / f"{stage}_results.jsonl").read_text().splitlines()) if x["repo"] == repo_name and x["pr"] == pr)
        task = next(x for x in map(json.loads, (D / f"{stage}_tasks.jsonl").read_text().splitlines()) if x["repo"] == repo_name and x["pr"] == pr)
        res = process(stage, repo_name, pr, items, task, r["run_dir"])
        OUT.open("a").write(json.dumps({"stage": stage, "repo": repo_name, "pr": pr, "results": res}) + "\n")
        c = {}
        for x in res:
            k = x.get("outcome") or "not_checked"
            c[k] = c.get(k, 0) + 1
        print(f"{repo_name}#{pr}: {len(items)} survivors -> {c}", flush=True)


if __name__ == "__main__":
    main()
