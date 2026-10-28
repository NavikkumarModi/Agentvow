"""Draw the held-out sample for the audit study (docs/research/AUDIT_STUDY_PREREG.md, sections 2 and 3). Deterministic given the seed, the corpus files and the checker commit: nothing here calls the network,
runs repository code or looks at a verdict. It only reads the AIDev tables, runs the frozen statement extractor on each description, removes every pull request used in development, and draws per stratum.

Strata: agent x repository primary language (Python / other), the proxy fixed in the pre-registration (the changed files' languages are not in the corpus). Order inside a stratum is a seeded shuffle of the sorted
candidate list; `rank` is that order, so a pull request that cannot be fetched is replaced by the next rank of the same stratum and nothing else (the replacement rule). Caps: at most `--max-per-repo` per
repository, and no agent above `--max-agent-share` of the final sample.
Usage: python3 research/audit/draw.py --seed N --out data/audit/sample.json [--target-prs 240] [--max-per-repo 3] [--max-agent-share 0.4] [--python-share 0.5] [--exclude FILE ...]
Refuses to run without --seed (no default: the seed is written in the freeze record before the draw) and prints a warning when the working tree is not clean."""
import argparse
import collections
import hashlib
import json
import random
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from agentvow import claims  # noqa: E402

DATA = ROOT / "data"
RULES_VERSION = "draw-v1"
PYTHON = "Python"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pr_url(repo: str, number) -> str:
    return f"https://github.com/{repo}/pull/{int(number)}"


def development_urls(extra_files=()) -> set:
    """Every pull request used to build or tune anything (precision rounds, B6, detection and CI studies, experiments), plus any extra exclusion files (JSON lists of pull-request URLs)."""
    out = set()
    ce = DATA / "checker_eval"
    for name in ("seen_prs.json", "dev_prs.json"):
        p = ce / name
        if p.exists():
            out |= set(json.loads(p.read_text()))
    for p in sorted(ce.glob("*.jsonl")) + sorted((DATA / "preconditions").glob("*.jsonl")) + sorted(DATA.glob("*.jsonl")):
        try:
            for line in p.read_text().splitlines():
                if not line.strip():
                    continue
                try:
                    j = json.loads(line)
                except ValueError:
                    continue
                if isinstance(j.get("pr"), str) and j["pr"].startswith("https://"):
                    out.add(j["pr"])
                elif j.get("repo") and isinstance(j.get("pr"), int):
                    out.add(pr_url(j["repo"], j["pr"]))
        except OSError:
            continue
    for p in sorted(DATA.glob("*.csv")):
        try:
            df = pd.read_csv(p, usecols=lambda c: c in ("repo", "pr"))
        except (ValueError, OSError):
            continue
        if {"repo", "pr"} <= set(df.columns):
            out |= {pr_url(r, n) for r, n in zip(df.repo, df.pr) if isinstance(r, str) and pd.notna(n)}
    for f in extra_files:
        out |= set(json.loads(Path(f).read_text()))
    return out


def population(exclude: set):
    d = pd.read_parquet(DATA / "aidev" / "pull_request.parquet", columns=["number", "body", "agent", "html_url", "repo_id"])
    r = pd.read_parquet(DATA / "aidev" / "repository.parquet", columns=["id", "full_name", "language"])
    d = d[d.body.notna() & d.html_url.fillna("").str.contains("github.com/")].copy()
    d = d.merge(r, left_on="repo_id", right_on="id", how="left")
    d["excluded"] = d.html_url.isin(exclude)
    n_before = len(d)
    d = d[~d.excluded]
    d["claims"] = d.body.map(lambda b: [c.kind for c in claims.extract(b)])
    d["in_scope"] = d.claims.map(lambda ks: sorted({k for k in ks if k != "unchecked"}))
    d = d[d.in_scope.map(bool)].copy()
    d["lang"] = d.language.map(lambda x: "python" if x == PYTHON else "other")
    d["stratum"] = d.agent + "|" + d.lang
    d["repo"] = d.html_url.map(lambda u: "/".join(u.split("github.com/")[1].split("/")[:2]))
    return d.sort_values("html_url").reset_index(drop=True), n_before


