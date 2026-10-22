"""The pilot evidence report: what a team that gated its agent pull requests for a period is shown. Deterministic and mechanical: it counts receipts (`agentvow-receipt/1`) and re-evaluates each under the
team's policy; it makes no claim about defects prevented, bugs found or time saved, because the receipts cannot show them. Recommendations are fixed rules over the counts, not a model's opinion."""
import json
import statistics
from collections import Counter
from datetime import datetime
from pathlib import Path

from . import policy as policy_mod

LIMITS = ("What this report shows: how many agent pull requests went through the gate, what the replay said about each, how often the result could be reproduced in more than one way, how much of the "
          "changed code the tests ran, and what the replay could not recreate. What it does not show: that any change is correct, that any defect was prevented, or that review time was saved. "
          "The output of a test run is written by the code under test; a pass is evidence to weigh, not verification. The counts come from receipts the team's own runners produced.")


def load(dirpath) -> tuple:
    """-> (receipts, invalid count). Skips anything that is not a well-formed receipt."""
    out, bad = [], 0
    for f in sorted(Path(dirpath).glob("*.json")):
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            bad += 1
            continue
        if isinstance(r, dict) and r.get("schema") == policy_mod.RECEIPT and isinstance(r.get("claims"), list) and isinstance(r.get("commit"), str):
            out.append(r)
        else:
            bad += 1
    return out, bad


def load_acks(dirpath) -> list:
    out = []
    for f in sorted(Path(dirpath).glob("*.json")):
        try:
            a = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(a, dict) and a.get("schema") == policy_mod.ACK:
            out.append(a)
    return out


def _week(ts: str) -> str:
    try:
        d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        y, w, _ = d.isocalendar()
        return f"{y}-W{w:02d}"
    except (ValueError, AttributeError):
        return "unknown"


def summarize(receipts: list, policy: dict | None = None, acks: list | None = None) -> dict:
    # the latest receipt per commit is the one that counts (earlier ones stay in the audit trail but are not double counted)
    latest = {}
    for r in sorted(receipts, key=lambda x: x.get("created_at", "")):
        latest[(r.get("repo"), r.get("commit"))] = r
    rs = list(latest.values())
    dec, verdicts, repro, cats, weeks, attention = Counter(), Counter(), Counter(), Counter(), {}, []
    covs, unauth, acked = [], 0, 0
    for r in rs:
        ev = policy_mod.evaluate(r, policy, acks)
        d = ev["decision"]
        dec[d] += 1
        acked += any(x.get("acknowledged_by") for x in ev["reasons"])
        weeks.setdefault(_week(r.get("created_at", "")), Counter())[d] += 1
        for c in r["claims"]:
            verdicts[c.get("verdict", "?")] += 1
            if c.get("capture_authenticated") is False:
                unauth += 1
        repro[r.get("reproducibility") or "none"] += 1
        for k in r.get("not_reproduced") or []:
            cats[k] += 1
        cv = r.get("coverage") or {}
        if cv.get("executable"):
            covs.append((cv.get("executed") or 0) / cv["executable"])
        if d != "allow":
            attention.append({"commit": r.get("commit", "")[:10], "pr": r.get("pr"), "decision": d, "rules": sorted({x["rule"] for x in ev["reasons"] if x["outcome"] != "allow"})})
    n = len(rs)
    return {"receipts": n, "invalid": 0, "repo": sorted({r.get("repo") for r in rs})[:3], "first": min((r.get("created_at", "") for r in rs), default=""), "last": max((r.get("created_at", "") for r in rs), default=""),
            "prs": len({r.get("pr") for r in rs if r.get("pr")}), "decisions": dict(dec), "acknowledged": acked, "verdicts": dict(verdicts), "reproducibility": dict(repro), "categories": cats.most_common(8),
            "coverage": {"n": len(covs), "median": round(statistics.median(covs), 3) if covs else None, "below_half": sum(1 for c in covs if c < 0.5)},
            "unauthenticated_captures": unauth, "weeks": {k: dict(v) for k, v in sorted(weeks.items())}, "attention": attention[:25], "policy_given": policy is not None}


