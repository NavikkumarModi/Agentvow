"""Receipts and policy (open, local, deterministic; no model).

A **receipt** (`agentvow-receipt/1`) is the minimal, shareable record of one check: which exact state it is about (commit and git tree hash), what each claim's verdict and basis was, what the replay contexts
found, the changed-line coverage, and the NAMES of the categories the replay could not reproduce. No source code, no free-text explanations (they can contain paths), no environment values.
A **policy** (`agentvow-policy/1`) turns a receipt into allow / block / needs_acknowledgement, with reasons in plain language. A contradiction can never be acknowledged away; an UNKNOWN or a
missing proof can be, by a named person, for exactly one receipt. In CI the policy file must come from the BASE branch, never from the pull request being judged (a pull request could weaken its own policy)."""
import hashlib
import re
import json
from datetime import datetime, timezone

from . import __version__

RECEIPT = "agentvow-receipt/1"
POLICY = "agentvow-policy/1"
ACK = "agentvow-ack/1"
OUTCOMES = ("allow", "needs_acknowledgement", "block")
_RANK = {"allow": 0, "needs_acknowledgement": 1, "block": 2}
DEFAULT_POLICY = {"schema": POLICY, "contradicted": "block", "unknown": "needs_acknowledgement", "supported": "allow", "no_claims": "needs_acknowledgement",
                  "require_reproducibility": None, "min_changed_line_coverage": None, "unauthenticated_capture": "needs_acknowledgement", "partial_capture": "needs_acknowledgement", "acknowledgers": []}
_POLICY_ENUMS = {"contradicted": ("block",), "unknown": OUTCOMES, "supported": OUTCOMES, "no_claims": OUTCOMES, "unauthenticated_capture": OUTCOMES, "partial_capture": OUTCOMES, "require_reproducibility": (None, "both", "any")}
_SUPPORTED = ("SUPPORTED_BY_PRIOR_EVIDENCE", "NOT_CONTRADICTED")