def quotas(pool: dict, target: int, python_share: float) -> dict:
    """Quota per stratum: `python_share` of the target is split equally over the Python strata and the rest over the others; a stratum smaller than its quota gives the surplus to the larger strata of the
    same group (largest remaining pool first, ties by name), so small strata are taken whole and nothing is silently lost."""
    q = {s: 0 for s in pool}
    for group, amount in (("python", round(target * python_share)), ("other", target - round(target * python_share))):
        members = sorted((s for s in pool if s.endswith("|" + group)))
        left = amount
        while left > 0 and any(q[s] < pool[s] for s in members):
            open_ = [s for s in members if q[s] < pool[s]]
            share = max(1, left // len(open_))
            for s in sorted(open_, key=lambda x: (-(pool[x] - q[x]), x)):
                give = min(share, pool[s] - q[s], left)
                q[s] += give
                left -= give
                if left == 0:
                    break
    return q


def draw(d: pd.DataFrame, seed: int, target: int, max_per_repo: int, max_agent_share: float, python_share: float = 0.5):
    """-> (selected rows list, pool size per stratum). Pure function of the inputs."""
    strata = sorted(d.stratum.unique())
    ranked = {}
    for s in strata:
        urls = list(d[d.stratum == s].html_url)
        random.Random(f"{seed}:{s}").shuffle(urls)
        ranked[s] = urls
    by_url = d.set_index("html_url")
    quota = quotas({s: len(v) for s, v in ranked.items()}, target, python_share)
    chosen, repo_count = [], collections.Counter()
    for s in strata:
        got = 0
        for rank, u in enumerate(ranked[s]):
            if got >= quota[s]:
                break
            repo = by_url.loc[u, "repo"]
            if repo_count[repo] >= max_per_repo:
                continue
            repo_count[repo] += 1
            got += 1
            chosen.append((s, rank, u))
    # no agent above the share cap: trim the highest ranks of the over-represented agent
    cap = int(max_agent_share * len(chosen))
    agent_of = lambda s: s.split("|")[0]
    counts = collections.Counter(agent_of(s) for s, _, _ in chosen)
    for a, c in counts.most_common():
        if c > cap:
            mine = sorted((x for x in chosen if agent_of(x[0]) == a), key=lambda x: -x[1])
            for x in mine[: c - cap]:
                chosen.remove(x)
    rows = []
    for s, rank, u in sorted(chosen, key=lambda x: (x[0], x[1])):
        r = by_url.loc[u]
        rows.append({"pr": u, "repo": r.repo, "number": int(r.number), "agent": r.agent, "stratum": s, "rank": rank, "kinds": list(r.in_scope), "n_claims": len(r.claims)})
    return rows, {s: len(v) for s, v in ranked.items()}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--target-prs", type=int, default=240)
    ap.add_argument("--max-per-repo", type=int, default=3)
    ap.add_argument("--max-agent-share", type=float, default=0.4)
    ap.add_argument("--python-share", type=float, default=0.5, help="share of the target drawn from Python repositories (the tests and lint checks only apply there)")
    ap.add_argument("--exclude", action="append", default=[])
    a = ap.parse_args(argv)
    dirty = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "--", "agentvow", "research/audit"], capture_output=True, text=True).stdout.strip()
    if dirty:
        print("WARNING: the checker or the draw script has uncommitted changes; the freeze record needs a clean commit:\n" + dirty, file=sys.stderr)
    commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    exclude = development_urls(a.exclude)
    d, n_before = population(exclude)
    rows, pool = draw(d, a.seed, a.target_prs, a.max_per_repo, a.max_agent_share, a.python_share)
    out = {"rules_version": RULES_VERSION, "seed": a.seed, "checker_commit": commit, "dirty": bool(dirty), "target_prs": a.target_prs, "max_per_repo": a.max_per_repo, "max_agent_share": a.max_agent_share, "python_share": a.python_share,
           "corpus_sha256": {n: sha256(DATA / "aidev" / n) for n in ("pull_request.parquet", "repository.parquet")}, "excluded_development_prs": len(exclude),
           "population_after_exclusion": int(len(d)), "pool_per_stratum": pool, "selected": len(rows), "selected_python": sum(r["stratum"].endswith("|python") for r in rows), "selected_claims": sum(r["n_claims"] for r in rows),
           "selected_per_agent": dict(collections.Counter(r["agent"] for r in rows)), "selected_repos": len({r["repo"] for r in rows}), "sample": rows}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=1))
    print(f"selected {len(rows)} pull requests in {out['selected_repos']} repositories; population {len(d)} after excluding {len(exclude)} development pull requests ({n_before - len(d) + 0} rows removed or out of scope)")
    return out


if __name__ == "__main__":
    main()
