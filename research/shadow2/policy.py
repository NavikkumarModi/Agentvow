"""Apply the frozen shadow policies (shadow_policy_v1.json) to the findings of one pull request -> 'proceed' | 'review'. Pure and deterministic; hypothetical decisions only (nothing acts)."""
import json
from pathlib import Path

POLICY = json.loads((Path(__file__).with_name("shadow_policy_v1.json")).read_text())["policies"]
NON_CLAIM_KINDS = {"snapshot", "none"}


def decide(findings: list, policy: str) -> str:
    """findings: [{'kind','verdict','attention'}]. 'none'/'snapshot' kinds are bookkeeping, not claims."""
    real = [f for f in findings if f.get("kind") not in NON_CLAIM_KINDS]
    for rule in POLICY[policy]["review_if"]:
        if rule.get("no_checkable_claim"):
            if not real:
                return "review"
        elif "verdict" in rule:
            for f in real:
                if f.get("verdict") == rule["verdict"] and ("kinds" not in rule or f.get("kind") in rule["kinds"]):
                    return "review"
        elif rule.get("attention"):
            if any(f.get("attention") for f in real):
                return "review"
    return "proceed"