def recommendations(s: dict) -> list:
    n = s["receipts"]
    if not n:
        return ["No receipts were found for the period; check that the gate ran and that its artifacts or the control plane's export were collected."]
    out = []
    single = s["reproducibility"].get("single", 0) + s["reproducibility"].get("none", 0)
    if single / n > 0.5:
        out.append(f"{single} of {n} receipts had only one replay context. Capture the agent's environment at the end of each agent turn (`agentvow init` for Claude Code) so the replay can compare the agent's packages with what the repository declares.")
    unk = s["verdicts"].get("UNKNOWN", 0)
    tot = sum(s["verdicts"].values()) or 1
    if unk / tot > 0.3:
        out.append(f"{unk} of {sum(s['verdicts'].values())} claims were UNKNOWN. Each pull request comment names the cause and a next step. In the study behind Agentvow, the most common cause (7 of 10 misses by a repository-only replay) was a dependency that none of the repository's own files installed; others were credentials, network or services the replay does not recreate.")
    if s["coverage"]["n"] and s["coverage"]["below_half"] / s["coverage"]["n"] > 0.3:
        out.append(f"In {s['coverage']['below_half']} of {s['coverage']['n']} receipts with coverage data, the tests ran fewer than half of the changed lines. A low share means the tests did not execute much of the new code; ask whether tests exist for it.")
    if not s["policy_given"]:
        out.append("No policy file was supplied, so the default applied (a contradiction blocks, UNKNOWN needs a named person's acknowledgement). Add `.agentvow/policy.json` to the base branch to name acknowledgers and set a minimum for changed-line coverage.")
    if s["decisions"].get("block", 0):
        out.append(f"{s['decisions']['block']} change(s) were blocked by the policy. Review each: a contradiction means the check found the agent's claim false in the replay.")
    if not out:
        out.append("Nothing in the counts calls for action. Keep the gate on and review the pull requests listed below.")
    return out


def render_markdown(s: dict, title: str = "Agent pull request evidence report", example: bool = False) -> str:
    n = s["receipts"]
    o = [f"# {title}", ""]
    if example:
        o += ["> **Illustrative example built from synthetic receipts. Not data from any team.**", ""]
    o += [f"Repository: {', '.join(s['repo']) or 'n/a'}. Period: {s['first'][:10] or 'n/a'} to {s['last'][:10] or 'n/a'}. Receipts counted (latest per commit): **{n}**"
          + (f", covering {s['prs']} pull request(s)" if s["prs"] else "") + ".", "", "## What the gate decided", ""]
    if n:
        o += ["| Decision | Changes |", "|---|---|"] + [f"| {k} | {s['decisions'].get(k, 0)} |" for k in ("allow", "needs_acknowledgement", "block")]
        o += ["", f"Needs-acknowledgement changes that a named person then acknowledged: {s['acknowledged']}.", ""]
        o += ["## What the replay said about each claim", "", "| Verdict | Claims |", "|---|---|"] + [f"| {k} | {v} |" for k, v in sorted(s["verdicts"].items())] + [""]
        o += ["## How reproducible the results were", "", "| Contexts that ran and agreed | Changes |", "|---|---|"] + [f"| {k} | {v} |" for k, v in sorted(s["reproducibility"].items())]
        o += ["", "`both`: the agent's captured packages and the repository's own files both reproduced the result. `captured_only` / `native_only`: only one did. `single`: only one context ran. `neither`: no context reproduced a pass.", ""]
        c = s["coverage"]
        o += ["## How much of the changed code the tests ran", "", (f"Median fraction of changed executable lines run by the tests: **{c['median']:.0%}** over {c['n']} receipts with coverage data; "
                                                                      f"{c['below_half']} had fewer than half of the changed lines run." if c["n"] else "No receipt had changed-line coverage data."), ""]
        if s["categories"]:
            o += ["## What the replay could not recreate (named, not judged)", "", "| Category | Receipts |", "|---|---|"] + [f"| {k} | {v} |" for k, v in s["categories"]] + [""]
        if s["unauthenticated_captures"]:
            o += [f"{s['unauthenticated_captures']} claim(s) used a capture supplied as a file (checked against the exact files and replayed, but not authenticated).", ""]
        if len(s["weeks"]) > 1:
            o += ["## By week", "", "| Week | allow | needs_acknowledgement | block |", "|---|---|---|---|"] + [f"| {w} | {d.get('allow', 0)} | {d.get('needs_acknowledgement', 0)} | {d.get('block', 0)} |" for w, d in s["weeks"].items()] + [""]
        if s["attention"]:
            o += ["## Changes that were not simply allowed", "", "| Commit | PR | Decision | Rules |", "|---|---|---|---|"] + [f"| `{a['commit']}` | {a['pr'] or ''} | {a['decision']} | {', '.join(a['rules'])} |" for a in s["attention"]] + [""]
    o += ["## What we recommend", ""] + [f"- {x}" for x in recommendations(s)] + ["", "## Limits of this report", "", LIMITS, ""]
    return "\n".join(o)
