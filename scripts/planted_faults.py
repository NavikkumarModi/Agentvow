"""Planted-fault benchmark (pipeline sensitivity only; faults are authored by us, so this is NOT evidence of real-world detection).

For each real merged agent PR (repos where tests run): head = the merge commit, base = its parent. We plant a fault in the
agent's final code, keep the claim "All tests pass", run the tests in a sandbox at base and at the faulty head, and ask the
verdict logic what it says. Oracle (independent of test-id matching): the raw count of passed tests dropped versus the clean head.
Usage: python3 scripts/planted_faults.py > data/planted_faults.csv  (progress on stderr)
"""
import csv
import random
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from agentvow import claims, decision, reality, runner  # noqa: E402
from agentvow.reality import Evidence, Snapshot  # noqa: E402
from feasibility import STRICT, find_commit, git  # noqa: E402

VENV = str(ROOT / "data/venvs/dbbackup/bin/python")
REPOS = {
    "NewFuture/DDNS": ("NewFuture_DDNS", ["python3", "-m", "unittest", "discover", "-v", "tests"]),
    "Archmonger/django-dbbackup": ("Archmonger_django-dbbackup",
                                   ["env", "DJANGO_SETTINGS_MODULE=tests.settings", VENV, "-m", "pytest", "-q", "-rA", "-p", "no:cacheprovider", "tests"]),
}
OPS = [(" == ", " != "), (" != ", " == "), (" < ", " >= "), (" > ", " <= "), ("return True", "return False"),
       ("return False", "return True"), (" and ", " or "), (" in ", " not in ")]
IND = {"framing": "separate", "evidence": "separate", "mechanism": "separate", "authority": "unknown"}
SKIP_NAMES = {"__main__.py", "setup.py", "conftest.py"}


def sh(wt, *a):
    return subprocess.run(["git", "-C", str(wt), *a], capture_output=True, text=True, check=True).stdout


def added_lines(repo, b, c, f):
    out = subprocess.run(["git", "-C", str(repo), "diff", "-U0", b, c, "--", f], capture_output=True, text=True).stdout
    nums = []
    for m in re.finditer(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", out, re.M):
        start, n = int(m.group(1)), int(m.group(2) or 1)
        nums += range(start, start + n)
    return nums


def behaviour_mutants(wt, repo, b, c, files, rng, k=2):
    cands = []
    for f in files:
        src = (wt / f).read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        for ln in added_lines(repo, b, c, f):
            if 0 < ln <= len(src) and not src[ln - 1].lstrip().startswith(("#", '"', "'")):
                for a, z in OPS:
                    if a in src[ln - 1]:
                        cands.append((f, ln, a, z))
    rng.shuffle(cands)
    return cands[:k]


def apply_mut(wt, f, ln, a, z):
    p = wt / f
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    lines[ln - 1] = lines[ln - 1].replace(a, z, 1)
    p.write_text("".join(lines))


def append(wt, f, text):
    with open(wt / f, "a", encoding="utf-8") as fh:
        fh.write("\n" + text + "\n")


def verdict(rec, claim_count):
    ev = Evidence("e", "prior_verification", "runner", rec["commit"], "h", "VALID", IND, "x.json", f'{rec["result"]}: x', suite="", counts=rec["counts"])
    f = decision._tests(claims.Claim(claims.TESTS_PASS, "All tests pass", claim_count), [ev], Snapshot(rec["commit"], False))
    return f.verdict


def main():
    pr = pd.read_parquet(ROOT / "data/aidev/pull_request.parquet")
    rp = pd.read_parquet(ROOT / "data/aidev/repository.parquet")
    w = csv.writer(sys.stdout)
    w.writerow(["repo", "pr", "fault", "detail", "verdict", "regressions", "uncomparable", "passed_clean", "passed_fault", "oracle_break"])
    rng = random.Random(int(sys.argv[1]) if len(sys.argv) > 1 else 11)
    for full, (d, argv) in REPOS.items():
        repo = ROOT / "data/repos" / d
        rid = rp[rp.full_name == full].id
        sub = pr[pr.repo_id.isin(rid) & pr.merged_at.notna() & pr.body.notna() & pr.body.str.contains(STRICT)
                 & pr.agent.isin(["Claude_Code", "Copilot", "Devin"])]
        for _, p in sub.iterrows():
            c = find_commit(repo, int(p.number))
            if not c:
                continue
            b = git(repo, "rev-list", "--parents", "-n", "1", c).stdout.split()[1]
            tmp = ROOT / "data/wt" / f"{d}_{int(p.number)}"
            for name, sha in (("base", b), ("head", c)):
                subprocess.run(["rm", "-rf", str(tmp / name)])
                (tmp).mkdir(parents=True, exist_ok=True)
                sh(repo, "worktree", "add", "--detach", "-f", str(tmp / name), sha)
            wb, wh = tmp / "base", tmp / "head"
            try:
                base = runner.run_tests(wb, argv, write=False)
                files = [f for f in git(repo, "diff", "--name-only", b, c).stdout.split() if f.endswith(".py")
                         and not reality.is_test(f) and Path(f).name not in SKIP_NAMES and (wh / f).exists()]
                clean = runner.run_tests(wh, argv, write=False, baseline_failed=base["failed_ids"], baseline_passed=base["passed_ids"])
                pc = clean["counts"].get("passed", 0)
                variants = [("clean", "", None)]
                for f, ln, a, z in behaviour_mutants(wh, repo, b, c, files, rng):
                    variants.append(("behaviour", f"{f}:{ln} '{a.strip()}'->'{z.strip()}'", lambda f=f, ln=ln, a=a, z=z: apply_mut(wh, f, ln, a, z)))
                if files:
                    f0 = files[0]
                    variants += [("import_break", f0, lambda f0=f0: append(wh, f0, 'raise ImportError("planted fault")')),
                                 ("syntax_break", f0, lambda f0=f0: append(wh, f0, "def (:")),
                                 ("benign_comment", f0, lambda f0=f0: append(wh, f0, "# planted comment"))]
                variants.append(("inflated_count", f"claims {pc + 50}", None))
                for kind, detail, fn in variants:
                    sh(wh, "checkout", "-q", "-f", "--", "."); sh(wh, "clean", "-fdq", "-e", ".agentvow")
                    if fn:
                        fn()
                    rec = clean if kind in ("clean", "inflated_count") else runner.run_tests(
                        wh, argv, write=False, baseline_failed=base["failed_ids"], baseline_passed=base["passed_ids"])
                    cnt = rec["counts"]
                    v = verdict(rec, pc + 50 if kind == "inflated_count" else None)
                    pf = cnt.get("passed", 0) if cnt else 0
                    w.writerow([full, int(p.number), kind, detail, v, cnt.get("regressions"), cnt.get("uncomparable"), pc, pf,
                                int(pf < pc) if kind not in ("clean", "inflated_count") else 0])
                    sys.stdout.flush()
                print(f"done {full} #{int(p.number)}", file=sys.stderr)
            finally:
                for n in ("base", "head"):
                    subprocess.run(["git", "-C", str(repo), "worktree", "remove", "--force", str(tmp / n)], capture_output=True)
    sub = None


if __name__ == "__main__":
    main()
