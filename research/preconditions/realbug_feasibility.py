"""Feasibility screen of REAL_BUG_PLAN.md section 3. For a seeded sample of BugsInPy bugs: can the buggy and fixed versions be built, and can the pre-existing suite (the tests at the
buggy commit) be run on both? No coverage and no coverage-vs-detection association is computed here. Usage: python3 research/preconditions/realbug_feasibility.py [per_project]"""
import json
import random
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from agentvow import runner  # noqa: E402

META = ROOT / "data" / "bip_meta" / "BugsInPy" / "projects"
CLONES = ROOT / "data" / "bip_clones"
OUT = ROOT / "data" / "preconditions" / "realbug_feasibility.jsonl"
PROJECTS = ["PySnooper", "black", "cookiecutter", "fastapi", "httpie", "luigi", "sanic", "scrapy", "thefuck", "tornado", "tqdm", "youtube-dl"]
PY = "/opt/homebrew/bin/python3.11"
SEED = 20261015
SUITE_CAP, BUILD_CAP = 300, 600


def sh(cmd, cwd=None, timeout=600):
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        return subprocess.CompletedProcess(cmd, 124, "", "timeout")


def info(path):
    d = {}
    for line in Path(path).read_text().splitlines():
        m = re.match(r'(\w+)\s*="?(.*?)"?$', line.strip())
        if m:
            d[m.group(1)] = m.group(2)
    return d


def clone(project, url):
    dest = CLONES / project
    if not dest.exists():
        CLONES.mkdir(parents=True, exist_ok=True)
        r = sh(["git", "clone", "--quiet", "--filter=blob:none", "--no-checkout", url, str(dest)], timeout=900)
        if r.returncode:
            shutil.rmtree(dest, ignore_errors=True)
            return None
    return dest


