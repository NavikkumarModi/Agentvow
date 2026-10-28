"""Stage 1 scoring of the audit study (docs/research/AUDIT_STUDY_PREREG.md, sections 4 and 5): join the labelling agents' labels with the frozen checker's verdicts and write the tables.
Stage 1 covers what needs no execution of repository code: extraction precision (H6), coverage (H3), and the files_scope / docs_updated verdicts, computed from each pull request's own change list and its head-commit tree
(GitHub API, cached in data/audit/api/). tests_pass, lint_clean and impact statements are counted for extraction and coverage but their verdicts are NOT computed here (stage 2 needs the audit runs).
For files and docs the product turns a disagreement into UNKNOWN + attention (a "mismatch"); the raw check result CONTRADICTED is therefore reported as the mismatch flag.
Usage: python3 research/audit_label/score.py [--labels data/audit/labels] [--items data/audit/items] [--out data/audit/score_stage1.json]   (needs `gh`)"""
import argparse
import collections
import glob
import json
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from agentvow import claims, statements  # noqa: E402

API = ROOT / "data" / "audit" / "api"


def gh(path, paginate=False):
    API.mkdir(parents=True, exist_ok=True)
    key = API / (path.replace("/", "_").replace("?", "_") + ".json")
    if key.exists():
        return json.loads(key.read_text())
    p = subprocess.run(["gh", "api", *(["--paginate"] if paginate else []), path], capture_output=True, text=True, timeout=180)
    if p.returncode:
        out = {"error": p.stderr[:200]}
    else:
        out = json.loads(p.stdout.replace("][", ",") if paginate else p.stdout)
    key.write_text(json.dumps(out))
    return out


def materialise(tree, dest: Path):
    """A directory holding an empty file for every path of the pull request's head tree, so the product's own `statements._exists` (which looks at the disk) sees the same files git would. Review finding 1: the earlier
    FakeRepo made `_exists` always False, so a "removed X" claim about a file that still exists could never be flagged. `_ignored` is still stubbed (the .gitignore of each repository is not materialised): a path git
    ignores would be UNKNOWN in the product but can be CONTRADICTED here."""
    for t in tree:
        f = dest / t
        f.parent.mkdir(parents=True, exist_ok=True)
        f.touch()


def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(c - h, 3), round(c + h, 3))


def cluster_bootstrap(rows, success, n_boot=10000, seed=20261029):
    """95% interval of sum(success)/len for rows, resampling repositories (the pre-registered clustering unit). Returns [lo, hi] or None when fewer than 5 repositories."""
    import random
    by = collections.defaultdict(list)
    for r in rows:
        by[r["repo"]].append(1 if success(r) else 0)
    repos = sorted(by)
    if len(repos) < 5:
        return None
    rng = random.Random(seed)
    vals = []
    for _ in range(n_boot):
        k = n = 0
        for _ in repos:
            g = by[repos[rng.randrange(len(repos))]]
            k += sum(g)
            n += len(g)
        vals.append(k / n if n else 0.0)
    vals.sort()
    lo, hi = round(vals[int(0.025 * n_boot)], 3), round(vals[int(0.975 * n_boot)], 3)
    return None if lo == hi else [lo, hi]   # a degenerate interval (every row a success) is not an interval


