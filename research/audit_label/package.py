"""Build the labelling items for the audit study (A1: labelling agents). One item per pull request: the repository, number and URL, the pull-request message, and the NUMBERED STATEMENTS the frozen extractor found, with
the extractor's kind and verdict removed (the labeller must not see them). Items are ordered by SHA-256(seed|url), so any prefix is a random subsample. No network, no repository code.
Usage: python3 research/audit_label/package.py --sample docs/research/audit_sample/sample.json --out data/audit/items [--urls FILE.json for a harness pilot on development pull requests]"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from agentvow import claims  # noqa: E402


def item_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:10]


def order_key(seed, url: str) -> str:
    return hashlib.sha256(f"{seed}|{url}".encode()).hexdigest()


def build(urls, seed, bodies: dict):
    items = []
    for u in urls:
        body = bodies.get(u)
        if not body:
            continue
        seen, stmts = set(), []
        for c in claims.extract(body):
            if c.text not in seen:
                seen.add(c.text)
                stmts.append({"n": len(stmts) + 1, "text": c.text})
        repo = "/".join(u.split("github.com/")[1].split("/")[:2])
        items.append({"id": item_id(u), "url": u, "repo": repo, "number": int(u.rstrip("/").split("/")[-1]), "message": body[-20000:], "statements": stmts, "order": order_key(seed, u)})
    return sorted(items, key=lambda i: i["order"])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample")
    ap.add_argument("--urls")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if a.sample:
        s = json.loads(Path(a.sample).read_text())
        urls, seed = [r["pr"] for r in s["sample"]], s["seed"]
    else:
        urls, seed = json.loads(Path(a.urls).read_text()), a.seed or 0
    d = pd.read_parquet(ROOT / "data" / "aidev" / "pull_request.parquet", columns=["body", "html_url"])
    bodies = dict(zip(d.html_url, d.body))
    items = build(urls, seed, bodies)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for i, it in enumerate(items):
        (out / f"{i:03d}_{it['id']}.json").write_text(json.dumps(it, indent=1))
    print(f"{len(items)} items, {sum(len(i['statements']) for i in items)} statements -> {out}")


if __name__ == "__main__":
    main()
