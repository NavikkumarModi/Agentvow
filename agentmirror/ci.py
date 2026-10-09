"""CI evidence: read the project's own check results for the exact commit through the GitHub CLI (read-only GETs).

Only jobs whose names look like test jobs count towards a "tests pass" claim; lint, security scans, title checks, release
automation and similar are reported but ignored. A commit with no CI yields no evidence (never a pass).
"""
import json
import re
import time
import subprocess
from pathlib import Path

from .reality import GIT_SAFE,  Evidence, Snapshot

# v2 (2026-10-07, post-hoc after the RQ4 audit: v1 had 91% precision, 59% recall on 60 blind-judged job names).
# Token-aware (underscores and digits do not hide a word), recognises python-version matrix names, excludes test.pypi.
TEST_JOB = re.compile(r"(?<![a-z])(?:tests?(?!\.pypi)|pytest|pytester|unit|unittests?|integration|tox|nox|specs?)(?![a-z])|^(?:python|py)[ -]?3\.\d+|^\U0001F40D", re.I)
TEST_JOB_V1 = re.compile(r"\b(?:tests?|pytest|unit|unittests?|integration|tox|nox|specs?)\b", re.I)
_IND = {"framing": "separate", "evidence": "separate", "mechanism": "separate", "authority": "unknown"}  # the PR can change the CI configuration


def _gh(path: str):
    r = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None


def _slug(repo: Path):
    r = subprocess.run(["git", *GIT_SAFE, "-C", str(repo), "remote", "get-url", "origin"], capture_output=True, text=True)
    m = re.search(r"github\.com[:/]([\w.-]+/[\w.-]+?)(?:\.git)?$", r.stdout.strip())
    return m.group(1) if m else None


def ci_evidence(repo: Path, snap: Snapshot, fetch=_gh, slug=None, sha=None, wait: int = 0, sleep=time.sleep) -> list:
    """Evidence from CI for HEAD. Not available for uncommitted work (CI never saw it)."""
    if snap.dirty and not sha:
        return []
    sha = sha or snap.commit
    slug = slug or _slug(repo)
    if not slug:
        return []
    deadline = time.time() + wait
    while True:
        data = fetch(f"repos/{slug}/commits/{sha}/check-runs?per_page=100") or {}
        pending = [r for r in data.get("check_runs", []) if TEST_JOB.search(r.get("name", "")) and r.get("status") != "completed"]
        if not pending or time.time() >= deadline:   # test jobs still running right after a push: wait (bounded) instead of reporting "no result"
            break
        sleep(15)
    if data.get("total_count", 0) > len(data.get("check_runs", [])):
        return []  # truncated listing: refuse to draw conclusions from a partial view
    out = []
    for run in data.get("check_runs", []):
        name, status, concl = run.get("name", ""), run.get("status"), run.get("conclusion")
        if not TEST_JOB.search(name) or status != "completed":
            continue
        if concl in ("neutral", "skipped"):
            continue  # a skipped job proves nothing
        ok = concl == "success"
        out.append(Evidence(f"ci_{len(out)}", "ci_check", "github-checks", snap.commit, "", "VALID", _IND,
                            f"ci:{name} ({concl})", f"{'pass' if ok else 'fail'}: {name} {concl}"))
    return out
