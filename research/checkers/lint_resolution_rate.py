"""How many generic lint statements on real agent pull-request descriptions ("lint passes", "formatting checks pass", "pre-commit passes") resolve to a linter Agentvow can run?
Uses the lint rows written by pr_body_precision.py, the PR's file list and the repository's configuration files (GitHub API, default branch today: an approximation of the state at the PR).
Usage: python3 research/checkers/lint_resolution_rate.py   (reads/writes data/checker_eval/)"""
import base64
import collections
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).resolve().parent))
from agentvow import lint  # noqa: E402
import pr_body_precision as P  # noqa: E402

CONFIGS = ["pyproject.toml", "setup.cfg", "tox.ini", ".flake8", "ruff.toml", ".ruff.toml", ".pre-commit-config.yaml"]
ROUNDS = ["pr_body_precision_20261027", "pr_body_precision_777", "pr_body_precision_4242", "pr_body_precision_99", "pr_body_precision_31337"]


def main():
    rows = []
    for r in ROUNDS:
        for l in (ROOT / "data" / "checker_eval" / f"{r}.jsonl").read_text().splitlines():
            x = json.loads(l)
            if x.get("kind") == "lint_clean":
                rows.append(x)
    seen, out, reasons = set(), collections.Counter(), collections.Counter()
    for x in rows:
        tool = x["detail"]["tool"]
        key = (x["pr"], tool)
        if key in seen:
            continue
        seen.add(key)
        if tool not in lint.GENERIC and tool not in lint.TOOLS:
            out["a tool Agentvow cannot run (" + tool + ")"] += 1
            continue
        if tool in lint.TOOLS:
            out["names a runnable tool"] += 1
            continue
        o, rp, _, n = x["pr"].split("github.com/")[1].split("/")[:4]
        files = P.gh(f"repos/{o}/{rp}/pulls/{n}/files?per_page=100", paginate=True)
        if isinstance(files, dict):
            out["no file list"] += 1
            continue
        changed = sorted({f["filename"] for f in files})
        d = Path(tempfile.mkdtemp())
        for c in CONFIGS:
            meta = P.gh(f"repos/{o}/{rp}/contents/{c}")
            if isinstance(meta, dict) and meta.get("content"):
                (d / c).write_text(base64.b64decode(meta["content"]).decode("utf-8", "replace"))
        tools, notes, blocked = lint.resolve(d, tool, changed)
        if tools:
            out["generic, resolved to " + ("+".join(tools))] += 1
            out["generic, resolved (any)"] += 1
        else:
            out["generic, unresolved"] += 1
            reasons[(blocked or "")[:70]] += 1
    n = len(seen)
    print(n, "distinct (PR, tool) lint statements")
    for k, v in out.most_common():
        print(f"{v:4d}  {k}")
    print("unresolved reasons:")
    for k, v in reasons.most_common(6):
        print(f"{v:4d}  {k}")


if __name__ == "__main__":
    main()
