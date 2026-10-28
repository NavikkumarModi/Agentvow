"""Draw the shadow-experiment pool (pre-registration, section 2). Reuses the frozen draw functions of research/audit/draw.py: development pull requests, the whole audit-study draw (240) and any extra exclusion file are removed,
strata are agent x repository language, at most 6 per repository, no agent above 50%, 30% of the target from Python repositories (the achievable pool under these caps is about 1,050, not 1,200: the in-scope population is dominated by one agent and one stratum). Deterministic given the seed; refuses to run without --seed.
Usage: python3 research/shadow2/pool.py --seed N --out data/shadow2/pool.json [--target 1200]"""
import argparse
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research" / "audit"))
import draw  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--target", type=int, default=1200)
    ap.add_argument("--max-per-repo", type=int, default=6)
    ap.add_argument("--max-agent-share", type=float, default=0.5)
    ap.add_argument("--python-share", type=float, default=0.3)
    a = ap.parse_args(argv)
    exclude = draw.development_urls() | {r["pr"] for r in json.loads((ROOT / "docs/research/audit_sample/sample.json").read_text())["sample"]}
    d, _ = draw.population(exclude)
    rows, pool = draw.draw(d, a.seed, a.target, a.max_per_repo, a.max_agent_share, a.python_share)
    out = {"seed": a.seed, "target": a.target, "max_per_repo": a.max_per_repo, "max_agent_share": a.max_agent_share, "python_share": a.python_share, "excluded": len(exclude), "population": int(len(d)), "pool_per_stratum": pool, "selected": len(rows),
           "per_agent": dict(collections.Counter(r["agent"] for r in rows)), "python_stratum": sum(r["stratum"].endswith("|python") for r in rows), "repos": len({r["repo"] for r in rows}), "sample": rows}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=1))
    print({k: v for k, v in out.items() if k not in ("sample", "pool_per_stratum")})


if __name__ == "__main__":
    main()
