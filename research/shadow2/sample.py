"""Choose the pull requests to label (pre-registration, section 4), after the cheap arms and the full arm 5 have run and before any label exists. Deterministic given the seed.
F = pull requests flagged by at least one of: arm 5 under the STRICT policy; arm 3 in its top 15% lexical scores; arm 1 with failing or pending CI. All of F is labelled up to a cap (default 220; above it F is subsampled with a seeded
probability recorded per pull request); of the rest, a seeded 10% is labelled. Each pull request gets its inclusion probability; weight = 1/probability.
Arm 5 findings for a pull request = the static files/docs findings + the full-run findings when the pull request was run + UNKNOWN for every other tests, lint or impact claim (not run: the product cannot run it).
Usage: python3 research/shadow2/sample.py --seed N [--cap 220] [--rest-rate 0.10]  -> data/shadow2/label_sample.json"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import policy  # noqa: E402

KINDS = {"tests_pass", "lint_clean", "backward_compatible", "no_downstream_impact"}


def arm5_findings(cheap, full):
    f = [{"kind": x["kind"], "verdict": x["verdict"] if x.get("ran") else "UNKNOWN", "attention": x["verdict"] == "CONTRADICTED"} for x in cheap.get("arm5_static", [])]   # a files/docs mismatch is attention (the product turns it into UNKNOWN + attention)
    f = [{**x, "verdict": "UNKNOWN" if x["attention"] else x["verdict"]} for x in f]
    if full and full.get("outcome") == "ran":
        f += [{"kind": x["kind"], "verdict": x["verdict"], "attention": bool(x.get("attention"))} for x in full.get("findings", []) if x["kind"] in KINDS]
        covered = {x["kind"] for x in full.get("findings", [])}
    else:
        covered = set()
    for c in cheap.get("claims", []):
        if c["kind"] in KINDS and c["kind"] not in covered:
            f.append({"kind": c["kind"], "verdict": "UNKNOWN", "attention": False})
            covered.add(c["kind"])
    return f


def arm5_score(findings):
    s = 0
    for x in findings:
        if x["verdict"] == "CONTRADICTED":
            s = max(s, 3)
        elif x.get("attention"):
            s = max(s, 2)
        elif x["verdict"] == "UNKNOWN" and x["kind"] in KINDS:
            s = max(s, 1)
    return s


def u(seed, tag, pr):
    return int(hashlib.sha256(f"{seed}|{tag}|{pr}".encode()).hexdigest()[:12], 16) / 16**12


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--cap", type=int, default=220)
    ap.add_argument("--rest-rate", type=float, default=0.10)
    a = ap.parse_args(argv)
    cheap = [json.loads(l) for l in (ROOT / "data/shadow2/cheap.jsonl").read_text().splitlines()]
    cheap = [c for c in cheap if "head" in c]
    full = {json.loads(l)["pr"]: json.loads(l) for l in (ROOT / "data/shadow2/full_arm5.jsonl").read_text().splitlines()} if (ROOT / "data/shadow2/full_arm5.jsonl").exists() else {}
    lex = sorted((c["arm3_lexical"] for c in cheap), reverse=True)
    thr = lex[max(0, int(0.15 * len(lex)) - 1)] if lex else 0
    rows = []
    for c in cheap:
        f5 = arm5_findings(c, full.get(c["pr"]))
        strict = policy.decide(f5, "strict")
        flags = {"arm5_strict": strict == "review", "arm3_top15": c["arm3_lexical"] >= thr and c["arm3_lexical"] > 0, "arm1_failing": c["arm1_ci"] == "failing_or_pending"}
        rows.append({"pr": c["pr"], "repo": c["repo"], "flagged": any(flags.values()), "flags": flags, "arm5_score": arm5_score(f5), "strict": strict, "lenient": policy.decide(f5, "lenient")})
    F = [r for r in rows if r["flagged"]]
    p_f = min(1.0, a.cap / len(F)) if F else 1.0
    out = []
    for r in rows:
        p = p_f if r["flagged"] else a.rest_rate
        r["prob"] = round(p, 6)
        r["selected"] = u(a.seed, "sel", r["pr"]) < p
        r["weight"] = round(1 / p, 4)
        out.append(r)
    sel = [r for r in out if r["selected"]]
    res = {"seed": a.seed, "cap": a.cap, "rest_rate": a.rest_rate, "lexical_threshold": thr, "pool": len(rows), "flagged": len(F), "p_flagged": p_f, "selected": len(sel),
           "selected_flagged": sum(r["flagged"] for r in sel), "selected_rest": sum(not r["flagged"] for r in sel), "rows": out}
    (ROOT / "data/shadow2/label_sample.json").write_text(json.dumps(res, indent=1))
    print({k: v for k, v in res.items() if k != "rows"})


if __name__ == "__main__":
    main()
