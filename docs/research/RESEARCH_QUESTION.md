# Research Question, Thesis, Non-Goals, Scope (G0)

## Research question

Can an agent-independent model of system reality identify **decision-changing** divergences in confidently asserted agent conclusions, and improve human oversight **without increasing review burden**?

## Thesis

An agent's explanation represents its belief, not proof of reality. Therefore:

- AGENT CLAIM ≠ EVIDENCE
- AGENT CONFIDENCE ≠ TRUTH
- MULTI-AGENT AGREEMENT ≠ INDEPENDENT VERIFICATION

The last is empirically supported: LLM judge panels show correlated errors (e.g. 9 judges ≈ 2 effective votes `[snippet]`, see RELATED_WORK). The first two are design premises.

## Primitive: Decision-Changing Reality Divergence Detection (DCRD)

Given claim C, proposed action A, reality graph G, independently observed evidence E, policies P, state S.

Find plausible S' such that:
1. S' is consistent with E (and P-compatible facts), and
2. S' differs materially from the state the agent assumed, and
3. decision(A | S') ≠ decision(A | S_assumed).

Output only findings that pass all three. Three-valued result per claim: SUPPORTED / CONTRADICTED / UNKNOWN, where UNKNOWN is emitted when a decision-flipping S' cannot be ruled out by evidence.

## Hypotheses
H1–H7 as in the master plan (harmful approvals, automation bias, downstream detection, UNKNOWN recognition, reuse, compression, reality-challenge vs model agreement). H7 is the core one. H5 (reuse) is likely the weakest novelty but easiest win.

## Non-goals
Not an observability dashboard, LLM judge, self-reflection prompt, generic coding-agent UI, static-analysis/architecture/policy-engine replacement, or chatbot. AgentMirror composes existing tools and contributes the decision-centric layer. It never approves, merges or deploys.

## SOTA scope
Domains: agent observability; trajectory visualization; claim/transcript verification; snapshot-bound verification; verification independence; LLM-judge reliability; architecture-aware agents; policy/runtime verification; provenance/evidence; agent memory staleness; blast-radius/impact analysis; counterfactual explanation; human oversight (automation bias, approval fatigue); protocols (OTel GenAI, MCP, A2A, ACP). Initial domain: coding agents. Sources: arXiv, GitHub, vendor docs, standards. Patent search: see PRIOR_ART.md limitation.