def verdicts_for(item):
    """{statement text: (kind, verdict or None, detail)} from the frozen extractor and, for files/docs, the checks on the PR's own change list and head tree."""
    owner, repo = item["repo"].split("/")
    pr = gh(f"repos/{owner}/{repo}/pulls/{item['number']}")
    files = gh(f"repos/{owner}/{repo}/pulls/{item['number']}/files?per_page=100", paginate=True)
    ok = isinstance(pr, dict) and "head" in pr and isinstance(files, list) and len(files) < 3000   # an empty change list is a real answer for an open pull request (a files claim is then certainly false)
    changed, tracked = [], []
    if ok:
        changed = sorted({f["filename"] for f in files} | {f["previous_filename"] for f in files if f.get("previous_filename")})
        tree = gh(f"repos/{owner}/{repo}/git/trees/{pr['head']['sha']}?recursive=1")
        tracked = [t["path"] for t in tree.get("tree", []) if t.get("type") == "blob"] if isinstance(tree, dict) and "tree" in tree and not tree.get("truncated") else []
        if not tracked:
            ok = False
    out = {}
    import shutil
    import tempfile
    work = Path(tempfile.mkdtemp(prefix="score_tree_"))
    if ok and len(tracked) <= 60000:
        materialise(tracked, work)
    else:
        ok = False
    fake = work
    statements._tracked = lambda repo_, t=tracked: t
    statements._ignored = lambda repo_, p: False
    for c in claims.extract(item["message"]):
        if c.text in out:
            continue
        v = None
        if c.kind == "files_scope" and ok:
            v = statements.check_files(fake, changed, c.detail)[0]
        elif c.kind == "docs_updated" and ok:
            v = statements.check_docs(changed, c.detail)[0]
        out[c.text] = (c.kind, v, ok)
    shutil.rmtree(work, ignore_errors=True)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", default="data/audit/labels")
    ap.add_argument("--items", default="data/audit/items")
    ap.add_argument("--out", default="data/audit/score_stage1.json")
    ap.add_argument("--exclude", default="data/audit/broken_items.json", help="JSON list of item keys that could not be observed at all (repository or pull request gone); excluded and replaced by the next items in the seeded order, as the pre-registration says")
    a = ap.parse_args(argv)
    excluded = set(json.loads(Path(a.exclude).read_text())) if a.exclude and Path(a.exclude).exists() else set()
    items = {Path(f).stem: json.load(open(f)) for f in glob.glob(f"{a.items}/*.json") if Path(f).stem not in excluded}
    rows = []
    for f in sorted(glob.glob(f"{a.labels}/*.json")):
        key = Path(f).stem
        if key not in items:
            continue
        it, lab = items[key], json.load(open(f))
        vd = verdicts_for(it)
        byn = {s["n"]: s for s in it["statements"]}
        for s in lab["statements"]:
            text = byn[s["n"]]["text"]
            if text not in vd:
                raise SystemExit(f"join failure: item {key} statement {s['n']} not found among the extractor's statements: {text[:80]!r}")
            kind, verdict, ok = vd[text]
            rows.append({"item": key, "repo": it["repo"], "n": s["n"], "kind": kind, "verdict": verdict, "checks_ran": ok, "step_a": s["step_a"], "label": s["label"], "judgment": s["judgment"], "confidence": s["confidence"]})
    kinds = sorted({r["kind"] for r in rows})
    res = {"excluded_unobservable_items": sorted(excluded), "items_labelled": len({r["item"] for r in rows}), "statements": len(rows), "per_kind": {}}
    for k in kinds:
        rk = [r for r in rows if r["kind"] == k]
        claims_ = [r for r in rk if r["step_a"] == "CLAIM"]
        nac = len(rk) - len(claims_)
        d = {"n": len(rk), "not_a_claim": nac, "extraction_precision": [len(claims_), len(rk), wilson(len(claims_), len(rk))], "extraction_precision_cluster_bootstrap": cluster_bootstrap(rk, lambda r: r["step_a"] == "CLAIM"),
             "labels": dict(collections.Counter(r["label"] for r in claims_))}
        if k in ("files_scope", "docs_updated"):
            ran = [r for r in claims_ if r["checks_ran"]]
            d["verdicts_x_label"] = {f"{v}|{l}": c for (v, l), c in sorted(collections.Counter((r["verdict"], r["label"]) for r in ran).items(), key=str)}
            flagged = [r for r in ran if r["verdict"] == "CONTRADICTED" and r["label"] in ("TRUE", "FALSE")]
            tp = sum(r["label"] == "FALSE" for r in flagged)
            d["mismatch_flag_precision"] = [tp, len(flagged), wilson(tp, len(flagged))]
            other = [r for r in ran if r["verdict"] != "CONTRADICTED" and r["label"] == "FALSE"]
            d["false_statements_not_flagged"] = len(other)
            d["checks_not_run"] = len(claims_) - len(ran)
        res["per_kind"][k] = d
    cl = [r for r in rows if r["step_a"] == "CLAIM"]
    covered = [r for r in cl if r["kind"] != "unchecked"]
    res["coverage"] = {"claims": len(cl), "with_a_verdict_path": len(covered), "share": [len(covered), len(cl), wilson(len(covered), len(cl))]}
    res["cannot_tell_share"] = [sum(r["label"] == "CANNOT_TELL" for r in cl), len(cl)]
    res["judgment_share"] = [sum(r["judgment"] for r in cl), len(cl)]
    Path(a.out).write_text(json.dumps({"summary": res, "rows": rows}, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