def canon(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def sha(obj) -> str:
    return hashlib.sha256(canon(obj)).hexdigest()


_KNOWN_VERDICTS = ("SUPPORTED_BY_PRIOR_EVIDENCE", "NOT_CONTRADICTED", "UNKNOWN", "CONTRADICTED")
MAX_CLAIMS, MAX_LIST = 200, 100


def build_receipt(decision: dict, repo: str, git_tree: str, base: str = "", pr: int | None = None) -> dict:
    """From the JSON that `agentvow check --json` prints. `repo` is `owner/name` as the caller (the CI runner) knows it."""
    claims = []
    for f in decision.get("findings", []):
        meta = f.get("meta") or {}
        cov = meta.get("changed_line_coverage") or {}
        claims.append({"kind": str(f.get("kind", ""))[:40], "verdict": str(f.get("verdict", ""))[:40], "basis": str(meta.get("support_basis", ""))[:40],
                       "capture_source": str(meta.get("capture_source", ""))[:20], "dropped_pins": len(meta.get("dropped_pins") or []),
                       # provenance of the capture, kept apart (never one "verified" flag): where it came from, whether the source was authenticated, what bound it to the files, whether the replay used all of it
                       "capture_authenticated": {"local": True, "bundle": False}.get(str(meta.get("capture_source", ""))), "state_binding": {"local": "capsule", "bundle": "git_tree"}.get(str(meta.get("capture_source", "")), ""),
                       "partial_replay": bool(meta.get("dropped_pins")),
                       "changed_lines": {"executed": cov.get("executed"), "executable": cov.get("executable")} if cov else None})
    if len(claims) > MAX_CLAIMS:   # keep the worst claims; say that some were left out (as an UNKNOWN claim, which is never read as support)
        order = {"CONTRADICTED": 0, "UNKNOWN": 1}
        claims = sorted(claims, key=lambda c: order.get(c["verdict"], 2))[:MAX_CLAIMS - 1] + [{"kind": "truncated", "verdict": "UNKNOWN", "basis": "", "capture_source": "", "dropped_pins": 0, "changed_lines": None}]
    pack = decision.get("pack") or {}
    cov = pack.get("coverage") or {}
    return {"schema": RECEIPT, "tool_version": __version__, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "repo": repo, "commit": decision.get("commit", ""),
            "git_tree": git_tree, "base": base, "pr": pr if isinstance(pr, int) and pr > 0 else None, "status": decision.get("status", ""), "claims": claims, "unexamined": int(decision.get("unexamined") or 0),
            "reproducibility": (pack.get("reproducibility") or {}).get("code", ""),
            "contexts": [{"name": str(c.get("name", ""))[:60], "result": str(c.get("result", ""))[:20], "passed": (c.get("counts") or {}).get("passed"), "failed": (c.get("counts") or {}).get("failed"),
                          "dropped_pins": len(c.get("dropped_pins") or [])} for c in pack.get("contexts", [])],
            "coverage": {"executed": cov.get("executed"), "executable": cov.get("executable")} if cov.get("available") else None,
            "not_reproduced": [str(i.get("category", ""))[:80] for i in (pack.get("manifest") or {}).get("items", [])]}




def _count(x) -> bool:
    return x is None or (isinstance(x, int) and not isinstance(x, bool) and 0 <= x <= 10**9)


def validate_receipt(r) -> str | None:
    """None when the receipt is well formed, else why not. Strict about types and sizes: everything downstream (the policy, the service, the report) may assume what this accepts."""
    if not isinstance(r, dict) or r.get("schema") != RECEIPT:
        return f"not an {RECEIPT} receipt"
    for k in ("repo", "commit", "git_tree"):
        if not isinstance(r.get(k), str) or not r[k] or len(r[k]) > 200:
            return f"{k} must be a short string"
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", r["commit"]) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", r["git_tree"]):
        return "commit and git_tree must be full hexadecimal object ids"
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}", r["repo"]) or ".." in r["repo"]:
        return "repo must look like owner/name"
    cl = r.get("claims")
    if not isinstance(cl, list) or len(cl) > MAX_CLAIMS:
        return "claims must be a list"
    for c in cl:
        if not isinstance(c, dict) or not isinstance(c.get("kind", ""), str) or not isinstance(c.get("verdict"), str) or not isinstance(c.get("capture_source", ""), str):
            return "each claim needs string kind and verdict"
        lines = c.get("changed_lines")
        if lines is not None and (not isinstance(lines, dict) or not _count(lines.get("executed")) or not _count(lines.get("executable"))):
            return "changed_lines must hold non-negative whole numbers"
        if not _count(c.get("dropped_pins", 0)):
            return "dropped_pins must be a whole number"
        if not (c.get("capture_authenticated") is None or isinstance(c.get("capture_authenticated"), bool)) or not isinstance(c.get("partial_replay", False), bool) or not isinstance(c.get("state_binding", ""), str) or len(c.get("state_binding", "")) > 20:
            return "capture provenance fields have the wrong type"
    cov = r.get("coverage")
    if cov is not None and (not isinstance(cov, dict) or not _count(cov.get("executed")) or not _count(cov.get("executable"))):
        return "coverage must hold non-negative whole numbers"
    for k in ("not_reproduced",):
        v = r.get(k, [])
        if not isinstance(v, list) or len(v) > MAX_LIST or not all(isinstance(x, str) and len(x) <= 120 for x in v):
            return f"{k} must be a short list of short strings"
    if not isinstance(r.get("reproducibility", ""), str) or len(r.get("reproducibility", "")) > 40:
        return "reproducibility must be a short string"
    if r.get("pr") is not None and not (isinstance(r["pr"], int) and not isinstance(r["pr"], bool) and r["pr"] > 0):
        return "pr must be a positive whole number or null"
    if len(canon(r)) > 60_000:
        return "receipt is too large"
    return None


def validate_policy(p) -> str | None:
    if not isinstance(p, dict) or p.get("schema") != POLICY:
        return f"not an {POLICY} policy"
    extra = set(p) - set(DEFAULT_POLICY)
    if extra:
        return f"unknown policy keys: {sorted(extra)}"
    for k, allowed in _POLICY_ENUMS.items():
        if k in p and p[k] not in allowed:
            return f"{k} must be one of {list(allowed)}"
    m = p.get("min_changed_line_coverage")
    if m is not None and not (isinstance(m, (int, float)) and not isinstance(m, bool) and 0 <= m <= 1):
        return "min_changed_line_coverage must be a number between 0 and 1"
    a = p.get("acknowledgers", [])
    if not isinstance(a, list) or not all(isinstance(x, str) and 0 < len(x) <= 80 for x in a):
        return "acknowledgers must be a list of user names"
    return None


def _valid_ack(a, receipt_sha: str, ackers: set) -> bool:
    return (isinstance(a, dict) and a.get("schema") == ACK and a.get("receipt_sha") == receipt_sha and isinstance(a.get("by"), str) and a["by"].lower() in ackers)


