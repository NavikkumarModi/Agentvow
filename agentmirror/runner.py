"""Test-run collector: execute a project's tests at the checked-out commit and record evidence.

Safety: the test command runs under macOS `sandbox-exec` with network denied and file writes limited
to the repo, temp dirs and /dev. Install steps (which need the network) are the caller's job and
happen before, outside the sandbox. Evidence is bound to the commit and marked as produced by a
separate tool (not the agent).
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from . import reality as R

_PYTEST = re.compile(r"(\d+) (passed|failed|skipped|errors?|xfailed|xpassed|deselected)")
_UNITTEST_RAN = re.compile(r"Ran (\d+) tests? in")
_UNITTEST_FAIL = re.compile(r"FAILED \((.*?)\)")
_UNITTEST_SKIP = re.compile(r"skipped=(\d+)")
_FAILED_ID = re.compile(r"^(?:(?:FAIL|ERROR): (.+)|(?:FAILED|ERROR) (\S+))", re.M)


_PASSED_ID = re.compile(r"^(?:(.+?) \.\.\. ok(?: \(.*\))?|PASSED (\S+))\s*$", re.M)


def failed_ids(output: str) -> list:
    found = ((a or b).strip() for a, b in _FAILED_ID.findall(output))
    return sorted({x for x in found if not x.startswith("(")})  # skip the "FAILED (failures=…)" summary line


_UNITTEST_ID = re.compile(r"\w+ \([\w.]+\)")
_PASSED_DOC = re.compile(r"^(\w+ \([\w.]+\))\n[^\n]*? \.\.\. ok(?: \(.*\))?\s*$", re.M)  # unittest -v prints the docstring, not the id


def passed_ids(output: str) -> list:
    """Needs verbose output: unittest -v, or pytest -rA."""
    found = {b.strip() for a, b in _PASSED_ID.findall(output) if b}                      # pytest -rA: PASSED path::test
    found |= {a.strip() for a, b in _PASSED_ID.findall(output) if a and _UNITTEST_ID.fullmatch(a.strip())}  # unittest -v
    found |= {m.strip() for m in _PASSED_DOC.findall(output)}
    return sorted(x for x in found if not x.startswith("(") and "\n" not in x)


_FAILED_MODULE = re.compile(r"_FailedTest\.([\w.]+)\)$")


def module_of_failure(failed_id: str):
    """Return the module/file a module-level failure (import or syntax error, collection error) belongs to, else None."""
    m = _FAILED_MODULE.search(failed_id)
    if m:
        return ("py", m.group(1))
    if re.fullmatch(r"[\w./-]+\.py", failed_id):  # pytest collection error: 'ERROR tests/test_x.py'
        return ("file", failed_id)
    return None


def classify_failures(ids: list, base_passed: list, base_failed: list):
    """-> (regressions, uncomparable). A module-level failure is a regression if that module had passing tests at base."""
    bp, bf = set(base_passed), set(base_failed)
    reg = unc = 0
    for i in ids:
        mod = module_of_failure(i)
        if mod:
            kind, name = mod
            had = any((x.split("(")[-1].rstrip(")") + ".").startswith(name + ".") for x in bp) if kind == "py" \
                else any(x.startswith(name + "::") for x in bp)
            had_fail = any((x.split("(")[-1].rstrip(")") + ".").startswith(name + ".") for x in bf) if kind == "py" \
                else any(x.startswith(name + "::") for x in bf)
            if had:
                reg += 1
            elif not had_fail:
                unc += 1
        elif i in bp:
            reg += 1
        elif i not in bf:
            unc += 1
    return reg, unc


_MISSING_MOD = re.compile(r"No module named '([\w]+)")
_HINT = re.compile(r"^(?:E\s+)?(?:\w*(?:Error|Exception)\b.*|ERROR: .*|error: .*|.*unrecognized arguments.*|.*fixture '.*' not found.*)$", re.M)


def error_hint(output: str) -> str:
    m = _HINT.search(output)
    return " ".join(m.group(0).split())[:160] if m else ""


def repo_local_names(repo: Path) -> set:
    names = set()
    for base in (repo, repo / "src", repo / "lib"):
        if base.is_dir():
            names |= {x.stem for x in base.iterdir() if x.suffix == ".py" or x.is_dir()}
    return names


_SECRET_DIRS = (".ssh", ".aws", ".gnupg", ".config/gh", ".config/gcloud", ".docker", ".kube", ".claude", ".copilot", ".codex", ".npmrc", ".netrc",
                ".pypirc", ".git-credentials", "Library/Keychains")


def _deny_reads() -> str:
    """Reads are allowed by default (Python and tools need the system), but never of the signing key or common credential stores."""
    home = Path.home()
    key = Path(os.environ.get("AGENTMIRROR_HOME", home / ".agentmirror"))
    targets = {os.path.realpath(t) for t in (key, *(home / d for d in _SECRET_DIRS))}   # the sandbox matches canonical paths (/var -> /private/var)
    return "".join(f'(deny file-read* (subpath "{t}"))(deny file-read* (literal "{t}"))' for t in sorted(targets))


def _profile(repo: Path, scratch: Path | None = None) -> str:
    """Tests: network denied; writes only inside the worktree and one private scratch directory (HOME and TMPDIR), /dev; no reads of the key or credentials."""
    extra = f' (subpath "{os.path.realpath(scratch)}")' if scratch else ""
    return f'(version 1)(allow default)(deny network*){_deny_reads()}(deny file-write*)(allow file-write* (subpath "{repo}"){extra} (subpath "/dev"))'


def profile_with_network(writable: list) -> str:
    """For installs only: network allowed, writes restricted to the given paths (they should include the install's own TMPDIR)."""
    allowed = " ".join(f'(subpath "{p}")' for p in [*map(str, writable), "/dev"])
    return f"(version 1)(allow default){_deny_reads()}(deny file-write*)(allow file-write* {allowed})"


def _run_group(cmd: list, cwd: Path, env: dict, timeout: int):
    """Run in its own process group and, on timeout, kill the WHOLE group: tests that start daemons (gpg-agent, servers) must not leak them."""
    proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        so, se = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        for kill in (lambda: os.killpg(proc.pid, 9), proc.kill):
            try:
                kill()
                break
            except (PermissionError, ProcessLookupError):
                continue
        proc.communicate()
        raise
    return so + "\n" + se, proc.returncode


def _require_sandbox():
    if shutil.which("sandbox-exec") is None:
        raise RuntimeError("running tests needs the macOS sandbox (sandbox-exec); refusing to run repository code unsandboxed on this platform")


def isolation_problem(repo: Path, argv: list, env: dict, scratch: Path | None = None):
    """The tests must import the project from THIS worktree. An editable install of another checkout would make the base run test the head's code
    (hiding every regression). Returns a description of the problem, or None."""
    py = next((a for a in argv if os.path.basename(a).startswith("python")), None)
    if not py:
        return None
    skip = ("test", "tests", "conftest", "setup", "docs", "doc", "examples", "scripts", "benchmarks", "tools")
    names = sorted(n for n in repo_local_names(repo) if n.isidentifier() and not n.startswith(skip) and not n.startswith("_"))[:6]
    if not names:
        return None
    code = "import importlib.util,sys\nfor n in sys.argv[1:]:\n    s = importlib.util.find_spec(n)\n    print(n + '\\t' + str(getattr(s, 'origin', None) or ''))\n"
    try:
        p = subprocess.run(["sandbox-exec", "-p", _profile(repo, scratch), py, "-c", code, *names], cwd=repo, env=env, capture_output=True, text=True, timeout=60)
    except (subprocess.TimeoutExpired, OSError):
        return None
    here = os.path.realpath(repo) + os.sep
    for line in p.stdout.splitlines():
        n, _, origin = line.partition("\t")
        if origin and origin not in ("None", "built-in", "frozen") and not os.path.realpath(origin).startswith(here):
            return f"the environment imports '{n}' from {origin}, outside this worktree (an editable install of another checkout?)"
    return None


def parse_counts(output: str) -> dict:
    counts = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}
    ran_all = _UNITTEST_RAN.findall(output)
    m = ran_all[-1] if ran_all else None  # the real summary is the last one; test output may print look-alike lines earlier
    if m:  # unittest
        total = int(m)
        failed = errors = skipped = 0
        f = _UNITTEST_FAIL.search(output)
        if f:
            for part in f.group(1).split(","):
                k, _, v = part.strip().partition("=")
                if k == "failures":
                    failed = int(v)
                elif k == "errors":
                    errors = int(v)
        sk = _UNITTEST_SKIP.search(output)
        skipped = int(sk.group(1)) if sk else 0
        return {"passed": max(total - failed - errors - skipped, 0), "failed": failed, "skipped": skipped, "errors": errors}
    lines = [l for l in output.strip().splitlines() if l.strip()]
    summary = [l for l in lines if re.search(r" in [\d.]+s\b", l) and _PYTEST.search(l)]
    tail = summary[-1] if summary else "\n".join(lines[-3:])  # only the real summary line; pytest repeats "1 error" in an earlier banner
    for n, kind in _PYTEST.findall(tail):
        kind = "errors" if kind.startswith("error") else kind
        if kind in counts:
            counts[kind] += int(n)
    return counts


