# Competitor Map (updated 2026-10-01)

| Category | Representatives | Overlap | Posture |
|---|---|---|---|
| Claim/transcript verifiers | backcheck, agent-receipts, claimcheck, Receipts, Aga (LLM in verdict path), AgentCheck, **StateProof**, **agent-claim-verifier**, claim-verifier (MCP), Praxen (LLM) | Claim↔evidence verdicts | Baselines B5/B6; reuse as collectors |
| **Evidence-bound claim ledgers** | **Assay** (closest overall), EA-Graph | Snapshot binding, reuse, blast radius, gate | Must-beat baseline; cite, never claim these ideas |
| Claim-vs-fact tool authorization | EBTE (2607.25364) | Claims vs independent facts → Allow/Review/Deny | Cite; different object (tool calls) |
| Evidence/audit | NIST probes, DEMM, NovaFabric, ATP, Flight Recorder, ClaimReceipt | Provenance, sufficiency | Adopt precedents; in-toto/CloudEvents/PROV for format |
| Architecture / impact | archagent, roam-code, import-linter, dependency-cruiser, ast-grep, RTS tools, blast-radius tools | Reality Graph inputs | Integrate |
| AI code review | CodeRabbit, Greptile, Qodo (graph-aware), Bugbot, Copilot review, Claude Code Review | Diff review; impact; LLM judges | Compare against (LLM-reviewer arm); no UNKNOWN/decision-flip documented |
| Policy / runtime | OPA, Cedar, AgentCore Policy, Dogwood (temporal), Microsoft AGT, Snyk/Invariant guardrails, Agent Control Protocol | Action gating | Integrate; trusts history as input |
| Observability / viz | AgentGUI, Agent Trajectory Explorer, TraceView, Graphectory, Langfuse, LangSmith, Phoenix, Braintrust, Helicone, AgentOps, Datadog | Process-centric trajectories | Not a differentiator; no claim-vs-reality view found |
| LLM judges / vendor classifiers | judge panels; Anthropic auto-mode classifier (≈83% catch of overeager behavior per vendor post) | H7 baseline | Evaluate against |
| Adjacent research | Assurance 2.0 defeaters, SWE-ABS, BSG-VA, CFC | Counter-state ideas | Position explicitly in related work |

Not audited: Honeycomb, Grafana AI, Graphite (docs 404), Lakera, Devin/OpenHands review internals; Sourcegraph, Codescene, Semgrep, Snyk at snippet level.
