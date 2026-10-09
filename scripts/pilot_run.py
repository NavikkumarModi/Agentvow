"""Run Agentvow's test-run collector on pool PRs and print what a reviewer would be told.

Usage: python3 scripts/pilot_run.py <owner/repo> [--python /path/to/python] [--limit N]
Tests run under sandbox-exec (network denied). Third-party code executes only inside that sandbox.
"""
import argparse
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from agentvow import decision, runner  # noqa: E402
from feasibility import STRICT, find_commit, git  # noqa: E402

ARGV = {
    "NewFuture/DDNS": ["{py}", "-m", "unittest", "discover", "-v", "tests"],
    "Archmonger/django-dbbackup": ["env", "DJANGO_SETTINGS_MODULE=tests.settings", "{py}", "-m", "pytest", "-q", "-rA", "-p", "no:cacheprovider", "tests"],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--limit", type=int, default=100)
    a = ap.parse_args()
    d = ROOT / "data/repos" / a.repo.replace("/", "_")
    pr = pd.read_parquet(ROOT / "data/aidev/pull_request.parquet")
    rp = pd.read_parquet(ROOT / "data/aidev/repository.parquet")
    rid = rp.index[rp["full_name"] == a.repo]
    rid = rp.loc[rid, "id"]
    sub = pr[pr.repo_id.isin(rid) & pr.merged_at.notna() & pr.body.notna() & pr.body.str.contains(STRICT)
             & pr.agent.isin(["Claude_Code", "Copilot", "Devin"])].head(a.limit)
    argv = [x.format(py=a.python) for x in ARGV[a.repo]]
    for _, p in sub.iterrows():
        c = find_commit(d, int(p.number))
        if not c:
            print(f"PR {int(p.number)}: merge commit not found"); continue
        parents = git(d, "rev-list", "--parents", "-n", "1", c).stdout.split()[1:]
        base = parents[0] if parents else f"{c}~1"
        rec = runner.run_pair(d, base, c, argv, timeout=600)
        dec = decision.check(d, base, p.body)
        f = next((x for x in dec.findings if x.kind == "tests_pass"), None)
        n = rec["counts"]
        print(f"PR {int(p.number):5d} {p.agent:10s} result={rec['result']:12s} passed={n.get('passed')} failed={n.get('failed')} "
              f"err={n.get('errors')} skip={n.get('skipped')} regress={n.get('regressions')} uncomp={n.get('uncomparable')} | verdict={f.verdict if f else '-'} | status={dec.status}")
        if f and f.verdict != "SUPPORTED_BY_PRIOR_EVIDENCE":
            print("      ", f.why[:230])


if __name__ == "__main__":
    main()
