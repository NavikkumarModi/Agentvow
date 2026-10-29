"""Analysis of the shadow experiment exactly as pre-registered (docs/research/SHADOW_EXPERIMENT_PREREG.md, section 5): weighted recall of positives at a fixed review budget per arm, pairwise differences with a repository cluster
bootstrap, unique catches, policy burden (census over the pool) and false-clear rate (weighted, labelled positives), and the two CANNOT_TELL sensitivity bounds. Nothing here decides anything.
Class of a labelled pull request: positive = at least one statement labelled FALSE; negative = no FALSE and at least one TRUE; unscorable = otherwise.
Usage: python3 research/shadow2/analyze.py [--budget 0.20] [--labels data/shadow2/labels] -> data/shadow2/results.json"""
import argparse
import glob
import hashlib
import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sample as S  # noqa: E402


def u(seed, tag, pr):
    return int(hashlib.sha256(f"{seed}|{tag}|{pr}".encode()).hexdigest()[:12], 16) / 16**12


def classify(labels, mode="base"):
    """labels: list of {'step_a','label'} for one pull request. mode 'pessimistic': unscorable counts positive; 'optimistic': unscorable counts negative."""
    cl = [l for l in labels if l["step_a"] == "CLAIM"]
    if any(l["label"] == "FALSE" for l in cl):
        return "positive"
    if any(l["label"] == "TRUE" for l in cl):
        return "negative"
    return {"base": "unscorable", "pessimistic": "positive", "optimistic": "negative"}[mode]


def top_set(ids, score, seed, tag, budget):
    k = math.ceil(budget * len(ids))
    order = sorted(ids, key=lambda i: (-score[i], u(seed, tag, i)))
    return set(order[:k])


def weighted_recall(pos, flagged, weight):
    den = sum(weight[p] for p in pos)
    return (sum(weight[p] for p in pos if p in flagged) / den) if den else None


def wilson(k, n, z=1.96):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 3), round(c + h, 3)]


