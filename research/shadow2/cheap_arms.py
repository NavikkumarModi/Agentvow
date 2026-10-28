"""Cheap arms for every pool pull request (pre-registration, section 3): arm 1 CI only, arm 2 trust-the-report, arm 3 lexical text triage, and the static part of arm 5 (files and documentation statements checked against the pull
request's own change list with the product's own checks on a materialised head tree). Reads GitHub only (cached); runs no repository code. Output: data/shadow2/cheap.jsonl (resumable).
Usage: python3 research/shadow2/cheap_arms.py [--pool data/shadow2/pool.json] [--limit N]"""
import argparse
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
from common import ROOT, gh  # noqa: E402
sys.path.insert(0, str(ROOT / "research" / "audit_label"))
import score as audit_score  # noqa: E402  (verdicts_for uses the product's statement checks on a real head tree)
from agentvow import claims  # noqa: E402

OUT = ROOT / "data" / "shadow2" / "cheap.jsonl"
# arm 3: fixed in advance, lowercase phrases of confident closing language; score = number of distinct phrases present
CONFIDENT = ["all tests pass", "tests pass", "fully", "no breaking", "backward compatible", "backwards compatible", "100%", "all checks", "verified", "comprehensive", "seamless", "no impact",
             "no regression", "successfully", "everything", "production-ready", "ready for production", "no issues", "works as expected", "thoroughly"]


def ci_status(owner, repo, sha):
    runs = gh(f"repos/{owner}/{repo}/commits/{sha}/check-runs?per_page=100")
    st = gh(f"repos/{owner}/{repo}/commits/{sha}/status")
    cr = runs.get("check_runs", []) if isinstance(runs, dict) else []
    if not cr and not (isinstance(st, dict) and st.get("statuses")):
        return "none"
    bad = [c for c in cr if c.get("conclusion") not in ("success", "neutral", "skipped") or c.get("status") != "completed"]
    if bad or (isinstance(st, dict) and st.get("state") in ("failure", "error", "pending") and st.get("statuses")):
        return "failing_or_pending"
    return "success"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default="data/shadow2/pool.json")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args(argv)
    pool = json.loads((ROOT / a.pool).read_text())["sample"]
    bod = common.bodies()
    done = {json.loads(l)["pr"] for l in OUT.read_text().splitlines()} if OUT.exists() else set()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    for r in pool:
        if r["pr"] in done:
            continue
        if a.limit is not None and n >= a.limit:
            break
        n += 1
        b = bod.get(r["pr"], {}).get("body", "")
        owner, repo = r["repo"].split("/")
        rec = {"pr": r["pr"], "repo": r["repo"], "agent": r["agent"], "stratum": r["stratum"], "number": r["number"]}
        pr = gh(f"repos/{owner}/{repo}/pulls/{r['number']}")
        if not isinstance(pr, dict) or "head" not in pr:
            rec["error"] = "pull request not observable"
            with OUT.open("a") as f:
                f.write(json.dumps(rec) + "\n")
            continue
        rec["head"], rec["base"] = pr["head"]["sha"], pr["base"]["sha"]
        ex = claims.extract(b[-20000:])
        kinds = [c.kind for c in ex]
        rec["claims"] = [{"kind": c.kind, "text": c.text[:300]} for c in ex]
        rec["arm1_ci"] = ci_status(owner, repo, rec["head"])
        rec["arm1_decision"] = "proceed" if rec["arm1_ci"] == "success" else "review"
        rec["arm2_decision"] = "proceed" if any(k in ("tests_pass", "lint_clean") for k in kinds) else "review"
        low = b.lower()
        rec["arm3_lexical"] = sum(1 for p in CONFIDENT if p in low)
        rec["message_chars"] = len(b)
        item = {"repo": r["repo"], "number": r["number"], "message": b[-20000:]}
        try:
            vd = audit_score.verdicts_for(item)
            rec["arm5_static"] = [{"kind": k, "verdict": v, "text": t[:300], "ran": ok} for t, (k, v, ok) in vd.items() if k in ("files_scope", "docs_updated")]
        except Exception as e:   # a harness failure is recorded, never turned into a verdict
            rec["arm5_static_error"] = f"{type(e).__name__}: {str(e)[:150]}"
        files = gh(f"repos/{owner}/{repo}/pulls/{r['number']}/files?per_page=100", paginate=True)
        rec["changes_python"] = bool(isinstance(files, list) and any(f.get("filename", "").endswith(".py") for f in files))
        with OUT.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        print(r["pr"], rec["arm1_ci"], rec["arm3_lexical"], len(rec.get("arm5_static", [])), flush=True)


if __name__ == "__main__":
    main()
