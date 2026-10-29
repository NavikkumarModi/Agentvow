"""Post-hoc robustness checks added after the adversarial review of the shadow experiment (exploratory, NOT pre-registered; every number is labelled as such in the results). Reuses analyze.py's functions.
(1) tie-seed distribution of the weighted recall at the 20% budget and of S1/S2; (2) recall within the flagged stratum and the weight carried by the 'rest' positives; (3) results with and without pull requests that have an empty change list;
(4) the binary-decision comparison (burden / recall / precision, weighted) for the arms that make a yes/no decision; (5) positives and scorable shares by arm-5 score.
Usage: python3 research/shadow2/robustness.py -> data/shadow2/robustness.json"""
import collections
import glob
import json
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze as A  # noqa: E402
import sample as S  # noqa: E402
from common import gh  # noqa: E402


def main():
    cheap = {json.loads(l)["pr"]: json.loads(l) for l in (ROOT / "data/shadow2/cheap.jsonl").read_text().splitlines()}
    cheap = {k: v for k, v in cheap.items() if "head" in v}
    ls = json.loads((ROOT / "data/shadow2/label_sample.json").read_text())
    rows = {r["pr"]: r for r in ls["rows"]}
    full = {json.loads(l)["pr"]: json.loads(l) for l in (ROOT / "data/shadow2/full_arm5.jsonl").read_text().splitlines()}
    ids = sorted(cheap)
    f5 = {i: S.arm5_findings(cheap[i], full.get(i)) for i in ids}
    sc = {
        "arm0": {i: 0 for i in ids},
        "arm1": {i: {"failing_or_pending": 2, "none": 1, "success": 0}[cheap[i]["arm1_ci"]] for i in ids},
        "arm2": {i: 1 if cheap[i]["arm2_decision"] == "review" else 0 for i in ids},
        "arm3": {i: cheap[i]["arm3_lexical"] for i in ids},
        "arm5": {i: S.arm5_score(f5[i]) for i in ids},
    }
    lab = {}
    for f in glob.glob(str(ROOT / "data/shadow2/labels/*.json")):
        it = json.load(open(ROOT / "data/shadow2/items" / (Path(f).stem + ".json")))
        lab[it["url"]] = json.load(open(f))["statements"]
    cls = {p: A.classify(s) for p, s in lab.items() if p in rows}
    w = {p: rows[p]["weight"] for p in cls}
    pos = [p for p, c in cls.items() if c == "positive"]
    neg = [p for p, c in cls.items() if c == "negative"]
    empty = {}
    for p in cls:
        o, r = cheap[p]["repo"].split("/")
        fl = gh(f"repos/{o}/{r}/pulls/{cheap[p]['number']}/files?per_page=100", paginate=True)
        empty[p] = isinstance(fl, list) and len(fl) == 0
    out = {"note": "post-hoc, exploratory; not pre-registered"}

    def tops(seed, budget=0.20, arms=("arm0", "arm1", "arm2", "arm3", "arm5")):
        t = {a: A.top_set(ids, sc[a], seed, a, budget) for a in arms}
        t["arm6"] = A.top_set(ids, sc["arm1"], seed, "arm1", budget / 2) | A.top_set(ids, sc["arm5"], seed, "arm5", budget / 2)
        return t

    # (1) tie-seed distribution
    rec = collections.defaultdict(list)
    s1 = s2 = 0
    n = 300
    for k in range(n):
        t = tops(1000 + k)
        for a, fl in t.items():
            rec[a].append(A.weighted_recall(pos, fl, w))
        s1 += A.weighted_recall(pos, t["arm5"], w) > max(A.weighted_recall(pos, t["arm0"], w), A.weighted_recall(pos, t["arm2"], w))
        def uniq(arm):
            u_ = [p for p in pos if p in t[arm] and p not in t["arm1"] and p not in t["arm3"]]
            return len(u_), len({cheap[p]["repo"] for p in u_})
        a0 = uniq("arm0"); s2 += (a0[0] >= 3 and a0[1] >= 3)
    out["tie_seed_distribution"] = {a: {"mean": round(statistics.mean(v), 3), "sd": round(statistics.stdev(v), 3)} for a, v in rec.items()}
    out["tie_seed_S1_share"] = round(s1 / n, 2)
    out["tie_seed_random_meets_S2_share"] = round(s2 / n, 2)
    d = [rec["arm5"][i] - rec["arm1"][i] for i in range(n)]
    out["tie_seed_arm5_minus_arm1"] = {"mean": round(statistics.mean(d), 3), "sd": round(statistics.stdev(d), 3), "positive_share": round(sum(x > 0 for x in d) / n, 2)}
    # (2) flagged stratum and weight concentration
    flagged_pos = [p for p in pos if rows[p]["flagged"]]
    rest_pos = [p for p in pos if not rows[p]["flagged"]]
    t0 = tops(20261030)
    out["rest_positives"] = {"n": len(rest_pos), "weight_share": round(sum(w[p] for p in rest_pos) / sum(w[p] for p in pos), 3)}
    out["recall_within_flagged_stratum"] = {a: [sum(p in fl for p in flagged_pos), len(flagged_pos)] for a, fl in t0.items()}
    # (3) without empty-change-list pull requests
    pos2 = [p for p in pos if not empty[p]]
    out["without_empty_change_list"] = {"positives": len(pos2), "weighted_recall": {a: round(A.weighted_recall(pos2, fl, w), 3) for a, fl in t0.items()},
                                        "unique_catches": [len([p for p in pos2 if p in t0["arm5"] and p not in t0["arm1"] and p not in t0["arm3"]]),
                                                           len({cheap[p]["repo"] for p in pos2 if p in t0["arm5"] and p not in t0["arm1"] and p not in t0["arm3"]})]}
    # (4) binary decisions
    dec = {
        "arm1_non_success": {i: cheap[i]["arm1_ci"] != "success" for i in ids},
        "arm1_failing_only": {i: cheap[i]["arm1_ci"] == "failing_or_pending" for i in ids},
        "arm2_review": {i: cheap[i]["arm2_decision"] == "review" for i in ids},
        "arm5_strict": {i: S.policy.decide(f5[i], "strict") == "review" for i in ids},
        "arm5_lenient": {i: S.policy.decide(f5[i], "lenient") == "review" for i in ids},
    }
    tab = {}
    for name, d_ in dec.items():
        fl = {i for i in ids if d_[i]}
        wp, wn = sum(w[p] for p in pos), sum(w[p] for p in neg)
        tp = sum(w[p] for p in pos if p in fl); fp = sum(w[p] for p in neg if p in fl)
        tab[name] = {"burden": round(len(fl) / len(ids), 3), "weighted_recall": round(tp / wp, 3), "weighted_precision": None if tp + fp == 0 else round(tp / (tp + fp), 3)}
    out["binary_decisions"] = tab
    # (5) scorable share by arm 5 score
    sh = {}
    for s_ in (0, 1, 2, 3):
        L = [p for p in cls if sc["arm5"][p] == s_]
        sh[s_] = {"labelled": len(L), "unscorable": sum(cls[p] == "unscorable" for p in L)}
    out["arm5_score_scorable_share"] = sh
    (ROOT / "data/shadow2/robustness.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
