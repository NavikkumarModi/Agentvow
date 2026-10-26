"""Plain-language explanation of a policy decision, for the person who has to act on it: what happened, what it means for the merge, what to do next, and what a pass does NOT show. Deterministic text from
the evaluation result (no model); every value that came from a receipt is stripped to harmless characters before it is shown. Used by the control plane's check run and by `agentvow policy explain`."""
import re

TITLES = {"allow": "Agentvow: nothing needs a person's attention (evidence, not proof)", "needs_acknowledgement": "Agentvow: a person must review and acknowledge this",
          "block": "Agentvow: blocked, this cannot merge as it is"}
HEADLINES = {
    "allow": "Agentvow replayed the checks and found nothing that needs a person's attention under this repository's policy. That is evidence to weigh, not proof that the change is correct.",
    "needs_acknowledgement": "Agentvow could not fully confirm this change. A person named in the repository's policy must look at it and acknowledge it before it can merge.",
    "block": "Agentvow will not let this through: a claim about this change was contradicted, a rule in this repository's policy is set to block it, or the check could not be trusted. It stays blocked until the cause is fixed.",
}
# rule -> (what it means, what to do). Written for a reviewer, not for an engineer who knows Agentvow's internals.
RULES = {
    "contradicted": ("A claim made about this change is false: tests that passed before the change fail after it.",
                     "Fix the code, or correct the claim. This cannot be acknowledged away."),
    "unknown": ("A claim could not be confirmed or refuted. Typical causes: the number of passing tests did not match what was said, a dependency or a credential the tests need was missing in the replay, or the only failures were ones that also happen without the change.",
                "Open the `gate / replay` job log for the exact cause (the receipt deliberately keeps no free text), decide whether you are satisfied, and if so a listed acknowledger replies on the pull request with the acknowledge command below."),
    "supported": ("The replay reproduced the claim: the tests the claim is about passed in a clean sandbox.", "Nothing to do for this item. The tests are written by the same code under review, so this is not proof of correctness."),
    "supported_confirm": ("The replay reproduced the claim, but this repository's policy asks a person to confirm even supported results.", "Review the change, then a listed acknowledger replies with the acknowledge command below."),
    "no_claims": ("The change made no claim that Agentvow can check, so nothing was confirmed or refuted.", "Review the change as you normally would; Agentvow has no opinion on it."),
    "unauthenticated_capture": ("The record of the agent's environment came from a file somebody supplied. Agentvow checked it against the exact files, but cannot tell who made it.",
                                "Acknowledge only if you trust whoever supplied it."),
    "partial_capture": ("The replay could not install some of the recorded packages on this runner and left them out, so it is not a full reproduction of the agent's environment.",
                        "Check whether the missing packages matter for the tests, then acknowledge or ask for another run."),
    "min_changed_line_coverage": ("Too few of the lines this change touched were run by the tests (or this was not measured), below the minimum the repository asks for.",
                                  "Add tests that run the changed lines, or acknowledge if the untested lines are acceptable."),
    "require_reproducibility": ("The repository's policy asks for the result to reproduce in more than one way, and it did not.", "Fix the setup so both replays can run, or acknowledge."),
    "unrecognized_verdict": ("The check produced a result this version of Agentvow does not recognise.", "Do not merge on this result; ask whoever runs Agentvow to update it."),
    "invalid_input": ("The receipt or the policy file could not be read as valid, so nothing was allowed.", "Fix the file named in the detail, then run the check again."),
    "policy_unreadable": ("The repository's policy file could not be read from the default branch, so nothing was allowed.", "Fix the policy file on the default branch (or the repository permissions), then run the check again."),
    "service": ("The service could not accept this receipt (for example the plan's allowance is used up or the repository needs a paid plan).", "Ask the owner of the Agentvow installation."),
}
NOT_SHOWN = "What this does not show: that the change is correct, that the tests are good, or that the code under test did not influence its own test output. Agentvow replays the checks independently of the agent's claim, not independently of the repository's own test code."


def _clean(x, n=300) -> str:
    return re.sub(r"[^\w .,;:()'/%+=-]", "", str(x))[:n]


def explain(result: dict, receipt_ids=(), acknowledgers=()) -> str:
    """Markdown for a check run summary or a pull request comment. `receipt_ids`: the ids a person can name when acknowledging (shown only when an acknowledgement is what is needed)."""
    receipt_ids = [receipt_ids] if isinstance(receipt_ids, str) else list(receipt_ids)
    decision = result.get("decision") if result.get("decision") in HEADLINES else "block"
    out = [HEADLINES[decision], ""]
    groups: dict = {}
    reasons = result.get("reasons") if isinstance(result.get("reasons"), list) else []
    for r in (x for x in reasons if isinstance(x, dict)):
        key = (str(r.get("rule", "")), str(r.get("outcome", "")), r.get("acknowledged_by") or "")
        groups.setdefault(key, []).append(r)
    if groups:
        out.append("**What Agentvow found**")
        for (rule, outcome, by), items in groups.items():
            key_ = "supported_confirm" if rule == "supported" and outcome == "needs_acknowledgement" else rule
            meaning, todo = RULES.get(key_, ("Agentvow reported something it has no plain description for.", "Read the detail."))
            if outcome == "block" and rule not in ("contradicted", "policy_unreadable", "invalid_input", "unrecognized_verdict", "service"):   # a rule the policy sets to block is not something a person can acknowledge
                todo = "This is blocked by the repository's policy and cannot be acknowledged: fix the cause, or ask a maintainer to change the policy."
            n = f" ({len(items)} claims)" if len(items) > 1 else ""
            line = f"- {meaning}{n}"
            if outcome == "allow":
                out.append(line)
                continue
            if by:
                line += f" **Acknowledged by @{_clean(by, 39)}.**"
            else:
                line += f" **What to do:** {todo}"
            out.append(line)
            out.append(f"  - Detail: {_clean(items[0].get('text', ''))} (rule: `{_clean(rule, 40)}`)")
        out.append("")
    if decision == "needs_acknowledgement" and receipt_ids:
        who = (" Listed acknowledgers: " + ", ".join("@" + _clean(a, 39) for a in acknowledgers) + ".") if acknowledgers else " The repository's policy lists no acknowledger yet, so nobody can acknowledge."
        ids = " and ".join(f"`/agentvow acknowledge {_clean(i, 64)[:12]}`" for i in receipt_ids[:3])
        many = " Each receipt that needs it needs its own comment:" if len(receipt_ids) > 1 else ""
        out += [f"**To acknowledge:**{many} a listed acknowledger comments {ids} on this pull request.{who} The acknowledger needs write access to the repository and cannot be the pull request's author (unless the author owns the repository). A contradiction can never be acknowledged.", ""]
    out.append(NOT_SHOWN)
    return "\n".join(out)
