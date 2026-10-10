"""How many review items does a human face at each level of abstraction, for the agent patches of Stage B1/B2, and how many of them does independent evidence close?
Descriptive proxy, NOT a measure of human effort (that needs a human study). Levels: lines, hunks, files, changed symbols, decision-relevant items.
Symbols come from the unified diff only (git's hunk function context plus added `def`/`class` lines), so they are approximate; untracked files created by the agent are NOT in the saved
patch and are counted from status.txt (their size is unknown). Decision-relevant item (deterministic rule, no model): a changed or added public symbol (name not starting with `_`) in a
non-test source file, any change to a dependency manifest, CI or build configuration, any deleted or renamed file, any new file outside tests/docs.
Usage: python3 research/preconditions/count_review_items.py [b1|b2]"""
import json
import re
import statistics
import sys
from pathlib import Path

D = Path(__file__).resolve().parents[2] / "data" / "preconditions"
MANIFEST = re.compile(r"(^|/)(pyproject\.toml|setup\.py|setup\.cfg|requirements[^/]*\.txt|Pipfile(\.lock)?|poetry\.lock|uv\.lock|tox\.ini|package\.json|Makefile|Dockerfile|MANIFEST\.in)$|^\.github/|(^|/)\.gitlab-ci")
TESTY = re.compile(r"(^|/)(tests?|testing|spec)(/|$)|(^|/)test_[^/]*\.py$|_test\.py$|(^|/)conftest\.py$")
DOCY = re.compile(r"\.(md|rst|txt)$|(^|/)docs?/|^LICENSE|^README|^CHANGELOG", re.I)
SYM = re.compile(r"^\s*(?:async\s+)?(?:def|class)\s+([A-Za-z_]\w*)")


def parse(patch: str):
    files, cur = {}, None
    for ln in patch.splitlines():
        m = re.match(r"^diff --git a/(.*) b/(.*)$", ln)
        if m:
            cur = files.setdefault(m.group(2), {"add": 0, "del": 0, "hunks": 0, "syms": set(), "new": False, "deleted": False, "renamed": m.group(1) != m.group(2)})
        elif cur is None:
            continue
        elif ln.startswith("new file"):
            cur["new"] = True
        elif ln.startswith("deleted file"):
            cur["deleted"] = True
        elif ln.startswith("@@"):
            cur["hunks"] += 1
            h = re.match(r"^@@[^@]*@@\s*(.*)$", ln)
            sm = SYM.match(h.group(1)) if h and h.group(1) else None
            if sm:
                cur["syms"].add(sm.group(1))
        elif ln.startswith("+") and not ln.startswith("+++"):
            cur["add"] += 1
            sm = SYM.match(ln[1:])
            if sm:
                cur["syms"].add(sm.group(1))
        elif ln.startswith("-") and not ln.startswith("---"):
            cur["del"] += 1
            sm = SYM.match(ln[1:])
            if sm:
                cur["syms"].add(sm.group(1))
    return files


def untracked(status: str):
    return [l[3:].strip('"') for l in status.splitlines() if l.startswith("??") and not l[3:].startswith((".agentvow", ".pytest_cache", "__pycache__")) and not l[3:].endswith((".pyc", ".json")) and "/__pycache__/" not in l]


def analyse(run_dir: Path):
    patch = (run_dir / "patch.diff").read_text() if (run_dir / "patch.diff").exists() else ""
    files = parse(patch)
    unt = untracked((run_dir / "status.txt").read_text() if (run_dir / "status.txt").exists() else "")
    items = []   # decision-relevant items
    for f, d in files.items():
        if TESTY.search(f) or DOCY.search(f):
            continue
        if MANIFEST.search(f):
            items.append(("config", f))
        elif d["deleted"] or d["renamed"]:
            items.append(("delete_or_rename", f))
        elif f.endswith(".py"):
            pub = [s for s in d["syms"] if not s.startswith("_")]
            items += [("public_symbol", f"{f}:{s}") for s in sorted(pub)]
            if d["new"] and not pub:
                items.append(("new_module", f))
        else:
            items.append(("other_file", f))
    for f in unt:
        if not (TESTY.search(f) or DOCY.search(f)):
            items.append(("new_untracked", f))
    src = [f for f in files if not (TESTY.search(f) or DOCY.search(f))]
    return {"lines": sum(d["add"] + d["del"] for d in files.values()), "hunks": sum(d["hunks"] for d in files.values()), "files": len(files) + len(unt),
            "source_files": len(src) + sum(1 for f in unt if not (TESTY.search(f) or DOCY.search(f))), "symbols": len({(f, s) for f, d in files.items() for s in d["syms"]}),
            "items": len(items), "kinds": sorted({k for k, _ in items}), "untracked": len(unt)}


def main(which):
    rows = [json.loads(l) for l in (D / f"stageb{'2' if which == 'b2' else ''}_results.jsonl").read_text().splitlines() if l.strip()]
    out = []
    for r in rows:
        rd = Path(r.get("run_dir") or "")
        if not (rd / "patch.diff").exists():
            continue
        a = analyse(rd)
        ev = ((r.get("ladder") or {}).get("evidence") or {}).get("result")
        out.append({**a, "name": f"{r['repo']}#{r['pr']}", "claim_closed": ev == "pass"})
    n = len(out)
    print(f"{which.upper()}: {n} patches")
    for k in ("lines", "hunks", "files", "source_files", "symbols", "items"):
        v = sorted(o[k] for o in out)
        print(f"  {k:13s} median {statistics.median(v):5.1f}  mean {statistics.mean(v):6.1f}  max {v[-1]:4d}  zero in {sum(1 for x in v if x == 0)}")
    tot = {k: sum(o[k] for o in out) for k in ("lines", "hunks", "files", "symbols", "items")}
    print("  totals", tot, f"| items per 100 lines {100 * tot['items'] / max(1, tot['lines']):.1f}")
    print(f"  patches with 0 decision-relevant items: {sum(o['items'] == 0 for o in out)}; 1-2: {sum(1 <= o['items'] <= 2 for o in out)}; 3+: {sum(o['items'] >= 3 for o in out)}")
    print(f"  patches whose single 'tests pass' claim was independently reproduced (zero-config replay): {sum(o['claim_closed'] for o in out)}/{n}; "
          f"patches with untracked files not in the patch: {sum(o['untracked'] > 0 for o in out)}")
    return out


if __name__ == "__main__":
    for w in (sys.argv[1:] or ["b1", "b2"]):
        main(w)
