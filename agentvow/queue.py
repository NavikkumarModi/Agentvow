"""The review queue: one ranked list of the agent pull requests that need a person, built from a directory of receipts (`agentvow-receipt/1`) and a policy. Deterministic: it re-evaluates each receipt under the policy
(agentvow.policy.evaluate) and orders the result; it adds no judgement of its own. It never says a change is safe: "no flag" means no policy rule asked for a person."""
from . import pilot_report, policy as policy_mod

ORDER = {"block": 0, "needs_acknowledgement": 1, "acknowledged": 2, "unverified": 3, "allow": 4}
LABEL = {"block": "stop: a check contradicted the agent", "needs_acknowledgement": "needs a person", "acknowledged": "a person has acknowledged", "unverified": "receipt not authenticated: its result is not trusted", "allow": "no flag raised"}
FOOTER = ("'No flag raised' means no policy rule asked for a person on this receipt; it is not a statement that the change is correct or safe. A queue entry is a reason to look, not a finding that something is wrong. "
          "Each entry lists the reasons the policy gave; open the receipt for the evidence.")


def _state(ev: dict) -> str:
    if ev["decision"] == "needs_acknowledgement":
        return "needs_acknowledgement"
    if ev["decision"] == "block":
        return "block"
    return "acknowledged" if any(r.get("acknowledged_by") for r in ev["reasons"]) else "allow"


def build(receipts: list, policy: dict | None = None, acks: list | None = None, limit_reasons: int = 3, auth: dict | None = None, mode: str = "off") -> list:
    """`auth` maps (repo, commit) to (ok, why) from ghreceipts; `mode` is off | report | require. A receipt that did not verify is never ranked as 'no flag raised': in report mode it is 'unverified', in require mode it needs a person."""
    latest = {}
    for r in sorted(receipts, key=lambda x: x.get("created_at", "")):
        latest[(r.get("repo"), r.get("commit"))] = r   # the latest receipt per commit counts, as in the pilot report
    out = []
    for r in latest.values():
        ev = policy_mod.evaluate(r, policy, acks)
        state = _state(ev)
        reasons = [x for x in ev["reasons"] if x["outcome"] != "allow" or (x.get("acknowledged_by") and x["outcome"] == "needs_acknowledgement")]
        claims = r.get("claims") or []
        verdict = (auth or {}).get((r.get("repo"), r.get("commit"))) if mode != "off" else None
        authn = None if verdict is None else ("verified" if verdict[0] else "unverified")
        if authn == "unverified":
            reasons = reasons + [{"rule": "receipt_authentication", "text": f"This receipt could not be authenticated ({verdict[1]}), so its result may not come from the gate. Treat it as no information until it is verified."}]
            if state in ("allow", "acknowledged"):
                state = "needs_acknowledgement" if mode == "require" else "unverified"
        out.append({"repo": str(r.get("repo", ""))[:100], "pr": r.get("pr"), "commit": str(r.get("commit", ""))[:10], "created_at": str(r.get("created_at", ""))[:25], "state": state, "auth": authn,
                    "contradicted": sum(1 for c in claims if str(c.get("verdict", "")).upper() == "CONTRADICTED"),
                    "unknown": sum(1 for c in claims if str(c.get("verdict", "")).upper() == "UNKNOWN"),
                    "reasons": [{"rule": x["rule"], "text": x["text"]} for x in reasons[:limit_reasons]], "more_reasons": max(0, len(reasons) - limit_reasons)})
    out.sort(key=lambda x: (ORDER[x["state"]], -x["contradicted"], -x["unknown"], x["created_at"], x["repo"], x["commit"]))
    return out


def _name(i: dict) -> str:
    return f"{i['repo']}#{i['pr']}" if i["pr"] else f"{i['repo']}@{i['commit']}"


def _missing_text(missing, note):
    if not missing and not note:
        return []
    out = []
    if missing:
        out.append(f"{len(missing)} open pull request(s) with no usable receipt (no information, not a clean result): " + ", ".join(f"#{m['pr']} ({m['why']})" for m in missing[:20]) + (f", and {len(missing) - 20} more" if len(missing) > 20 else ""))
    if note:
        out.append(note)
    return out


def render_text(items: list, missing: list | None = None, note: str = "") -> str:
    n = {s: sum(1 for i in items if i["state"] == s) for s in ORDER}
    head = f"{len(items)} receipt(s): {n['block']} stop, {n['needs_acknowledgement']} need a person, {n['acknowledged']} acknowledged, " + (f"{n['unverified']} not authenticated, " if n["unverified"] else "") + f"{n['allow']} with no flag raised.\n"
    lines = [head]
    for i in items:
        lines.append(f"[{LABEL[i['state']]}] {_name(i)}{' [verified]' if i.get('auth') == 'verified' else ''}  (commit {i['commit']}; {i['contradicted']} contradicted, {i['unknown']} unknown)")
        for r in i["reasons"]:
            lines.append(f"    - {r['text']}")
        if i["more_reasons"]:
            lines.append(f"    - ... and {i['more_reasons']} more")
    lines += [""] + _missing_text(missing, note)
    lines.append("\n" + FOOTER)
    return "\n".join(lines) + "\n"


def render_markdown(items: list, title: str = "Agent pull request review queue", missing: list | None = None, note: str = "") -> str:
    md = lambda x: pilot_report._md(x, 220)
    n = {s: sum(1 for i in items if i["state"] == s) for s in ORDER}
    out = [f"# {md(title)}", "", f"{len(items)} receipt(s): **{n['block']}** stop, **{n['needs_acknowledgement']}** need a person, {n['acknowledged']} acknowledged, " + (f"{n['unverified']} not authenticated, " if n["unverified"] else "") + f"{n['allow']} with no flag raised.", ""]
    for st in ("block", "needs_acknowledgement", "acknowledged", "unverified", "allow"):
        group = [i for i in items if i["state"] == st]
        if not group:
            continue
        out += [f"## {LABEL[st].capitalize()} ({len(group)})", ""]
        for i in group:
            out.append(f"- **{md(_name(i))}**{' [verified]' if i.get('auth') == 'verified' else ''} (commit `{md(i['commit'])}`, {i['contradicted']} contradicted, {i['unknown']} unknown)")
            out += [f"  - {md(r['text'])}" for r in i["reasons"]]
            if i["more_reasons"]:
                out.append(f"  - ... and {i['more_reasons']} more")
        out.append("")
    out += [md(x) for x in _missing_text(missing, note)]
    out += ["---", FOOTER, ""]
    return "\n".join(out)