def run_tests(repo: Path, argv: list[str], timeout: int = 600, env_extra: dict | None = None,
              baseline_failed: list | None = None, baseline_passed: list | None = None, write: bool = True, suite: str = "", subdir: str = "",
              base_repo: Path | None = None) -> dict:
    """Run `argv` in `repo` (already checked out); write evidence JSON; return the record.

    Differential rule (avoids false alarms from environment limits such as a missing network):
      * regression = fails now AND passed at the base commit -> can contradict a claim
      * known-failing = failed at base too -> pre-existing or environmental
      * uncomparable = fails now but did not exist at base (new or renamed test) -> cannot be judged"""
    snap = R.snapshot(repo)
    # HOME must be inside a path the sandbox lets tests write to (tests often write caches/config to $HOME). It lives under the
    # (throwaway) worktree's .agentmirror/, which is excluded from status and from the tree hash.
    _require_sandbox()
    repo = Path(repo).resolve()
    # HOME and TMPDIR must be SHORT paths (macOS limits unix-socket paths to 104 chars; gpg-agent and others hang otherwise) and writable: one private
    # scratch directory directly under /private/tmp, the only writable place besides the worktree; removed afterwards.
    scratch = Path(tempfile.mkdtemp(prefix="am", dir="/private/tmp"))
    (scratch / "h").mkdir()
    (scratch / "t").mkdir()
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(scratch / "h"), "TMPDIR": str(scratch / "t"),
           "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": f"{repo / 'src'}:{repo}", **(env_extra or {})}  # this worktree's code wins over any installed copy
    try:
        return _run_tests(repo, argv, timeout, env, scratch, baseline_failed, baseline_passed, write, suite, subdir, base_repo, snap, started := time.time())
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def _run_tests(repo, argv, timeout, env, scratch, baseline_failed, baseline_passed, write, suite, subdir, base_repo, snap, started):
    code = None
    if not (repo / subdir).is_dir():  # e.g. a suite folder that is new in this change: no baseline exists
        return {"commit": snap.commit, "tree": snap.tree, "suite": suite, "subdir": subdir, "result": "inconclusive", "counts": {},
                "summary": f"directory '{subdir}' does not exist at this commit", "failed_ids": [], "passed_ids": []}
    problem = isolation_problem(repo, argv, env, scratch)
    if problem:
        return {"commit": snap.commit, "tree": snap.tree, "suite": suite, "subdir": subdir, "result": "inconclusive", "counts": {},
                "summary": "isolation failure: " + problem, "failed_ids": [], "passed_ids": [], "hint": ""}
    try:
        out, code = _run_group(["sandbox-exec", "-p", _profile(repo, scratch), *argv], repo / subdir, env, timeout)
        counts = parse_counts(out)
        ids, ok_ids = failed_ids(out), passed_ids(out)
        if not any(counts[k] for k in ("passed", "failed", "errors")) and (ok_ids or ids):
            # no summary line (e.g. the project's config makes pytest extra quiet): fall back to the per-test lines
            mod_level = [i for i in ids if module_of_failure(i)]
            counts = {"passed": len(ok_ids), "failed": len(ids) - len(mod_level), "skipped": counts["skipped"], "errors": len(mod_level)}
        ran = sum(counts.values())
        if code == 0 and ran:
            result = "pass"
        elif counts["failed"] or counts["errors"]:
            result = "fail" if (counts["passed"] or counts["failed"]) else "inconclusive"
        else:
            result = "inconclusive"
        summary = f"exit {code}; " + (out.strip().splitlines()[-1] if out.strip() else "no output")
        hint = error_hint(out) if result != "pass" else ""
        # A module that is not part of this repo cannot be imported: the environment (built for another commit) lacks a dependency.
        # That is an environment limit, never evidence about the agent's change.
        local = repo_local_names(repo) | (repo_local_names(base_repo) if base_repo else set())  # a module that existed at base (renamed/removed) is a regression, not a missing dependency
        env_missing = sorted(m for m in set(_MISSING_MOD.findall(out)) if m not in local)
        if env_missing and result != "pass" and not counts.get("passed"):
            result, summary = "inconclusive", f"missing dependency in AgentMirror's environment: {', '.join(env_missing[:4])} (pass --python with the project's virtualenv, or use --setup auto)"
            baseline_failed = baseline_passed = None
    except subprocess.TimeoutExpired:
        counts, ids, ok_ids, result, summary, hint = {}, [], [], "inconclusive", f"timeout after {timeout}s", ""
    if counts and baseline_failed is not None and baseline_passed is not None:
        counts["regressions"], counts["uncomparable"] = classify_failures(ids, baseline_passed, baseline_failed)
        if not baseline_passed:
            counts["no_baseline"] = 1  # the suite did not run (or ran nothing) at base: nothing here is attributable to the change
        # tests that passed at base but are not reported as passing or failing now were deleted, renamed, skipped or never ran
        counts["missing"] = len(set(baseline_passed) - set(ok_ids) - set(ids)) if ok_ids or ids else len(baseline_passed)
        if baseline_passed and not ok_ids and not ids and not any(counts.get(k, 0) for k in ("passed", "failed", "errors")) and code not in (0, None):
            # the suite ran at base but cannot run at all now (e.g. an import error aborts collection): every base test is lost
            counts["errors"], counts["regressions"] = 1, len(baseline_passed)
            summary += " [suite cannot run at this state although it ran at base]"
        if counts.get("regressions") and result == "inconclusive":
            result = "fail"
    rec = ({
        "commit": snap.commit, "tree": snap.tree, "suite": suite, "subdir": subdir, "result": result, "counts": counts, "summary": summary[:200],
        "command": " ".join(argv), "produced_by": "agentmirror-runner", "duration_s": round(time.time() - started, 1),
        "network": "denied", "env": "agentmirror venv; may differ from project CI", "failed_ids": ids, "passed_ids": ok_ids, "hint": hint})
    if write:
        R.safe_write(repo, Path(".agentmirror") / "evidence" / f"testrun_{snap.commit[:10]}.json", json.dumps(R.sign_record(rec)))
    return rec


def run_pair(repo: Path, base: str, head: str, argv: list[str], timeout: int = 600) -> dict:
    """Run at `base` (not recorded as evidence) then at `head` (recorded), comparing failing test ids."""
    subprocess.run(["git", "-C", str(repo), "checkout", "-q", "-f", "--detach", base], check=True)
    b = run_tests(repo, argv, timeout, write=False)
    subprocess.run(["git", "-C", str(repo), "checkout", "-q", "-f", "--detach", head], check=True)
    return run_tests(repo, argv, timeout, baseline_failed=b["failed_ids"], baseline_passed=b["passed_ids"])
