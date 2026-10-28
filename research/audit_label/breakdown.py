"""Reproducible breakdowns for the stage 1 results (review findings 4 and 9): claims by kind and repository-language stratum, and the reasons labellers gave for CANNOT_TELL.
Reasons are a KEYWORD HEURISTIC on the labeller's note and evidence, applied in the stated order of precedence (first match wins); categories are therefore exclusive by construction but approximate, and 'other' is whatever matches none.
Usage: python3 research/audit_label/breakdown.py [labels_dir=data/audit/labels]"""
import collections
import glob
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ORDER = [   # first match wins
    ("repository or pull request gone (404)", r"(repository|repo|pull request|pr \d+|pr #?\d+).{0,80}(404|not accessible|no longer)|404.{0,60}(repository|pull request)"),
    ("permission denied", r"permission|denied|classifier"),
    ("disk full", r"enospc|no space left"),
    ("toolchain not installed", r"not installed|no zig|no go |dotnet|cargo|jdk|toolchain|sbt|no .{0,20} toolchain"),
    ("no CI result or expired logs", r"no ci|ci logs|expired|no check.?runs?|no ci check"),
    ("not observable (author's machine, opinion, hedge)", r"author|own machine|observ|judgment|settle|vague|may break|hedged"),
]


def reason(text):
    t = text.lower()
    for name, rx in ORDER:
        if re.search(rx, t):
            return name
    return "other (no keyword matched)"


def main(labels="data/audit/labels"):
    broken = set(json.load(open(ROOT / "data/audit/broken_items.json")))
    sample = json.load(open(ROOT / "docs/research/audit_sample/sample.json"))["sample"]
    stratum = {r["pr"]: r["stratum"].split("|")[1] for r in sample}
    items = {Path(f).stem: json.load(open(f)) for f in glob.glob(str(ROOT / "docs/research/audit_data/items/*.json"))}
    score = json.load(open(ROOT / "data/audit/score_stage1.json"))["rows"]
    by = collections.Counter()
    for r in score:   # score_stage1.json already excludes the unobservable items
        if r["step_a"] == "CLAIM":
            by[(r["kind"], stratum[items[r["item"]]["url"]])] += 1
    print("claims by kind and repository language (python / other):")
    kinds = sorted({k for k, _ in by})
    for k in kinds:
        print(f"  {k}: python {by[(k, 'python')]}, other {by[(k, 'other')]}")
    print(f"  all: python {sum(v for (k, s), v in by.items() if s == 'python')}, other {sum(v for (k, s), v in by.items() if s == 'other')}")
    rs, n = collections.Counter(), 0
    for f in sorted(glob.glob(os.path.join(labels, "*.json"))):
        if Path(f).stem in broken:
            continue
        for s in json.load(open(f))["statements"]:
            if s["label"] == "CANNOT_TELL":
                n += 1
                rs[reason(s["note"] + " " + " ".join(s["evidence"]))] += 1
    print(f"CANNOT_TELL {n}:")
    for k, v in rs.most_common():
        print(f"  {v}  {k}")


if __name__ == "__main__":
    main(*sys.argv[1:2])
