"""Mutation study harness (docs/research/forecast_grounding/MUTATION_STUDY_PREREG.md, population per amendment 2). Rules are fixed there; this file implements them.
Per valid run of Stages B3-B6: rebuild head + the captured environment, require the sandboxed target tests to pass twice, measure which added lines they execute (coverage),
enumerate cosmic-ray mutants on the lines the agent's patch added, sample <= 25 (seeded, stratified by operator family), run them in the platform sandbox, record outcomes.
Usage: python3 research/preconditions/mutation_study.py [max_runs] -> data/preconditions/mutation_study.jsonl (resumable; one JSON line per run)"""
import json
import os
import random
import re
import shlex
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["B6"] = "1"
os.environ["AGENTVOW_MAX_ENV_MB"] = "3072"
import stageb_run as sb  # noqa: E402
from agentvow import changedcov, envsetup, recipe as recipe_mod, runner  # noqa: E402

D = ROOT / "data" / "preconditions"
OUT = D / "mutation_study.jsonl"
CR = "/tmp/mutvenv/bin/cosmic-ray"
SEED, CAP, RUN_SECONDS = "20261015", 25, 20 * 60
STAGES = ("stageb3", "stageb4", "stageb5", "stageb6")
TESTY = re.compile(r"(^|/)(tests?|testing)(/|$)|(^|/)test_[^/]*\.py$|_test\.py$|(^|/)conftest\.py$")


def norm(n):
    return re.sub(r"[-_.]+", "-", n).lower()


def added_by_file(patch):
    out, cur, n = {}, None, 0
    for ln in patch.splitlines():
        m = re.match(r"^diff --git a/.* b/(.*)$", ln)
        if m:
            cur = m.group(1); out.setdefault(cur, set()); continue
        h = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", ln)
        if h:
            n = int(h.group(1)); continue
        if cur is None or ln.startswith(("+++", "---")):
            continue
        if ln.startswith("+"):
            out[cur].add(n); n += 1
        elif not ln.startswith("-"):
            n += 1
    return {f: s for f, s in out.items() if f.endswith(".py") and not TESTY.search(f)}


def stmt_line(path, line):
    """First line of the innermost statement that contains `line` (falls back to the line itself)."""
    import ast
    try:
        tree = ast.parse(Path(path).read_text(errors="replace"))
    except (SyntaxError, ValueError, OSError):
        return line
    best = None
    for n in ast.walk(tree):
        if isinstance(n, ast.stmt) and n.lineno <= line <= (n.end_lineno or n.lineno):
            if best is None or (n.end_lineno - n.lineno) < (best.end_lineno - best.lineno) or ((n.end_lineno - n.lineno) == (best.end_lineno - best.lineno) and n.lineno >= best.lineno):
                best = n
    return best.lineno if best else line


def family(op):
    return op.split("/")[-1].split("_")[0]


def sample(cands, key):
    rng = random.Random(f"{SEED}|{key}")
    cands = sorted(cands, key=lambda c: (c["file"], c["line"], c["operator"], c["occurrence"]))
    groups = {}
    for c in cands:
        groups.setdefault(family(c["operator"]), []).append(c)
    fams = sorted(groups)
    rng.shuffle(fams)
    for f in fams:
        rng.shuffle(groups[f])
    out = []
    while len(out) < CAP and any(groups[f] for f in fams):
        for f in fams:
            if groups[f] and len(out) < CAP:
                out.append(groups[f].pop())
    return out


def sh(cmd, cwd, timeout, shell=False, env=None):
    try:
        return subprocess.run(cmd, cwd=cwd, shell=shell, capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, "", "timeout")


