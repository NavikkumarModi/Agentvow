"""Stage 2 scoring: join the audit's findings (data/audit/stage2.jsonl) with the labels (statement text <-> finding claim) for tests, lint and impact statements, and write the tables for H1 (precision of CONTRADICTED),
H2 (UNKNOWN that a labeller could settle), H4 (reach) and the miss rate. Only statements of pull requests that stage 2 ran are included. CANNOT_TELL labels are reported but excluded from precision/miss denominators.
Usage: python3 research/audit_label/score_stage2.py   -> data/audit/score_stage2.json"""
import collections
import glob
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def wilson(k, n, z=1.96):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 3), round(c + h, 3)]


def norm(t):
    return re.sub(r"\s+", " ", t or "").strip()


def main():
    runs = {r["item"]: r for r in map(json.loads, open(ROOT / "data/audit/stage2.jsonl"))}
    rows = []
    for key, run in runs.items():
        item = json.load(open(ROOT / "docs/research/audit_data/items" / (key + ".json")))
        lab = {s["n"]: s for s in json.load(open(ROOT / "docs/research/audit_data/labels" / (key + ".json")))["statements"]}
        findings = {norm(f["claim"]): f for f in run.get("findings", [])}
        for s in item["statements"]:
            l = lab[s["n"]]
            if l["step_a"] != "CLAIM":
                continue
            f = findings.get(norm(s["text"]))
            if f is None or f["kind"] not in ("tests_pass", "lint_clean", "backward_compatible", "no_downstream_impact"):
                continue
            rows.append({"item": key, "repo": item["repo"], "kind": f["kind"], "verdict": f["verdict"], "attention": f["attention"], "label": l["label"], "judgment": l["judgment"], "why": f["why"][:200]})
    res = {"items_run": len(runs), "statements": len(rows), "per_kind": {}}
    for k in sorted({r["kind"] for r in rows}):
        rk = [r for r in rows if r["kind"] == k]
        d = {"n": len(rk), "labels": dict(collections.Counter(r["label"] for r in rk)), "verdicts": dict(collections.Counter(r["verdict"] for r in rk)),
             "verdict_x_label": {f"{v}|{l}": c for (v, l), c in sorted(collections.Counter((r["verdict"], r["label"]) for r in rk).items(), key=str)}}
        flagged = [r for r in rk if r["verdict"] == "CONTRADICTED" and r["label"] in ("TRUE", "FALSE")]
        tp = sum(r["label"] == "FALSE" for r in flagged)
        d["contradicted_precision"] = [tp, len(flagged), wilson(tp, len(flagged))]
        decided = [r for r in rk if r["label"] in ("TRUE", "FALSE")]
        d["labelled_true_false"] = len(decided)
        d["labelled_false_flagged"] = sum(1 for r in decided if r["label"] == "FALSE" and r["verdict"] == "CONTRADICTED")
        d["labelled_false_total"] = sum(1 for r in decided if r["label"] == "FALSE")
        d["unknown_but_labeller_decided"] = [sum(1 for r in decided if r["verdict"] == "UNKNOWN"), len(decided)]
        d["reach"] = [sum(1 for r in rk if r["verdict"] != "UNKNOWN"), len(rk)]
        res["per_kind"][k] = d
    res["unknown_reasons"] = dict(collections.Counter(re.sub(r"\d+", "N", r["why"])[:90] for r in rows if r["verdict"] == "UNKNOWN").most_common(8))
    res["run_status"] = dict(collections.Counter(r.get("status") for r in runs.values()))
    res["seconds_median"] = sorted(r["seconds"] for r in runs.values() if r.get("seconds"))[len(runs) // 2]
    (ROOT / "data/audit/score_stage2.json").write_text(json.dumps({"summary": res, "rows": rows}, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
