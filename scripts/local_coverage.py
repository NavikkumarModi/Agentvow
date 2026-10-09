"""Can AgentMirror verify agent test claims locally? Coverage + agreement with CI on real PRs (see docs/research/LOCAL_COVERAGE.md).

Per repo: clone, automatic env setup ladder (sandboxed pip: network allowed, writes limited), then per PR: tests at base and head under the
network-denied sandbox, verdict from the real decision logic. Resumable; output data/local_coverage.jsonl.
"""
import json
import os
import re
import subprocess
import sys
import time
import shutil
import tomllib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agentmirror_check import claims, decision, envsetup, reality, runner  # noqa: E402

DATA = ROOT / "data"
REPOS = DATA / "repos2"
VENVS = DATA / "venvs2"
OUT = DATA / "local_coverage.jsonl"
EXTRAS = ("test", "tests", "testing", "dev", "develop")
REQ_FILES = ("requirements.txt", "requirements-dev.txt", "requirements_dev.txt", "requirements-test.txt", "requirements_test.txt",
             "dev-requirements.txt", "test-requirements.txt", "tests/requirements.txt")


MIN_FREE = 2.5 * 1024**3
MAX_VENV = 700 * 1024**2


def free_ok():
    return shutil.disk_usage(DATA).free > MIN_FREE


