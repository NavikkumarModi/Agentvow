"""Stage 2 scoring (revised after the adversarial review): join the audit's findings (data/audit/stage2.jsonl) with the labels. One ROW PER STATEMENT. A statement can receive several findings (different checkers on the same
sentence); the aggregation rule, stated here and chosen after the first look (disclosed in the results), is the worst verdict: CONTRADICTED over UNKNOWN over NOT_CONTRADICTED/SUPPORTED. A sensitivity variant uses only the finding
whose kind is the statement's own kind from the extractor ("own kind"). Impact = backward_compatible + no_downstream_impact statements merged. CANNOT_TELL labels are excluded from precision and miss-rate denominators.
Reports Wilson intervals and a repository cluster bootstrap for the headline, plus a split by the labeller's `judgment` flag (pre-registration A1.5).
Usage: python3 research/audit_label/score_stage2.py   -> data/audit/score_stage2.json"""
import collections
import json
import math
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KINDS = {"tests_pass": "tests", "lint_clean": "lint", "backward_compatible": "impact", "no_downstream_impact": "impact"}
RANK = {"CONTRADICTED": 3, "UNKNOWN": 2, "NOT_CONTRADICTED": 1, "SUPPORTED_BY_PRIOR_EVIDENCE": 1}


def wilson(k, n, z=1.96):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 3), round(c + h, 3)]


def boot(rows, fn, n_boot=10000, seed=20261029):
    by = collections.defaultdict(list)
    for r in rows:
        by[r["repo"]].append(r)
    repos = sorted(by)
    if len(repos) < 5:
        return None
    rng = random.Random(seed)
    vals = []
    for _ in range(n_boot):
        sample = [r for _ in repos for r in by[repos[rng.randrange(len(repos))]]]
        v = fn(sample)
        if v is not None:
            vals.append(v)
    vals.sort()
    if len(vals) < 100:
        return None
    lo, hi = round(vals[int(0.025 * len(vals))], 3), round(vals[int(0.975 * len(vals))], 3)
    return None if lo == hi else [lo, hi]


def norm(t):
    return re.sub(r"\s+", " ", t or "").strip()


def build_rows(variant):
    runs = {r["item"]: r for r in map(json.loads, open(ROOT / "data/audit/stage2.jsonl"))}
    kind1 = {(r["item"], r["n"]): r["kind"] for r in json.load(open(ROOT / "data/audit/score_stage1.json"))["rows"]}
    rows = []
    for key, run in runs.items():
        item = json.load(open(ROOT / "docs/research/audit_data/items" / (key + ".json")))
        lab = {s["n"]: s for s in json.load(open(ROOT / "docs/research/audit_data/labels" / (key + ".json")))["statements"]}
        by_claim = collections.defaultdict(list)
        for f in run.get("findings", []):
            by_claim[norm(f["claim"])].append(f)
        for s in item["statements"]:
            l = lab[s["n"]]
            if l["step_a"] != "CLAIM":
                continue
            own = kind1.get((key, s["n"]))
            fs = [f for f in by_claim.get(norm(s["text"]), []) if f["kind"] in KINDS]
            if variant == "own_kind":
                fs = [f for f in fs if f["kind"] == own]
            if not fs:
                continue
            worst = max(fs, key=lambda f: RANK.get(f["verdict"], 0))
            rows.append({"item": key, "repo": item["repo"], "n": s["n"], "group": KINDS[own if own in KINDS else fs[0]["kind"]], "kinds": sorted({f["kind"] for f in fs}), "verdict": worst["verdict"],
                         "label": l["label"], "judgment": l["judgment"], "n_findings": len(fs), "why": worst["why"][:200]})
    return rows, runs


def summarise(rows):
    out = {}
    for g in sorted({r["group"] for r in rows}):
        rg = [r for r in rows if r["group"] == g]
        dec = [r for r in rg if r["label"] in ("TRUE", "FALSE")]
        flagged = [r for r in dec if r["verdict"] == "CONTRADICTED"]
        tp = sum(r["label"] == "FALSE" for r in flagged)
        nc = [r for r in dec if r["verdict"] in ("NOT_CONTRADICTED", "SUPPORTED_BY_PRIOR_EVIDENCE")]
        miss = sum(r["label"] == "FALSE" for r in nc)
        prs = collections.defaultdict(list)
        for r in flagged:
            prs[r["item"]].append(r["label"])
        pr_tp = sum("FALSE" in v for v in prs.values())
        nj = [r for r in flagged if not r["judgment"]]
        out[g] = {"n": len(rg), "labels": dict(collections.Counter(r["label"] for r in rg)), "verdict_x_label": {f"{v}|{l}": c for (v, l), c in sorted(collections.Counter((r["verdict"], r["label"]) for r in rg).items(), key=str)},
                  "contradicted_precision": [tp, len(flagged), wilson(tp, len(flagged)), boot(flagged, lambda s: (sum(x["label"] == "FALSE" for x in s) / len(s)) if s else None)],
                  "contradicted_precision_by_pull_request": [pr_tp, len(prs), wilson(pr_tp, len(prs))],
                  "contradicted_precision_non_judgment_labels": [sum(r["label"] == "FALSE" for r in nj), len(nj)],
                  "contradicted_judgment_labels": [sum(r["judgment"] for r in flagged), len(flagged)],
                  "not_contradicted_but_labelled_false": [miss, len(nc), wilson(miss, len(nc))],
                  "labelled_false_total": sum(r["label"] == "FALSE" for r in dec), "labelled_false_flagged": sum(r["label"] == "FALSE" and r["verdict"] == "CONTRADICTED" for r in dec),
                  "unknown_but_labeller_decided": [sum(r["verdict"] == "UNKNOWN" for r in dec), len(dec)], "verdict_produced": [sum(r["verdict"] != "UNKNOWN" for r in rg), len(rg)],
                  "pull_requests": len({r["item"] for r in rg})}
    return out


def main():
    res = {}
    for variant in ("worst", "own_kind"):
        rows, runs = build_rows(variant)
        res[variant] = {"statements": len(rows), "groups": summarise(rows)}
        if variant == "worst":
            json.dump({"rows": rows}, open(ROOT / "data/audit/score_stage2_rows.json", "w"), indent=1)
    secs = sorted(r["seconds"] for r in runs.values() if r.get("seconds") is not None)
    res["run_status"] = dict(collections.Counter(r.get("status") for r in runs.values()))
    res["seconds_median"] = secs[len(secs) // 2]
    res["env_not_built_stderr"] = sorted(k for k, r in runs.items() if "environment setup incomplete" in (r.get("stderr") or ""))
    res["env_too_heavy_in_findings"] = sorted(k for k, r in runs.items() if any("environment too heavy" in (f.get("why") or "") for f in r.get("findings", [])))
    (ROOT / "data/audit/score_stage2.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