def process(stage, r, task, yield_row):
    rec = {"stage": stage, "repo": r["repo"], "pr": r["pr"], "candidates_total": yield_row.get("candidates")}
    tmp = Path(tempfile.mkdtemp(prefix="mstudy_")).resolve()
    scratch = Path(tempfile.mkdtemp(prefix="am", dir=runner.scratch_base())).resolve()
    (scratch / "h").mkdir(); (scratch / "t").mkdir()
    t_run = time.time()
    try:
        rd = Path(r["run_dir"])
        repo, base_sha = sb.prepare(task, tmp)
        if repo is None:
            return {**rec, "excluded": "could not rebuild the task"}
        repo = repo.resolve()
        patch = (rd / "patch.diff").read_text()
        if patch.strip() and sb.sh(["git", "apply", "--whitespace=nowarn", str(rd / "patch.diff")], repo).returncode:
            return {**rec, "excluded": "patch did not apply"}
        own = norm(str(envsetup._project_name(repo) or ""))
        keep = [l for l in (rd / "pipfreeze_agent.txt").read_text().splitlines()
                if l and not l.startswith("-e") and " @ " not in l and not l.lower().startswith("pip==") and not (own and norm(re.split(r"[=<>!~ \[]", l, maxsplit=1)[0]) == own)]
        (repo / ".agentvow-freeze.txt").write_text("\n".join(keep) + "\n")
        rcp = recipe_mod.parse({"schema": "agentvow-recipe/1", "setup": ["pip install -r .agentvow-freeze.txt"], "test": "pytest -q", "env": {}})
        t = time.time()
        py, notes, aborted = recipe_mod.build_env(repo, rcp, tmp / "venv", tmp / "home")
        rec["env_build_s"] = round(time.time() - t, 1)
        if not py or aborted:
            return {**rec, "excluded": f"environment not built ({aborted or '; '.join(notes)[:80]})"}
        targets = task["target_files"]
        pp = ":".join([f"{repo}/src", str(repo), *[str(repo / x) for x in rcp.local_roots]])
        inner = ["env", f"HOME={scratch}/h", f"TMPDIR={scratch}/t", "PYTHONDONTWRITEBYTECODE=1", f"PYTHONPATH={pp}", py, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *targets]
        cmd = shlex.join(runner.wrap(inner, repo, scratch))
        secs = []
        for i in (1, 2):
            t = time.time(); b = sh(cmd, repo, 300, shell=True); secs.append(time.time() - t)
            if b.returncode != 0:
                return {**rec, "excluded": f"baseline run {i} did not pass (rc {b.returncode}); flaky or environment-dependent", "baseline_output": (b.stdout + b.stderr)[-500:]}
        t0 = sum(secs) / 2; rec["baseline_s"] = round(t0, 1)
        timeout = max(10, int(5 * t0))
        # coverage of the target tests (coverage is installed for this step only)
        rc_, df = tmp / "empty.rc", repo / ".agentvow" / "cov"
        rc_.write_text("[run]\n"); df.parent.mkdir(parents=True, exist_ok=True)
        had_coverage = subprocess.run([py, "-c", "import coverage"], capture_output=True).returncode == 0   # the captured environment may already contain it (for example through pytest-cov): then it must stay
        if not had_coverage:
            envsetup._pip(tmp / "venv", repo, tmp / "home", ["install", "-q", "coverage"], 300, envsetup.MAX_VENV, envsetup.MIN_FREE)
        t = time.time()
        cov_argv = changedcov.coverage_argv([py, "-m", "pytest", "-q", "-p", "no:cacheprovider", *targets], str(rc_), str(df))
        cres = runner.run_tests(repo, cov_argv, write=False, timeout=600)
        ex = sh(runner.wrap([py, "-m", "coverage", "json", "--rcfile", str(rc_), "--data-file", str(df), "-o", str(scratch / "cov.json")], repo, scratch=scratch, env=os.environ), repo, 120)
        try:
            cov = json.loads((scratch / "cov.json").read_text())
        except (OSError, ValueError):
            cov = None
            rec["coverage_export_error"] = (ex.stdout + ex.stderr)[-300:]
        rec["coverage_s"] = round(time.time() - t, 1)
        if not had_coverage:
            envsetup._pip(tmp / "venv", repo, tmp / "home", ["uninstall", "-y", "coverage"], 120, envsetup.MAX_VENV, envsetup.MIN_FREE)
        rec["coverage_preinstalled"] = had_coverage
        files_cov = (cov or {}).get("files", {})
        by_rel = {}
        for k, v in files_cov.items():
            try:
                by_rel[str(Path(k).resolve().relative_to(repo))] = v
            except ValueError:
                by_rel[k] = v
        if cres.get("result") != "pass" or cov is None:
            rec["coverage_note"] = f"coverage run {cres.get('result')}; executed-line labels unavailable"
            rec["coverage_run_summary"] = str(cres.get("summary"))[:300]
        # enumerate and sample
        cands = []
        dbs = {}
        for f, lines in added_by_file(patch).items():
            if not (repo / f).is_file():
                continue
            cfgp, db = tmp / f"{abs(hash(f))}.toml", tmp / f"{abs(hash(f))}.sqlite"
            cfgp.write_text(f'[cosmic-ray]\nmodule-path = {json.dumps(f)}\ntimeout = {float(timeout)}\nexcluded-modules = []\ntest-command = {json.dumps(cmd)}\n\n[cosmic-ray.distributor]\nname = "local"\n')
            p = sh([CR, "init", str(cfgp), str(db)], repo, 300)
            if p.returncode:
                continue
            c = sqlite3.connect(db)
            for jid, row, op, occ in c.execute("select job_id, start_pos_row, operator_name, occurrence from mutation_specs"):
                if row in lines:
                    cands.append({"file": f, "line": row, "operator": op, "occurrence": occ, "job_id": jid})
            c.close(); dbs[f] = (cfgp, db)
        rec["candidates_enumerated"] = len(cands)
        chosen = sample(cands, f"{stage}|{r['repo']}|{r['pr']}")
        rec["sampled"] = len(chosen)
        if not chosen:
            return {**rec, "mutants": [], "note": "no candidate mutants on the added lines"}
        keepids = {c["job_id"] for c in chosen}
        for f, (cfgp, db) in dbs.items():
            c = sqlite3.connect(db)
            ids = [j for (j,) in c.execute("select job_id from mutation_specs") if j not in keepids]
            for j in ids:
                c.execute("delete from work_items where job_id = ?", (j,)); c.execute("delete from mutation_specs where job_id = ?", (j,))
            c.commit(); c.close()
        results, t_mut = [], time.time()
        for f, (cfgp, db) in dbs.items():
            mine = [c for c in chosen if c["file"] == f]
            if not mine:
                continue
            before = (repo / f).read_bytes()
            bl = sh([CR, "baseline", str(cfgp)], repo, 300)
            if bl.returncode != 0:
                return {**rec, "excluded": f"cosmic-ray baseline failed for {f}", "mutants": [], "baseline_output": (bl.stdout + bl.stderr)[-700:]}
            remaining = RUN_SECONDS - (time.time() - t_run)
            if remaining < 30:
                rec["time_cap_hit"] = True; break
            sh([CR, "exec", str(cfgp), str(db)], repo, int(remaining))
            if (repo / f).read_bytes() != before:
                (repo / f).write_bytes(before); rec["file_restored_by_harness"] = True
            dump = sh([CR, "dump", str(db)], repo, 60).stdout.splitlines()
            out = {}
            for line in dump:
                try:
                    wi, wr = json.loads(line)
                except ValueError:
                    continue
                out[wi["job_id"]] = wr
            for c in mine:
                wr = out.get(c["job_id"])
                if wr is None:
                    results.append({**c, "outcome": "not_run"}); continue
                to, wo = str(wr.get("test_outcome")).lower(), str(wr.get("worker_outcome")).lower()
                outcome = "timeout" if "timeout" in wo or "timeout" in to else ("incompetent" if "incompetent" in to else ("killed" if "killed" in to else ("survived" if "survived" in to else f"other:{wo}/{to}")))
                v = by_rel.get(f)
                sl = stmt_line(repo / f, c["line"])   # coverage records a statement by its FIRST line: map the mutated line to its enclosing statement
                ex_l, mi_l = (v.get("executed_lines", []), v.get("missing_lines", [])) if v else ([], [])
                results.append({**c, "outcome": outcome, "stmt_line": sl, "executed": bool(v) and sl in ex_l, "executable": bool(v) and (sl in ex_l or sl in mi_l), "line_executed_raw": bool(v) and c["line"] in ex_l})
        rec["mutation_s"] = round(time.time() - t_mut, 1)
        # survivor diffs (for review): apply on a copy, diff, restore
        for m in results:
            if m["outcome"] == "survived":
                f = repo / m["file"]; orig = f.read_bytes()
                sh([CR, "apply", m["file"], m["operator"], str(m["occurrence"])], repo, 60)
                new = f.read_text(errors="replace").splitlines(); f.write_bytes(orig)
                old = orig.decode(errors="replace").splitlines()
                i = m["line"] - 1
                m["original_line"] = old[i].strip()[:200] if i < len(old) else ""
                m["mutated_line"] = new[i].strip()[:200] if i < len(new) else ""
                m["context"] = [l[:160] for l in old[max(0, i - 3): i + 4]]
        for m in results:
            m.pop("job_id", None)
        rec["mutants"] = results
        rec["total_s"] = round(time.time() - t_run, 1)
        return rec
    finally:
        if os.environ.get("MUT_KEEP"):   # diagnostics only: keep the working directory
            print("kept:", tmp, scratch, flush=True)
        else:
            shutil.rmtree(tmp, ignore_errors=True); shutil.rmtree(scratch, ignore_errors=True)