def dir_size(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
def sh(args, cwd=None, timeout=300, env=None):
    try:
        p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
        return p.returncode, (p.stdout + p.stderr)
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def pip(venv, repo, args, timeout=300):
    """Sandboxed pip with a live size watchdog: kills the install as soon as the environment exceeds MAX_VENV or the disk runs low."""
    env = {"PATH": os.environ["PATH"], "HOME": str(DATA / "home"), "PIP_CACHE_DIR": str(DATA / "pipcache"), "PIP_NO_CACHE_DIR": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1"}
    prof = runner.profile_with_network([venv, repo, DATA / "home", DATA / "pipcache"])
    proc = subprocess.Popen(["sandbox-exec", "-p", prof, str(venv / "bin/pip"), *args], cwd=repo, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, start_new_session=True)
    start = time.time()
    while proc.poll() is None:
        time.sleep(2)
        if time.time() - start > timeout:
            reason = "timeout"
        elif dir_size(venv) > MAX_VENV:
            reason = "environment too heavy"
        elif not free_ok():
            reason = "disk low"
        else:
            continue
        for killer in (lambda: os.killpg(proc.pid, 9), proc.kill):
            try:
                killer()
                break
            except (PermissionError, ProcessLookupError):
                continue
        subprocess.run(["pkill", "-9", "-f", str(venv / "bin/pip")], capture_output=True)  # sandbox-exec's child can outlive its parent
        proc.wait()
        return 125, reason
    out = proc.stdout.read()
    return proc.returncode, out


def setup_env(repo: Path, key: str):
    """Uses the shipped agentmirror_check.envsetup (same ladder and resource guards as `--setup auto`)."""
    py, notes, aborted = envsetup.build_env(repo, VENVS / key, DATA / "home")
    if aborted:
        notes = notes + [aborted]
    return (VENVS / key if py else None), notes


def one_repo(item):
    repo_name, prs = item
    if not free_ok():
        return [{**p, "stage": "skipped_low_disk"} for p in prs]
    try:
        return _one_repo(repo_name, prs)
    except Exception as e:  # one repo must never abort the others
        return [{**p, "stage": "error", "note": f"{type(e).__name__}: {e}"[:200]} for p in prs]
    finally:
        shutil.rmtree(VENVS / repo_name.replace("/", "_"), ignore_errors=True)  # keep disk free: environments are disposable
        shutil.rmtree(DATA / "home" / "tmp", ignore_errors=True)


def _one_repo(repo_name, prs):
    key = repo_name.replace("/", "_")
    repo = REPOS / key
    res = []
    t0 = time.time()
    if not repo.exists():
        rc, out = sh(["git", "clone", "-q", f"https://github.com/{repo_name}.git", str(repo)], timeout=600)
        if rc:
            return [{**p, "stage": "clone_failed", "note": out[-150:]} for p in prs]
    venv, notes = setup_env(repo, key)
    if venv is not None and any("too heavy" in n or "disk low" in n for n in notes):
        return [{**p, "stage": "env_too_heavy", "note": "; ".join(notes)[:200]} for p in prs]
    if venv is None:
        return [{**p, "stage": "env_failed", "note": "; ".join(notes)} for p in prs]
    py = str(venv / "bin/python")
    argv = [py, "-m", "pytest", "-q", "-rA", "-p", "no:cacheprovider"]
    for p in prs:
        r = {**p, "setup_notes": notes, "stage": "?"}
        try:
            n = p["pr"]
            sh(["git", "fetch", "-q", "origin", f"pull/{n}/head"], cwd=repo, timeout=120)
            info = subprocess.run(["gh", "api", f"repos/{repo_name}/pulls/{n}"], capture_output=True, text=True)
            info = json.loads(info.stdout)
            head, base, body = info["head"]["sha"], info["base"]["sha"], info.get("body") or ""
            cl = [c for c in claims.extract(body) if c.kind == "tests_pass"]
            r.update(claimed_counts=[c.count for c in cl], head=head, base=base)
            if sh(["git", "checkout", "-q", "-f", "--detach", head], cwd=repo)[0] or sh(["git", "cat-file", "-e", base], cwd=repo)[0]:
                r["stage"] = "no_commits"; res.append(r); continue
            tmp = DATA / "wt2" / f"{key}_{n}"
            sh(["rm", "-rf", str(tmp)])
            tmp.mkdir(parents=True, exist_ok=True)
            for nm, sha in (("base", base), ("head", head)):
                sh(["git", "worktree", "add", "--detach", "-f", str(tmp / nm), sha], cwd=repo)
            env = {"PYTHONPATH": f"{tmp}/NAME/src:{tmp}/NAME"}
            b = runner.run_tests(tmp / "base", argv, timeout=240, write=False, env_extra={"PYTHONPATH": f"{tmp}/base/src:{tmp}/base"})
            h = runner.run_tests(tmp / "head", argv, timeout=240, write=False, baseline_failed=b["failed_ids"], baseline_passed=b["passed_ids"],
                                 env_extra={"PYTHONPATH": f"{tmp}/head/src:{tmp}/head"})
            ev = repo / ".agentmirror" / "evidence"
            ev.mkdir(parents=True, exist_ok=True)
            (ev / f"testrun_{head[:10]}_0.json").write_text(json.dumps(reality.sign_record(h)))
            d = decision.check(repo, base, body)
            f = next((x for x in d.findings if x.kind == "tests_pass"), None)
            r.update(stage="done", base_result=b["result"], base_counts=b["counts"], head_result=h["result"], head_counts=h["counts"],
                     verdict=f.verdict if f else None, why=(f.why[:200] if f else None), status=d.status,
                     head_summary=h.get("summary"), head_hint=h.get("hint"), base_hint=b.get("hint"))
        except Exception as e:  # report, never hide
            r.update(stage="error", note=f"{type(e).__name__}: {e}"[:200])
        finally:
            for nm in ("base", "head"):
                sh(["git", "worktree", "remove", "--force", str(DATA / "wt2" / f"{key}_{p['pr']}" / nm)], cwd=repo)
        res.append(r)
    for r in res:
        r["repo_seconds"] = round(time.time() - t0)
    return res


def main(workers=1, sample="local_coverage_sample.csv", out="local_coverage.jsonl"):
    global OUT
    OUT = DATA / out
    for d in (REPOS, VENVS, DATA / "home", DATA / "pipcache", DATA / "wt2"):
        d.mkdir(parents=True, exist_ok=True)
    sel = pd.read_csv(DATA / sample)
    done = {(j["repo"], j["pr"]) for j in map(json.loads, OUT.read_text().splitlines())} if OUT.exists() else set()
    by = {}
    for r in sel.itertuples():
        if (r.repo, int(r.pr)) not in done:
            by.setdefault(r.repo, []).append({"repo": r.repo, "pr": int(r.pr), "agent": r.agent, "group": r.group, "ci_outcome": r.outcome})
    print(f"{sum(map(len, by.values()))} PRs in {len(by)} repos to run", file=sys.stderr)
    with ThreadPoolExecutor(workers) as ex, OUT.open("a") as fh:
        for res in ex.map(one_repo, by.items()):
            for r in res:
                fh.write(json.dumps(r) + "\n")
            fh.flush()
            print("done", res[0]["repo"], [r.get("stage") for r in res], file=sys.stderr)


if __name__ == "__main__":
    a = sys.argv[1:]
    main(int(a[0]) if a else 1, *(a[1:3]))