def evaluate(receipt: dict, policy: dict | None = None, acks: list | None = None) -> dict:
    """-> {"decision", "conclusion", "reasons", "policy_sha", "receipt_sha"}. Deterministic. Acknowledgements count only if made by a listed acknowledger for exactly this receipt."""
    pol = {**DEFAULT_POLICY, **(policy or {})}
    bad = validate_policy(pol)
    bad_r = validate_receipt(receipt)
    if bad or bad_r:
        why = f"The policy is invalid ({bad})" if bad else f"The receipt is malformed ({bad_r})"
        return {"decision": "block", "conclusion": "failure", "reasons": [{"rule": "invalid_input", "outcome": "block", "text": f"{why}; nothing was allowed.", "acknowledged_by": None}],
                "policy_sha": "" if bad else sha(pol), "receipt_sha": sha(receipt) if isinstance(receipt, (dict, list, str, int, float, type(None))) else ""}
    rsha = sha(receipt)
    ackers = {x.lower() for x in pol["acknowledgers"]}
    good = [a for a in (acks or []) if _valid_ack(a, rsha, ackers)]
    reasons = []

    def add(rule, outcome, text):
        by = None
        if outcome == "needs_acknowledgement" and good:
            by = good[0]["by"]
        reasons.append({"rule": rule, "outcome": outcome, "text": text, "acknowledged_by": by})

    claims = receipt.get("claims") or []
    if not claims:
        add("no_claims", pol["no_claims"], "The agent made no claim that could be checked, so there is nothing to confirm or refute.")
    for c in claims:
        v = str(c.get("verdict", "")).strip().upper()
        kind = str(c.get("kind", "claim"))[:40]
        if v == "CONTRADICTED":
            add("contradicted", pol["contradicted"], f"The check found the '{kind}' claim contradicted. A contradiction cannot be acknowledged away: change the code or correct the claim.")
        elif v in _SUPPORTED:
            add("supported", pol["supported"], f"The '{kind}' claim was supported by the replay.")
            if c.get("capture_source") == "bundle":
                add("unauthenticated_capture", pol["unauthenticated_capture"], "The package capture was supplied as a file and is not authenticated (it was checked against the exact files and replayed here; the packages it names were chosen by whoever made it).")
            if c.get("partial_replay") or (c.get("dropped_pins") or 0) > 0:
                add("partial_capture", pol["partial_capture"], f"The replay left out {c.get('dropped_pins') or 'some'} pinned package(s) it could not install on the runner, so it is not a reproduction from the complete captured environment.")
            cl = c.get("changed_lines") or receipt.get("coverage") or {}
            m = pol["min_changed_line_coverage"]
            if m is not None:
                ex, exe = cl.get("executed"), cl.get("executable")
                if exe is None:
                    add("min_changed_line_coverage", "needs_acknowledgement", "The policy asks for a minimum of changed lines run by the tests, but changed-line coverage was not measured for this change.")
                elif exe > 0 and (ex or 0) / exe < m:
                    add("min_changed_line_coverage", "needs_acknowledgement", f"Only {ex or 0} of {exe} changed lines were run by the tests ({(ex or 0) / exe:.0%}); the policy asks for {m:.0%}.")
        elif v == "UNKNOWN":
            add("unknown", pol["unknown"], f"The '{kind}' claim could not be confirmed or refuted (UNKNOWN): the evidence was missing or the replay could not run.")
        else:
            add("unrecognized_verdict", "block", f"The '{kind}' claim has a verdict this version does not recognise ({str(c.get('verdict'))[:30]!r}); nothing was allowed.")
    req = pol["require_reproducibility"]
    if req and claims:
        code = receipt.get("reproducibility", "")
        ok = (code == "both") if req == "both" else (code in ("both", "captured_only", "native_only", "single"))
        if not ok:
            add("require_reproducibility", "needs_acknowledgement", f"The policy asks for reproducibility '{req}', but the receipt says '{code or 'none'}'.")
    eff = "allow"
    for r in reasons:
        o = r["outcome"] if not (r["outcome"] == "needs_acknowledgement" and r["acknowledged_by"]) else "allow"
        if _RANK[o] > _RANK[eff]:
            eff = o
    concl = {"allow": "success", "needs_acknowledgement": "action_required", "block": "failure"}[eff]
    return {"decision": eff, "conclusion": concl, "reasons": reasons, "policy_sha": sha(pol), "receipt_sha": rsha}
