"""Repair-loop pilot (docs/research/REPAIR_LOOP_PREREG.md section 1): which shadow-pool pull requests are units, and in which stratum. Deterministic; reads only frozen shadow data.
R = a CONTRADICTED finding (arm-5 score 3) whose first-pass label is positive and, where a second-pass label exists, also positive; F = first-pass negative among score >= 2; I = score 2 with only attention on UNKNOWN impact; the rest are listed as unlabelled/unscorable, not analysed.
Runtime filters (environment buildable, head commit fetchable, change list non-empty) are applied by the harness and recorded with reasons.
Usage: python3 research/repair/eligibility.py -> data/repair/eligible.json (and prints its SHA-256)"""
import glob
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research/shadow2"))
import analyze as A  # noqa: E402
import sample as S  # noqa: E402


def labels(d):
    out = {}
    for f in glob.glob(str(ROOT / "data/shadow2" / d / "*.json")):
        it = json.load(open(ROOT / "data/shadow2/items" / Path(f).name))
        out[it["url"]] = A.classify(json.load(open(f))["statements"])
    return out


def main():
    cheap = {}
    for l in (ROOT / "data/shadow2/cheap.jsonl").read_text().splitlines():
        r = json.loads(l)
        if "head" in r:
            cheap[r["pr"]] = r
    full = {json.loads(l)["pr"]: json.loads(l) for l in (ROOT / "data/shadow2/full_arm5.jsonl").read_text().splitlines()}
    l1, l2 = labels("labels"), labels("labels2")
    units = []
    for p in sorted(cheap):
        if p not in full:
            continue
        f = S.arm5_findings(cheap[p], full[p])
        sc = S.arm5_score(f)
        if sc < 2:
            continue
        first, second = l1.get(p, "unlabelled"), l2.get(p)
        contradicted = sorted({x["kind"] for x in f if x["verdict"] == "CONTRADICTED"})
        if sc == 3 and first == "positive" and second in (None, "positive"):
            stratum = "R"
        elif first == "negative":
            stratum = "F"
        elif sc == 2:
            stratum = "I"
        else:
            stratum = "other"
        units.append({"pr": p, "repo": cheap[p]["repo"], "number": cheap[p]["number"], "head": cheap[p]["head"], "base": cheap[p]["base"], "score": sc, "contradicted_kinds": contradicted,
                      "first_pass": first, "second_pass": second, "stratum": stratum, "ci": cheap[p]["arm1_ci"]})
    out = {"n": len(units), "counts": {s: sum(u["stratum"] == s for u in units) for s in ("R", "F", "I", "other")}, "units": units}
    Path(ROOT / "data/repair").mkdir(parents=True, exist_ok=True)
    text = json.dumps(out, indent=1, sort_keys=True)
    (ROOT / "data/repair/eligible.json").write_text(text)
    print(out["counts"], hashlib.sha256(text.encode()).hexdigest())
    for u in units:
        if u["stratum"] == "R":
            print(u["repo"], u["number"], u["contradicted_kinds"], u["first_pass"], u["second_pass"], u["ci"])


if __name__ == "__main__":
    main()
