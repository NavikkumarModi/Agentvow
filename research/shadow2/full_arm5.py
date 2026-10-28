"""Full arm 5 on the Python pull requests of the pool (pre-registration, section 3): the frozen audit (`agentvow check --setup auto --run-tests --json`) on pull requests that change Python files and carry a tests, lint or impact claim,
one at a time, clone deleted afterwards, as in stage 2 of the audit study (the runner is reused). Repository code runs only inside Agentvow's own sandbox (owner authorisation 2026-10-28 for installs and test runs of these open-source
repositories; confirm in the freeze record). Output: data/shadow2/full_arm5.jsonl (resumable)."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research" / "audit_label"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import stage2_run as s2  # noqa: E402
import common  # noqa: E402

OUT = ROOT / "data" / "shadow2" / "full_arm5.jsonl"
KINDS = {"tests_pass", "lint_clean", "backward_compatible", "no_downstream_impact"}


def targets():
    bod = common.bodies()
    out = []
    for l in (ROOT / "data/shadow2/cheap.jsonl").read_text().splitlines():
        r = json.loads(l)
        if r.get("changes_python") and any(c["kind"] in KINDS for c in r.get("claims", [])) and "head" in r:
            out.append({"item": "pr_" + r["pr"].split("github.com/")[1].replace("/", "__").replace("pull__", "pull_"), "repo": r["repo"], "number": r["number"], "base": r["base"], "head": r["head"],
                        "message": bod[r["pr"]]["body"][-20000:], "pr": r["pr"]})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    a = ap.parse_args(argv)
    s2.SCRATCH = Path(str(s2.SCRATCH).replace("stage2", "shadow2"))
    done = {json.loads(l)["item"] for l in OUT.read_text().splitlines()} if OUT.exists() else set()
    n = 0
    for t in targets():
        if t["item"] in done:
            continue
        if a.limit is not None and n >= a.limit:
            break
        rec = s2.run_one(t)
        rec["pr"] = t["pr"]
        with OUT.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        n += 1
        print(t["item"], rec["outcome"], rec.get("status"), rec.get("seconds"), flush=True)


if __name__ == "__main__":
    main()
