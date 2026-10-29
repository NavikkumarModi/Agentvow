"""Gate-strength test (pre-registration, section 5; written after the freeze): minimal false variants of TRUE files statements, labelled false by construction, run through the product's own files check on the pull request's change list
and head tree. Two variants per statement with a named changed path: (a) the path is replaced by an invented sibling that does not exist ("Updated `x.py`" -> "Updated `x_old_copy.py`") and (b) "Did not touch `<path>`" about a path the
change did touch. Author and checker are not independent, so this is pipeline sensitivity only and is never mixed into the primary result. Reads the audit-study labels by default (development data) or any labels directory of the
same shape. No repository code runs.
Usage: python3 research/shadow2/seeded.py [--items docs/research/audit_data/items] [--labels docs/research/audit_data/labels]"""
import argparse
import collections
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research" / "audit_label"))
sys.path.insert(0, str(ROOT))
import score as audit_score  # noqa: E402
from agentvow import claims, statements  # noqa: E402


def variants(text, path):
    stem, dot, ext = path.rpartition(".")
    invented = f"{stem}_old_copy.{ext}" if dot else path + "_old_copy"
    return {"invented_path": text.replace(path, invented), "left_alone_but_changed": f"Did not touch `{path}`."}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", default="docs/research/audit_data/items")
    ap.add_argument("--labels", default="docs/research/audit_data/labels")
    a = ap.parse_args(argv)
    tally = collections.defaultdict(lambda: collections.Counter())
    total = 0
    for f in sorted(glob.glob(str(ROOT / a.labels / "*.json"))):
        key = Path(f).stem
        item = json.load(open(ROOT / a.items / (key + ".json")))
        lab = {s["n"]: s for s in json.load(open(f))["statements"]}
        owner, repo = item["repo"].split("/")
        files = audit_score.gh(f"repos/{owner}/{repo}/pulls/{item['number']}/files?per_page=100", paginate=True)
        pr = audit_score.gh(f"repos/{owner}/{repo}/pulls/{item['number']}")
        if not isinstance(files, list) or not isinstance(pr, dict) or "head" not in pr or not files:
            continue
        changed = sorted({x["filename"] for x in files})
        tree = audit_score.gh(f"repos/{owner}/{repo}/git/trees/{pr['head']['sha']}?recursive=1")
        tracked = [t["path"] for t in tree.get("tree", []) if t.get("type") == "blob"] if isinstance(tree, dict) and "tree" in tree and not tree.get("truncated") else []
        if not tracked:
            continue
        import shutil
        import tempfile
        work = Path(tempfile.mkdtemp(prefix="seeded_"))
        try:
            audit_score.materialise(tracked, work)
            statements._tracked = lambda r_, t=tracked: t
            statements._ignored = lambda r_, p: False
            for s in item["statements"]:
                l = lab[s["n"]]
                if l["step_a"] != "CLAIM" or l["label"] != "TRUE":
                    continue
                for kind, detail in statements.extract_sentence(s["text"]):
                    if kind != "files_scope":
                        continue
                    for c in detail["checks"]:
                        if c["expect"] != "changed" or c["path"] not in changed:
                            continue
                        for name, text in variants(s["text"], c["path"]).items():
                            for k2, d2 in statements.extract_sentence(text):
                                if k2 != "files_scope":
                                    continue
                                v = statements.check_files(work, changed, d2)[0]
                                tally[name][v] += 1
                                total += 1
        finally:
            shutil.rmtree(work, ignore_errors=True)
    out = {name: dict(c) for name, c in tally.items()}
    out["total_variants"] = total
    print(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    main()
