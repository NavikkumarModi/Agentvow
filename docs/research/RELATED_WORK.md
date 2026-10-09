# Related Work (first pass; all `[snippet]`)

## 1. Claim-vs-reality verification for coding agents
backcheck, Aga Verify Agent, AgentCheck and Receipts share one principle: no model in the verdict path; bind verification to the actual repository state. They are the nearest products to AgentMirror's reconciliation layer. Differences: they verify *completion claims* ("tests pass", "fixed") against the agent's own transcript or re-run commands. None (from snippets) models system reality beyond the diff (consumers, architecture, policy) or asks whether an unverified state could flip the decision.

## 2. Evidence and provenance for agents
NIST evaluation probes, ClaimReceipt, the Decision Evidence Maturity Model, NovaFabric, Agent Flight Recorder, Agent-Native Telemetry and the evidence-tracing survey (2606.04990) cover tamper-evident records, sufficiency/coverage and audit trails. They address "is the record trustworthy / sufficient", not "what plausible reality contradicts the conclusion".

## 3. Memory staleness and verification reuse
EA-Graph (2608.04278) anchors verification memory to artifacts under upstream drift; TEPA, "When Stale Constraints Go Unchecked" and revocation studies address stale retained beliefs. Work Memory (snapshot-bound reuse of others' evidence) is therefore **not novel**; it is engineering, with EA-Graph as the closest baseline to read and beat/adopt.

## 4. Independence of verification
Correlated-error results for LLM panels (2609.22512, 2605.29800, 2606.29270) justify the independence vector. Independence-aware evaluation (Zenodo 22368667) and Maat (2609.34017) propose related ideas. The four-axis vector (framing/evidence/mechanism/authority) needs a check against these.

## 5. Architecture and policy awareness
archagent supplies deterministic architecture-invariant checking; OPA/Cedar/AgentCore Policy/Dogwood supply pre-action authorization and action-sequence runtime verification. These are sources of reality evidence to import.

## 6. Impact / blast-radius analysis
Commercial and OSS tools compute downstream consumers from dependency graphs at PR time. The "hidden downstream dependency" detector is an existing capability; AgentMirror should consume it.

## 7. Visualization and observability
AgentGUI, Agent Trajectory Explorer, TraceView, Graphectory and OTel-based stacks show trajectories. None claims decision-centric claim/reality views. Agent Map is an engineering/UX contribution only.

## 8. Counterfactual search
Counterfactual-state explanation in RL (ACTER, minimal counterfactuals, robustness regions) is the conceptual ancestor of "find a plausible state that flips the decision". Transfer to evidence-consistent counter-realities for SE claims is the candidate gap; must check program-analysis literature (symbolic execution, abstract interpretation, may/must analysis) which also reasons about "possible states consistent with observations".

## 9. Human oversight
Automation bias and approval fatigue are well documented `[snippet]`. Whether claim/evidence separation and UNKNOWN states reduce harmful approvals is untested for coding agents; "Humans are Missing from AI Coding Agent Research" (2608.12355) supports the need for human-centred evaluation.

## 10. Protocols
OTel GenAI conventions are all "Development" status: use an adapter layer. MCP is widely adopted; A2A less; ACP reportedly merged into A2A (verify before building an ACP adapter).

---
## UPDATE 2026-10-01
This first-pass file is superseded in detail by `sota/01–04`. Key shifts: (1) Work Memory and snapshot binding are now clearly "already solved / engineering" (Assay, EA-Graph); (2) claim↔evidence verdicts are commodity; (3) counter-state ideas have precedents (Assurance 2.0 defeaters, SWE-ABS, CFC, classifier counterfactuals) that must be positioned in related work; (4) human-factors evidence is mixed and creates a burden/overreliance trade-off; (5) protocol corrections (ACP). See NOVELTY_BOUNDARY.md for the current boundary.
