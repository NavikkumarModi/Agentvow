"""Agreement between the first labelling pass (data/audit/labels) and the second, blind pass by a different model (data/audit/labels2) on the seeded 20% sample (docs/research/AUDIT_STUDY_PREREG.md, A1 point 2).
Category per statement: NOT_A_CLAIM, TRUE, FALSE or CANNOT_TELL. Reports percent agreement and Cohen's kappa overall and per statement kind (kind joined from data/audit/score_stage1.json), and lists every disagreement.
Agreement between two LLM labellers is consistency, not independent verification.
Usage: python3 research/audit_label/agree.py"""
import collections
import glob
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def cat(s):
    return "NOT_A_CLAIM" if s["step_a"] == "NOT_A_CLAIM" else s["label"]


def kappa(pairs):
    n = len(pairs)
    if n == 0:
        return None
    po = sum(a == b for a, b in pairs) / n
    ca, cb = collections.Counter(a for a, _ in pairs), collections.Counter(b for _, b in pairs)
    pe = sum(ca[c] * cb[c] for c in set(ca) | set(cb)) / (n * n)
    return None if pe == 1 else round((po - pe) / (1 - pe), 3)


def main():
    rows = json.load(open(ROOT / "data/audit/score_stage1.json"))["rows"]
    kind = {(r["item"], r["n"]): r["kind"] for r in rows}
    broken = set(json.load(open(ROOT / "data/audit/broken_items.json")))
    pairs, per, dis = [], collections.defaultdict(list), []
    for f in sorted(glob.glob(str(ROOT / "data/audit/labels2/*.json"))):
        key = Path(f).stem
        if key in broken:
            continue
        l1 = {s["n"]: s for s in json.load(open(ROOT / "data/audit/labels" / (key + ".json")))["statements"]}
        for s in json.load(open(f))["statements"]:
            a, b = cat(l1[s["n"]]), cat(s)
            pairs.append((a, b))
            per[kind[(key, s["n"])]].append((a, b))
            if a != b:
                dis.append({"item": key, "n": s["n"], "kind": kind[(key, s["n"])], "first": a, "second": b, "first_note": l1[s["n"]]["note"][:160], "second_note": s["note"][:160]})
    claims_only = [(a, b) for a, b in pairs if not (a == "NOT_A_CLAIM" and b == "NOT_A_CLAIM")]   # both passes called it not a claim: dropped so that easy agreement does not inflate the statistics
    out = {"items": len({Path(f).stem for f in glob.glob(str(ROOT / "data/audit/labels2/*.json"))} - broken), "statements": len(pairs), "excluding_both_not_a_claim": {"n": len(claims_only), "agree": sum(a == b for a, b in claims_only), "kappa": kappa(claims_only)},
           "agreement": [sum(a == b for a, b in pairs), len(pairs)], "kappa": kappa(pairs),
           "per_kind": {k: {"n": len(v), "agree": sum(a == b for a, b in v), "kappa": kappa(v)} for k, v in sorted(per.items())}, "disagreements": dis}
    (ROOT / "data/audit/agreement.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "disagreements"}, indent=1))
    for d in dis:
        print(d["item"], d["n"], d["kind"], d["first"], "->", d["second"])


if __name__ == "__main__":
    main()
