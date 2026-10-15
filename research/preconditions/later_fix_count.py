"""Feasibility enumeration for a predictive-validity test of mutation survivors: of the lines each valid run's PR ADDED, how many were changed later in the repository's default
branch, and how many of those by commits whose subject looks like a fix? COUNTS ONLY: nothing here is joined to mutant outcomes. Method: the commit M that merged the PR (found as in
scripts/feasibility.py), added lines = the first-parent diff of M, `git blame --reverse M..tip` to see which lines were later changed and by which next commit.
Usage: python3 research/preconditions/later_fix_count.py -> data/preconditions/later_fix_counts.jsonl"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data" / "preconditions"
OUT = D / "later_fix_counts.jsonl"
TESTY = re.compile(r"(^|/)(tests?|testing)(/|$)|(^|/)test_[^/]*\.py$|_test\.py$|(^|/)conftest\.py$")
FIX = re.compile(r"\b(fix(es|ed)?|bug(fix)?|regress(ion)?|revert|hotfix|repair|correct(s|ed)?|resolve[sd]?|patch)\b", re.I)


def git(repo, *a, timeout=300):
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True, timeout=timeout).stdout


def find_merge(repo, number):
    for pat in (rf"\(#{number}\)$", rf"Merge pull request #{number}\b"):
        h = git(repo, "log", "--first-parent", "-E", f"--grep={pat}", "--format=%H", "-n", "1").strip()
        if h:
            return h
    return None


def added_lines(repo, m):
    out, cur = {}, None
    for ln in git(repo, "diff", "-U0", f"{m}^1", m).splitlines():
        mm = re.match(r"^diff --git a/.* b/(.*)$", ln)
        if mm:
            cur = mm.group(1); out.setdefault(cur, set()); continue
        h = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", ln)
        if h and cur:
            s, n = int(h.group(1)), int(h.group(2) or 1); out[cur] |= set(range(s, s + n))
    return {f: s for f, s in out.items() if f.endswith(".py") and not TESTY.search(f)}


def main():
    done = {(j["repo"], j["pr"]) for j in map(json.loads, OUT.read_text().splitlines())} if OUT.exists() else set()
    runs = defaultdict(list)
    for stage in ("stageb3", "stageb4", "stageb5", "stageb6"):
        for r in map(json.loads, (D / f"{stage}_results.jsonl").read_text().splitlines()):
            if r.get("truth_in_agent_env") == "pass" and r.get("base_fails_in_agent_env") and (r["repo"], r["pr"]) not in done:
                runs[r["repo"]].append((stage, r["pr"]))
    for repo_name, items in sorted(runs.items()):
        tmp = Path(tempfile.mkdtemp(prefix="lfix_"))
        try:
            p = subprocess.run(["git", "clone", "-q", f"https://github.com/{repo_name}.git", str(tmp / "r")], capture_output=True, text=True, timeout=1800)
            if p.returncode:
                for stage, pr in items:
                    OUT.open("a").write(json.dumps({"stage": stage, "repo": repo_name, "pr": pr, "skipped": "clone failed"}) + "\n")
                continue
            repo = tmp / "r"
            tip = git(repo, "rev-parse", "HEAD").strip()
            for stage, pr in items:
                m = find_merge(repo, pr)
                rec = {"stage": stage, "repo": repo_name, "pr": pr}
                if not m or subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", m, tip]).returncode:
                    OUT.open("a").write(json.dumps({**rec, "skipped": "merge commit not found on the default branch" if not m else "not an ancestor of the tip"}) + "\n"); continue
                mdate = datetime.fromisoformat(git(repo, "log", "-1", "--format=%cI", m).strip())
                tdate = datetime.fromisoformat(git(repo, "log", "-1", "--format=%cI", tip).strip())
                n_lines = n_changed = n_fix = 0
                for f, lines in added_lines(repo, m).items():
                    if m == tip:
                        n_lines += len(lines); continue
                    bl = git(repo, "blame", "--reverse", "-w", "-M", "--line-porcelain", f"{m}..{tip}", "--", f, timeout=600).splitlines()
                    cur = None
                    meta = {}
                    for ln in bl:
                        h = re.match(r"^([0-9a-f]{40}) (\d+) (\d+)", ln)
                        if h:
                            cur = (h.group(1), int(h.group(3))); continue
                    # porcelain gives sha + final line number for each line; collect (sha, final_lineno)
                    entries = []
                    for ln in bl:
                        h = re.match(r"^([0-9a-f]{40}) (\d+) (\d+)", ln)
                        if h:
                            entries.append((h.group(1), int(h.group(3))))
                    seen = {}
                    for sha, lineno in entries:
                        if lineno in lines:
                            n_lines += 1
                            if sha != tip:
                                n_changed += 1
                                if sha not in seen:
                                    nxt = git(repo, "rev-list", "--reverse", "--ancestry-path", f"{sha}..{tip}", "--", f).split()
                                    subj, dt = ("", None)
                                    if nxt:
                                        subj = git(repo, "log", "-1", "--format=%s", nxt[0]).strip()
                                        dt = datetime.fromisoformat(git(repo, "log", "-1", "--format=%cI", nxt[0]).strip())
                                    seen[sha] = bool(subj and FIX.search(subj) and dt and 0 <= (dt - mdate).days <= 365)
                                n_fix += seen[sha]
                OUT.open("a").write(json.dumps({**rec, "added_lines": n_lines, "changed_later": n_changed, "changed_by_fix_within_1y": n_fix, "days_observable": (tdate - mdate).days}) + "\n")
                print(f"{repo_name}#{pr}: {n_lines} added lines, {n_changed} changed later, {n_fix} by fix-like commits within a year (observable {(tdate - mdate).days} days)", flush=True)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
