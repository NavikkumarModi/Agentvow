"""S0 step 3: can AgentMirror's collectors run on real agent PRs?

For each merged AIDev PR with a strict 'tests pass' claim in the cloned repos, find the merge
commit, check it out, and run `check` with the PR body as the transcript. Static analysis only:
no third-party code is executed. Usage: python3 scripts/feasibility.py
"""
import collections
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agentmirror_check import decision  # noqa: E402

REPOS = {"NewFuture/DDNS": "NewFuture_DDNS", "Archmonger/django-dbbackup": "Archmonger_django-dbbackup",
         "dvershinin/gixy": "dvershinin_gixy", "translate/translate": "translate_translate",
         "QuantEcon/QuantEcon.py": "QuantEcon_QuantEcon.py"}
STRICT = re.compile(r"\b(?:all )?\d+ (?:\w+ )?tests? (?:are )?(?:pass(?:ed|ing)?)\b|\ball tests? pass", re.I)


def git(repo, *a):
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True)


def find_commit(repo, number):
    for pat in (rf"\(#{number}\)$", rf"Merge pull request #{number}\b"):
        r = git(repo, "log", "--all", "-E", f"--grep={pat}", "--format=%H", "-n", "1")
        if r.stdout.strip():
            return r.stdout.strip()
    return None


def main():
    pr = pd.read_parquet(ROOT / "data/aidev/pull_request.parquet")
    rp = pd.read_parquet(ROOT / "data/aidev/repository.parquet").set_index("id")
    rows = []
    for full, d in REPOS.items():
        repo = ROOT / "data/repos" / d
        rid = rp.index[rp["full_name"] == full]
        sub = pr[pr.repo_id.isin(rid) & pr.merged_at.notna() & pr.body.notna() & pr.body.str.contains(STRICT)
                 & pr.agent.isin(["Claude_Code", "Copilot", "Devin"])]
        for _, p in sub.iterrows():
            c = find_commit(repo, int(p.number))
            row = {"repo": full, "pr": int(p.number), "agent": p.agent, "commit": bool(c)}
            if c:
                parents = git(repo, "rev-list", "--parents", "-n", "1", c).stdout.split()[1:]
                git(repo, "checkout", "-q", "--detach", c)
                try:
                    dec = decision.check(repo, parents[0] if parents else f"{c}~1", p.body)
                    row.update(status=dec.status, changed=len(dec.changed),
                               kinds="/".join(sorted({f.verdict for f in dec.findings})))
                except Exception as e:  # report, never hide
                    row.update(status=f"ERROR {type(e).__name__}: {e}"[:80], changed=0, kinds="")
            rows.append(row)
    df = pd.DataFrame(rows)
    print(df.to_string(index=False))
    print("\nresolved to a merge commit:", int(df.commit.sum()), "of", len(df))
    print(collections.Counter(df[df.commit].status).most_common())


if __name__ == "__main__":
    main()