def boot_diff(pos, repo, weight, fa, fb, seed, n=5000):
    """95% interval of recall(a) - recall(b), resampling repositories among the labelled positives."""
    by = {}
    for p in pos:
        by.setdefault(repo[p], []).append(p)
    repos = sorted(by)
    if len(repos) < 5:
        return None
    rng = random.Random(seed)
    vals = []
    for _ in range(n):
        sp = [p for _ in repos for p in by[repos[rng.randrange(len(repos))]]]
        ra, rb = weighted_recall(sp, fa, weight), weighted_recall(sp, fb, weight)
        if ra is not None and rb is not None:
            vals.append(ra - rb)
    vals.sort()
    return [round(vals[int(0.025 * len(vals))], 3), round(vals[int(0.975 * len(vals))], 3)] if len(vals) > 100 else None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=float, default=0.20)
    ap.add_argument("--labels", default="data/shadow2/labels")
    ap.add_argument("--seed", type=int, default=20261030)
    a = ap.parse_args(argv)
    cheap = {json.loads(l)["pr"]: json.loads(l) for l in (ROOT / "data/shadow2/cheap.jsonl").read_text().splitlines()}
    cheap = {k: v for k, v in cheap.items() if "head" in v}
    ls = json.loads((ROOT / "data/shadow2/label_sample.json").read_text())
    rows = {r["pr"]: r for r in ls["rows"]}
    full = {json.loads(l)["pr"]: json.loads(l) for l in (ROOT / "data/shadow2/full_arm5.jsonl").read_text().splitlines()} if (ROOT / "data/shadow2/full_arm5.jsonl").exists() else {}
    ids = sorted(cheap)
    repo = {i: cheap[i]["repo"] for i in ids}
    f5 = {i: S.arm5_findings(cheap[i], full.get(i)) for i in ids}
    scores = {
        "arm0_random": {i: u(a.seed, "rand", i) for i in ids},
        "arm1_ci": {i: {"failing_or_pending": 2, "none": 1, "success": 0}[cheap[i]["arm1_ci"]] for i in ids},
        "arm2_trust_report": {i: 1 if cheap[i]["arm2_decision"] == "review" else 0 for i in ids},
        "arm3_lexical": {i: cheap[i]["arm3_lexical"] for i in ids},
        "arm5_agentvow": {i: S.arm5_score(f5[i]) for i in ids},
    }
    flags = {name: top_set(ids, sc, a.seed, name, a.budget) for name, sc in scores.items()}
    half = a.budget / 2
    flags["arm6_ci_plus_agentvow"] = top_set(ids, scores["arm1_ci"], a.seed, "arm1_ci", half) | top_set(ids, scores["arm5_agentvow"], a.seed, "arm5_agentvow", half)
    # labels
    labelled = {}
    for f in glob.glob(str(ROOT / a.labels / "*.json")):   # label files carry the item's name; the pull request comes from the item file
        lab = json.load(open(f))
        item = json.load(open(ROOT / "data/shadow2/items" / (Path(f).stem + ".json")))
        labelled[item["url"]] = lab["statements"]
    res = {"budget": a.budget, "pool": len(ids), "labelled": len(labelled), "arms": {}, "policies": {}}
    for mode in ("base", "pessimistic", "optimistic"):
        cls = {p: classify(s, mode) for p, s in labelled.items() if p in rows}
        pos = [p for p, c in cls.items() if c == "positive"]
        weight = {p: rows[p]["weight"] for p in cls}
        block = {"positives": len(pos), "negatives": sum(c == "negative" for c in cls.values()), "unscorable": sum(c == "unscorable" for c in cls.values()), "recall": {}, "diff_vs_arm1": {}, "diff_vs_arm3": {}}
        for name, fl in flags.items():
            r = weighted_recall(pos, fl, weight)
            k = sum(1 for p in pos if p in fl)
            block["recall"][name] = {"weighted": None if r is None else round(r, 3), "unweighted": [k, len(pos), wilson(k, len(pos))]}
        for name, ref in (("diff_vs_arm1", "arm1_ci"), ("diff_vs_arm3", "arm3_lexical")):
            for arm in ("arm5_agentvow", "arm6_ci_plus_agentvow"):
                ra, rb = weighted_recall(pos, flags[arm], weight), weighted_recall(pos, flags[ref], weight)
                block[name][arm] = None if ra is None or rb is None else {"diff": round(ra - rb, 3), "cluster_bootstrap_95": boot_diff(pos, repo, weight, flags[arm], flags[ref], a.seed)}
        if mode == "base":
            uniq = [p for p in pos if p in flags["arm5_agentvow"] and p not in flags["arm1_ci"] and p not in flags["arm3_lexical"]]
            block["unique_catches"] = {"count": len(uniq), "repos": sorted({repo[p] for p in uniq}), "prs": uniq}
            for pol in ("strict", "lenient"):
                dec = {i: S.policy.decide(f5[i], pol) for i in ids}
                burden = sum(d == "review" for d in dec.values()) / len(ids)
                fc_den = sum(weight[p] for p in pos)
                fc = (sum(weight[p] for p in pos if dec[p] == "proceed") / fc_den) if fc_den else None
                neg = [p for p, c in cls.items() if c == "negative"]
                prec_num = sum(weight[p] for p in pos if dec[p] == "review")
                prec_den = prec_num + sum(weight[p] for p in neg if dec[p] == "review")
                res["policies"][pol] = {"review_burden_census": round(burden, 3), "false_clear_rate_weighted": None if fc is None else round(fc, 3),
                                        "false_clear_unweighted": [sum(dec[p] == "proceed" for p in pos), len(pos)], "review_precision_weighted": None if not prec_den else round(prec_num / prec_den, 3)}
        res["arms"][mode] = block
    (ROOT / "data/shadow2/results.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
