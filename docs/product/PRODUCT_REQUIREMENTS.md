# Product Requirements (draft; implementation blocked on G2)

## Users
Primary: a human approving an autonomous agent's change, possibly non-technical. Secondary: engineer drilling into evidence.

## Must answer
1. What did the agent do? 2. What does it believe happened? 3. What does available reality show? 4. What exactly am I deciding?

## Requirements
- R1 Ingest without modifying the agent (transcript + repo first; OTel/MCP later).
- R2 Separate CLAIM / OBSERVATION / EVIDENCE / INFERENCE / ASSUMPTION / UNKNOWN in every view.
- R3 Every evidence object carries provenance, collector, snapshot, hash, freshness, independence vector.
- R4 Discover prior work; classify reusable / stale / contradictory / claim-only.
- R5 Reconcile claims: SUPPORTED_BY, CONTRADICTED_BY, INCOMPLETE_BECAUSE, UNKNOWN_ABOUT.
- R6 Surface only decision-changing findings by default; everything else one click away.
- R7 Approval text states action, scope, expected effect, affected components, risks, reversibility, evidence, unknowns, and what it does NOT authorize.
- R8 Translator never introduces facts not in the decision object.
- R9 Never approve, reject, merge or deploy.
- R10 Deterministic collectors preferred; no LLM in verdict path.

## v0.1 CLI output (first milestone)
Agent claim → independent reality → evidence list (with validity) → conflict → unknown → decision impact → status (REVIEW REQUIRED / NO DECISION-CHANGING FINDINGS / INSUFFICIENT EVIDENCE).
Note "no findings" must never render as "safe" when UNKNOWNs exist.

## Non-requirements for v0.1
VS Code, desktop, web UI, protocol adapters beyond transcript/git/filesystem.
