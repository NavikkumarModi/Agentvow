"""Validate labelling-agent output against the item files and the schema in PROMPT.md: valid JSON, every numbered statement exactly once, step_a/label/confidence values allowed, a TRUE or FALSE label carries evidence.
Usage: python3 research/audit_label/validate.py [items_dir=data/audit/items] [labels_dir=data/audit/labels]   -> prints problems; exit 1 if any"""
import glob
import json
import os
import sys

STEP = {"CLAIM", "NOT_A_CLAIM"}
LABEL = {"TRUE", "FALSE", "CANNOT_TELL", None}
CONF = {"HIGH", "MEDIUM", "LOW"}


def check(item: dict, lab: dict) -> list:
    bad = []
    got = [s.get("n") for s in lab.get("statements", [])]
    want = [s["n"] for s in item["statements"]]
    if sorted(got) != sorted(want):
        bad.append(f"statements {got} != {want}")
    for s in lab.get("statements", []):
        if s.get("step_a") not in STEP:
            bad.append(f"n={s.get('n')}: bad step_a {s.get('step_a')!r}")
        if s.get("label") not in LABEL:
            bad.append(f"n={s.get('n')}: bad label {s.get('label')!r}")
        if s.get("step_a") == "NOT_A_CLAIM" and s.get("label") is not None:
            bad.append(f"n={s.get('n')}: NOT_A_CLAIM must have label null")
        if s.get("step_a") == "CLAIM" and s.get("label") is None:
            bad.append(f"n={s.get('n')}: CLAIM needs a label")
        if s.get("confidence") not in CONF:
            bad.append(f"n={s.get('n')}: bad confidence {s.get('confidence')!r}")
        if s.get("label") in ("TRUE", "FALSE") and not s.get("evidence"):
            bad.append(f"n={s.get('n')}: {s.get('label')} without evidence")
        if not isinstance(s.get("judgment"), bool):
            bad.append(f"n={s.get('n')}: judgment must be true or false")
    return bad


def main(items_dir="data/audit/items", labels_dir="data/audit/labels") -> int:
    problems = 0
    items = {os.path.basename(f)[:-5]: f for f in glob.glob(os.path.join(items_dir, "*.json"))}
    for f in sorted(glob.glob(os.path.join(labels_dir, "*.json"))):
        key = os.path.basename(f)[:-5].split(".")[0]
        try:
            lab = json.load(open(f))
        except ValueError as e:
            print(f"{f}: invalid JSON ({e})"); problems += 1; continue
        if key not in items:
            print(f"{f}: no item file"); problems += 1; continue
        for p in check(json.load(open(items[key])), lab):
            print(f"{f}: {p}"); problems += 1
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
