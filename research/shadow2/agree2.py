"""Agreement between the first labelling pass (Sonnet, data/shadow2/labels) and the second blind pass (Opus, data/shadow2/labels2) on the seeded sample of the shadow experiment. Consistency only; two LLM labellers are not independent
verification. Categories: NOT_A_CLAIM, TRUE, FALSE, CANNOT_TELL. Also the pull-request-level class (positive / negative / unscorable) agreement, which is what the primary analysis uses.
Usage: python3 research/shadow2/agree2.py -> data/shadow2/agreement.json"""
import collections
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze as A  # noqa: E402


def cat(s):
    return "NOT_A_CLAIM" if s["step_a"] == "NOT_A_CLAIM" else s["label"]


def kappa(pairs):
    n = len(pairs)
    if not n:
        return None
    po = sum(a == b for a, b in pairs) / n
    ca, cb = collections.Counter(a for a, _ in pairs), collections.Counter(b for _, b in pairs)
    pe = sum(ca[c] * cb[c] for c in set(ca) | set(cb)) / (n * n)
    return None if pe == 1 else round((po - pe) / (1 - pe), 3)


def main():
    cheap = {json.loads(l)["pr"]: json.loads(l) for l in (ROOT / "data/shadow2/cheap.jsonl").read_text().splitlines()}
    pairs, per, dis, prs = [], collections.defaultdict(list), [], []
    for f in sorted(glob.glob(str(ROOT / "data/shadow2/labels2/*.json"))):
        key = Path(f).stem
        item = json.load(open(ROOT / "data/shadow2/items" / (key + ".json")))
        l1 = {s["n"]: s for s in json.load(open(ROOT / "data/shadow2/labels" / (key + ".json")))["statements"]}
        l2 = {s["n"]: s for s in json.load(open(f))["statements"]}
        kinds = {c["text"]: c["kind"] for c in cheap[item["url"]]["claims"]}
        for n, s in l2.items():
            a, b = cat(l1[n]), cat(s)
            k = kinds.get(item["statements"][n - 1]["text"], "?")
            pairs.append((a, b)); per[k].append((a, b))
            if a != b:
                dis.append({"item": key, "n": n, "kind": k, "first": a, "second": b})
        prs.append((A.classify(list(l1.values())), A.classify(list(l2.values()))))
    claims_only = [(a, b) for a, b in pairs if not (a == "NOT_A_CLAIM" and b == "NOT_A_CLAIM")]
    out = {"items": len(glob.glob(str(ROOT / "data/shadow2/labels2/*.json"))), "statements": len(pairs), "agreement": [sum(a == b for a, b in pairs), len(pairs)], "kappa": kappa(pairs),
           "claims_only": {"n": len(claims_only), "agree": sum(a == b for a, b in claims_only), "kappa": kappa(claims_only)},
           "per_kind": {k: {"n": len(v), "agree": sum(a == b for a, b in v), "kappa": kappa(v)} for k, v in sorted(per.items())},
           "pr_class": {"n": len(prs), "agree": sum(a == b for a, b in prs), "kappa": kappa(prs), "table": {f"{a}|{b}": c for (a, b), c in sorted(collections.Counter(prs).items())}},
           "disagreement_count": len(dis), "disagreements_by_pair": {f"{a}->{b}": c for (a, b), c in collections.Counter((d["first"], d["second"]) for d in dis).items()}}
    (ROOT / "data/shadow2/agreement.json").write_text(json.dumps({**out, "disagreements": dis}, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
