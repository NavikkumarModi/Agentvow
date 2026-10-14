"""Join the planted-fault behaviour mutants to changed-line coverage (docs/research/forecast_grounding/MUTATION_VS_COVERAGE_PLAN.md; decision rules fixed there).
No new mutants: for each PR, re-create the clean head, run the suite once under `coverage`, and check whether each stored mutant's line was executed.
Usage: python3 research/preconditions/mutation_vs_coverage.py > data/mutation_vs_coverage.json"""
import csv
import json
import re
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
from agentvow import changedcov, runner  # noqa: E402
from feasibility import find_commit, git  # noqa: E402

COVPY = "/tmp/covenv/bin/python"
DBVENV = str(ROOT / "data/venvs/dbbackup/bin/python")
REPOS = {
    "NewFuture/DDNS": ("NewFuture_DDNS", [COVPY, "-m", "unittest", "discover", "-v", "tests"]),
    "Archmonger/django-dbbackup": ("Archmonger_django-dbbackup", ["env", "DJANGO_SETTINGS_MODULE=tests.settings", DBVENV, "-m", "pytest", "-q", "-rA", "-p", "no:cacheprovider", "tests"]),
}


def code_changing(head, f, ln, a, z):
    """Does the planted flip change the program's AST, or only a comment or a docstring (statement-level string)? Ordinary string literals are NOT blanked: a changed message or key
    can change behaviour a test asserts, so such flips stay behavioural."""
    import ast
    try:
        src = (head / f).read_text(errors="replace")
        lines = src.splitlines(keepends=True)
        mut = list(lines)
        mut[ln - 1] = mut[ln - 1].replace(a, z, 1)
        def norm(text):
            t = ast.parse(text)
            for n in ast.walk(t):
                if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str):
                    n.value.value = ""
            return ast.dump(t, annotate_fields=False)
        return norm(src) != norm("".join(mut))
    except (SyntaxError, ValueError, IndexError):
        return None


def mutants():
    seen = {}
    for v in ("", "_v2", "_v3", "_v4", "_v5"):
        p = ROOT / f"data/planted_faults{v}.csv"
        if not p.exists():
            continue
        for r in csv.DictReader(open(p)):
            if r["fault"] == "behaviour":
                m = re.match(r"(.+?):(\d+) '(.+?)'->'(.+?)'$", r["detail"])
                seen.setdefault((r["repo"], int(r["pr"]), m.group(1), int(m.group(2)), m.group(3), m.group(4)), int(r["oracle_break"]))
    return seen


def main():
    ms = mutants()
    by_pr = defaultdict(list)
    for k, det in ms.items():
        by_pr[(k[0], k[1])].append((k, det))
    out, timing = [], {}
    for (full, num), items in sorted(by_pr.items()):
        d, argv = REPOS[full]
        repo = ROOT / "data/repos" / d
        c = find_commit(repo, num)
        wt = Path(tempfile.mkdtemp(prefix="mutcov_"))
        subprocess.run(["git", "-C", str(repo), "worktree", "add", "--detach", "-f", str(wt / "head"), c], check=True, capture_output=True)
        head = wt / "head"
        try:
            rc, df = wt / "empty.rc", head / ".agentvow" / "cov"
            rc.write_text("[run]\n"); df.parent.mkdir(parents=True, exist_ok=True)
            cargv = changedcov.coverage_argv([a for a in argv], str(rc), str(df)) if argv[0] != "env" else ["env", argv[1], *changedcov.coverage_argv(argv[2:], str(rc), str(df))]
            t = time.time()
            unsandboxed = full.startswith("Archmonger")   # deviation (logged in the plan): django-dbbackup's gpg tests hang inside the macOS test sandbox (gpg-agent cannot start); its small suite runs unsandboxed
            if unsandboxed:
                import os
                try:
                    cp = subprocess.run(cargv, cwd=head, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": f"{head}/src:{head}"}, capture_output=True, text=True, timeout=600, stdin=subprocess.DEVNULL)
                    res = {"result": "pass" if cp.returncode == 0 else "fail", "counts": {"passed": int(re.search(r"(\d+) passed", cp.stdout).group(1)) if re.search(r"(\d+) passed", cp.stdout) else None}}
                except subprocess.TimeoutExpired:
                    res = {"result": "inconclusive", "counts": {}}
            else:
                res = runner.run_tests(head, cargv, write=False)
            secs = round(time.time() - t, 1)
            py = argv[0] if argv[0] != "env" else argv[2]
            cov = changedcov.export_json(py, str(rc), str(df), str(wt / "cov.json"), head, wrap=None if unsandboxed else (lambda a_: runner.wrap(a_, head, scratch=wt, env=__import__("os").environ)))
            files = (cov or {}).get("files", {})
            by_rel = {}
            for k, v in files.items():
                try:
                    by_rel[str(Path(k).resolve().relative_to(head.resolve()))] = v
                except ValueError:
                    by_rel[k] = v
            timing[f"{full}#{num}"] = {"sandboxed": not unsandboxed, "seconds": secs, "result": res.get("result"), "passed": (res.get("counts") or {}).get("passed")}
            for (k, det) in items:
                _, _, f, ln, a, z = k
                v = by_rel.get(f)
                executable = v is not None and (ln in v.get("executed_lines", []) or ln in v.get("missing_lines", []))
                executed = bool(v) and ln in v.get("executed_lines", [])
                src = (head / f).read_text(errors="replace").splitlines()
                out.append({"repo": full, "pr": num, "file": f, "line": ln, "op": f"{a}->{z}", "detected": det, "executed": executed, "file_in_coverage": v is not None, "executable": executable, "kind": {None: "invalid_syntax", False: "comment_or_docstring_only", True: "code_changing"}[code_changing(head, f, ln, a, z)],
                            "source": src[ln - 1].strip()[:110] if 0 < ln <= len(src) else ""})
        finally:
            subprocess.run(["git", "-C", str(repo), "worktree", "remove", "--force", str(head)], capture_output=True)
            import shutil
            shutil.rmtree(wt, ignore_errors=True)
        print(f"done {full}#{num} {timing[f'{full}#{num}']}", file=sys.stderr, flush=True)
    json.dump({"mutants": out, "suite": timing}, sys.stdout, indent=1)


if __name__ == "__main__":
    main()
