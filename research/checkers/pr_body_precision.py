"""Precision of the files / docs / lint statement checkers on real agent pull-request descriptions (AIDev corpus), against each pull request's real list of changed files (GitHub API).
Samples PRs per agent that contain such a statement, runs the extractors and the file/doc checks with the PR's own file list, and writes every verdict for hand review.
Usage: python3 research/checkers/pr_body_precision.py [per_agent=40]   (needs `gh` logged in; caches API answers in data/checker_eval/)"""
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from agentvow import claims, statements  # noqa: E402

CACHE = ROOT / "data" / "checker_eval"
CACHE.mkdir(parents=True, exist_ok=True)
SEED = 20261027


def gh(path, paginate=False):
    key = CACHE / (path.replace("/", "_").replace("?", "_") + ".json")
    if key.exists():
        return json.loads(key.read_text())
    cmd = ["gh", "api", *(["--paginate"] if paginate else []), path]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        key.write_text(json.dumps({"error": p.stderr[:200]}))
        return {"error": p.stderr[:200]}
    txt = p.stdout
    if paginate:   # --paginate concatenates JSON arrays: ][ -> ,
        txt = txt.replace("][", ",")
    out = json.loads(txt)
    key.write_text(json.dumps(out))
    return out


class FakeRepo:
    """Just enough of a repository for statements.check_files: a set of tracked paths."""
    def __init__(self, tree):
        self.tree = set(tree)

    def __truediv__(self, p):
        return _Node(self.tree, str(p))


class _Node:
    def __init__(self, tree, p):
        self.tree, self.p = tree, p

    def exists(self):
        return self.p in self.tree or any(t.startswith(self.p.rstrip("/") + "/") for t in self.tree)

    def is_dir(self):
        return any(t.startswith(self.p.rstrip("/") + "/") for t in self.tree)


def main():
    per = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else SEED
    skip = set(json.loads(Path(sys.argv[3]).read_text())) if len(sys.argv) > 3 else set()
    d = pd.read_parquet(ROOT / "data" / "aidev" / "pull_request.parquet", columns=["number", "body", "agent", "html_url", "state", "merged_at"])
    d = d[d.body.notna() & d.html_url.str.contains("github.com/")].copy()
    d["kinds"] = d.body.map(lambda b: sorted({c.kind for c in claims.extract(b[:20000])} & {"files_scope", "docs_updated", "lint_clean"}))
    d = d[d.kinds.map(bool)]
    d = d[~d.html_url.isin(skip)]
    sample = pd.concat([g.sample(min(per, len(g)), random_state=seed) for _, g in d.groupby("agent")])
    rows = []
    for _, r in sample.iterrows():
        m = r.html_url.split("github.com/")[1].split("/")
        owner, repo, num = m[0], m[1], r.number
        files = gh(f"repos/{owner}/{repo}/pulls/{num}/files?per_page=100", paginate=True)
        if isinstance(files, dict):
            rows.append({"pr": r.html_url, "agent": r.agent, "error": files["error"]}); continue
        changed = sorted({f["filename"] for f in files} | {f["previous_filename"] for f in files if f.get("previous_filename")})
        tree = gh(f"repos/{owner}/{repo}/git/trees/HEAD?recursive=1")
        tracked = [t["path"] for t in tree.get("tree", [])] if isinstance(tree, dict) and "tree" in tree else []
        removed = {f["filename"] for f in files if f.get("status") == "removed"}   # the tree is the default branch today; the file list is the pull request's own
        tracked = [t for t in tracked if t not in removed]
        tracked = sorted(set(tracked) | {f["filename"] for f in files if f.get("status") != "removed"})
        if not files or len(files) >= 3000:   # GitHub returns at most 3000 files: a longer list is cut off and says nothing about absence
            rows.append({"pr": r.html_url, "agent": r.agent, "error": "no changed files returned by GitHub"}); continue
        fake = FakeRepo(tracked)
        statements._tracked = lambda repo_, t=tracked: t
        statements._ignored = lambda repo_, p: False
        for c in claims.extract(r.body[:20000]):
            if c.kind == "files_scope":
                v, why, _ = statements.check_files(fake, changed, c.detail)
            elif c.kind == "docs_updated":
                v, why, _ = statements.check_docs(changed, c.detail)
            elif c.kind == "lint_clean":
                v, why = "(not run)", c.detail["tool"]
            else:
                continue
            rows.append({"pr": r.html_url, "agent": r.agent, "kind": c.kind, "verdict": v, "sentence": c.text[:300], "detail": c.detail, "why": why[:300], "n_changed": len(changed), "tree_truncated": bool(tree.get("truncated")) if isinstance(tree, dict) else None})
    out = ROOT / "data" / "checker_eval" / f"pr_body_precision_{seed}.jsonl"
    out.write_text("\n".join(json.dumps(x) for x in rows))
    import collections
    c = collections.Counter((x.get("kind"), x.get("verdict")) for x in rows if "kind" in x)
    print(len(sample), "PRs;", len(rows), "rows"); [print(k, v) for k, v in sorted(c.items(), key=str)]
    print("errors:", sum(1 for x in rows if "error" in x))


if __name__ == "__main__":
    main()