def main(limit=999):
    done = {(j["stage"], j["repo"], j["pr"]) for j in map(json.loads, OUT.read_text().splitlines())} if OUT.exists() else set()
    n, t_all = 0, time.time()
    for stage in STAGES:
        rows = [json.loads(l) for l in (D / f"{stage}_results.jsonl").read_text().splitlines() if l.strip()]
        tasks = {(j["repo"], j["pr"]): j for j in map(json.loads, (D / f"{stage}_tasks.jsonl").read_text().splitlines())}
        yf = D / ("mutation_yield.jsonl" if stage == "stageb6" else f"mutation_yield_{stage}.jsonl")
        yld = {(j["repo"], j["pr"]): j for j in map(json.loads, yf.read_text().splitlines())}
        for r in rows:
            k = (r["repo"], r["pr"])
            y = yld.get(k)
            only = os.environ.get("MUT_ONLY")   # diagnostics only: "stageb3,fgmacedo/python-statemachine,533"
            if only and only != f"{stage},{k[0]},{k[1]}":
                continue
            if not (r.get("truth_in_agent_env") == "pass" and r.get("base_fails_in_agent_env")) or (stage, *k) in done or n >= limit:
                continue
            if not y or "candidates" not in y or y["candidates"] == 0:
                OUT.open("a").write(json.dumps({"stage": stage, "repo": k[0], "pr": k[1], "excluded": (y or {}).get("skipped") or "no candidate mutants on the added lines (enumeration)"}) + "\n")
                continue
            if time.time() - t_all > 8 * 3600:
                print("total wall-clock cap reached", flush=True); return
            if shutil.disk_usage(D).free < 4 * 1024**3:
                print("disk low; stopping", flush=True); return
            res = process(stage, r, tasks[k], y); n += 1
            OUT.open("a").write(json.dumps(res) + "\n")
            ms = res.get("mutants") or []
            print(f"[{n}] {stage} {k[0]}#{k[1]}: " + (res.get("excluded") or f"{len(ms)} mutants " + str({o: sum(m['outcome'] == o for m in ms) for o in sorted({m['outcome'] for m in ms})}) + f" in {res.get('total_s')}s"), flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 999)