def run_suite(py, repo, scratch):
    (scratch / "h").mkdir(exist_ok=True); (scratch / "t").mkdir(exist_ok=True)
    inner = ["env", f"HOME={scratch}/h", f"TMPDIR={scratch}/t", "PYTHONDONTWRITEBYTECODE=1", f"PYTHONPATH={repo}:{repo}/src", py, "-m", "pytest", "-q", "--tb=no", "-rfE",
             "--continue-on-collection-errors", "-p", "no:cacheprovider"]
    cmd = runner.wrap(inner, repo, scratch)
    t = time.time()
    try:
        p = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, timeout=SUITE_CAP)
        out, rc, to = p.stdout + p.stderr, p.returncode, False
    except subprocess.TimeoutExpired as e:
        out, rc, to = (e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")), 124, True
    out = re.sub(r"\x1b\[[0-9;]*m", "", out)
    failed = sorted(set(re.findall(r"^(?:FAILED|ERROR) (\S+)", out, re.M)))
    counts = runner.parse_counts(out)
    return {"rc": rc, "timeout": to, "seconds": round(time.time() - t, 1), "failed": failed, "counts": counts, "tail": out[-300:]}


def process(project, bug):
    rec = {"project": project, "bug": bug, "t0": time.strftime("%F %T")}
    meta = META / project / "bugs" / str(bug)
    bi = info(meta / "bug.info"); pinfo = info(META / project / "project.info")
    rec.update(python_required=bi.get("python_version"), test_file=bi.get("test_file"))
    clone_dir = clone(project, pinfo["github_url"])
    if not clone_dir:
        rec["stage"] = "clone failed"; return rec
    tmp = Path(tempfile.mkdtemp(prefix="rbf_")).resolve()
    try:
        bad, fix = bi["buggy_commit_id"], bi["fixed_commit_id"]
        if sh(["git", "cat-file", "-e", bad + "^{commit}"], clone_dir).returncode or sh(["git", "cat-file", "-e", fix + "^{commit}"], clone_dir).returncode:
            if sh(["git", "fetch", "--quiet", "origin", bad, fix], clone_dir, 600).returncode:
                rec["stage"] = "commits not fetchable"; return rec
        rec["commits_ok"] = True
        patch = (meta / "bug_patch.txt").read_text()
        files = re.findall(r"^diff --git a/(\S+) b/", patch, re.M)
        rec["changed_files"] = files
        rec["changed_lines_removed_or_modified"] = sum(1 for l in patch.splitlines() if l.startswith("-") and not l.startswith("---"))
        names = sh(["git", "diff", "--name-only", bad, fix], clone_dir).stdout.split()
        tests_touched = [f for f in names if re.search(r"(^|/)(tests?|testing)(/|_)|_test\.py$|(^|/)test_", f)]
        rec["fix_touches_tests"] = tests_touched[:10]
        wt = tmp / "buggy"
        r = sh(["git", "worktree", "add", "--quiet", "--detach", str(wt), bad], clone_dir, 900)
        if r.returncode:
            rec["stage"] = "checkout failed: " + r.stderr[-200:]; return rec
        # fixed source with the SAME (buggy-commit) tests: apply the bug patch to a copy of the buggy tree
        fixed = tmp / "fixed"
        shutil.copytree(wt, fixed, symlinks=True)
        ap = sh(["git", "apply", "--whitespace=nowarn", str(meta / "bug_patch.txt")], fixed)
        rec["patch_applies"] = ap.returncode == 0
        if ap.returncode:
            rec["stage"] = "bug patch does not apply"; return rec
        req = tmp / "requirements.txt"
        raw = (meta / "requirements.txt").read_bytes() if (meta / "requirements.txt").exists() else b""
        for enc in ("utf-8-sig", "utf-16"):
            try:
                req.write_text(raw.decode(enc)); break
            except UnicodeError:
                continue
        venv = tmp / "venv"
        t = time.time()
        r = sh([PY, "-m", "venv", str(venv)], timeout=120)
        py = str(venv / "bin" / "python")
        ins = sh([py, "-m", "pip", "install", "-q", "--disable-pip-version-check", "pytest", *(["-r", str(req)] if req.exists() and req.read_text().strip() else [])], wt, BUILD_CAP)
        rec["env"] = {"python": "3.11", "install_rc": ins.returncode, "seconds": round(time.time() - t, 1), "err": ins.stderr[-300:] if ins.returncode else ""}
        if ins.returncode:
            # one retry without the pinned file, to separate "pins unusable" from "project unusable"
            ins2 = sh([py, "-m", "pip", "install", "-q", "--disable-pip-version-check", "pytest"], wt, 300)
            rec["env"]["unpinned_fallback"] = "pytest only; project dependencies not installed"
            rec["env"]["pinned_failed"] = True
        scratch = Path(tempfile.mkdtemp(prefix="am", dir=runner.scratch_base())).resolve()
        try:
            rec["suite_buggy"] = run_suite(py, wt, scratch)
            rec["suite_fixed"] = run_suite(py, fixed, scratch)
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
        sb_, sf = rec["suite_buggy"], rec["suite_fixed"]
        rec["failing_only_on_buggy"] = sorted(set(sb_["failed"]) - set(sf["failed"]))[:10]
        rec["failing_only_on_fixed"] = sorted(set(sf["failed"]) - set(sb_["failed"]))[:10]
        passed = sf["counts"].get("passed", 0) if isinstance(sf["counts"], dict) else 0
        rec["feasible"] = bool(not rec["env"]["install_rc"] and not sf["timeout"] and not sb_["timeout"] and sf["rc"] in (0, 1) and sb_["rc"] in (0, 1) and passed >= 1)
        rec["stage"] = "done"
        return rec
    finally:
        sh(["git", "worktree", "prune"], clone_dir)
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    per = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    rng = random.Random(SEED)
    sample = []
    for p in PROJECTS:
        bugs = sorted(int(x.name) for x in (META / p / "bugs").iterdir())
        sample += [(p, b) for b in sorted(rng.sample(bugs, min(per, len(bugs))))]
    done = {(j["project"], j["bug"]) for j in map(json.loads, OUT.read_text().splitlines())} if OUT.exists() else set()
    for p, b in sample:
        if (p, b) in done:
            continue
        if shutil.disk_usage(ROOT).free < 3 * 1024**3:
            print("low disk; stopping", flush=True); return
        try:
            rec = process(p, b)
        except Exception as e:  # recorded, not hidden
            rec = {"project": p, "bug": b, "stage": f"harness error: {type(e).__name__}: {str(e)[:200]}"}
        OUT.open("a").write(json.dumps(rec) + "\n")
        print(p, b, rec.get("stage"), "feasible" if rec.get("feasible") else "", flush=True)


if __name__ == "__main__":
    main()
