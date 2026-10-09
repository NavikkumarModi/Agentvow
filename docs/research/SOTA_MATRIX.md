# SOTA Matrix (G1, first pass)

Status: all entries `[snippet]` (web-search summaries, 2026-09-30). Full reads required before any paper citation. Dates are arXiv IDs / repo as returned by search.

Legend for columns: Claim↔Evidence = checks agent claims against evidence; Snap = binds evidence to a state snapshot; Indep = addresses verification independence; Arch = architecture-aware; Pol = policy-aware; Viz = visualization; HDS = human decision support; Reuse = prior-work reuse; CE = counterexample/counter-state search.

| System | Source | Problem / mechanism | Claim↔Ev | Snap | Indep | Arch | Pol | Viz | HDS | Reuse | CE | Key limit vs Agentvow |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| backcheck (Vector Institute) | github.com/VectorInstitute/backcheck | Checks Claude Code claims vs its own session transcript; zero LLM calls | ✓ | partial | ✗ (evidence is agent's own transcript) | ✗ | ✗ | ✗ | verdict list | ✗ | ✗ | Evidence = agent-produced; no system reality |
| Aga Verify Agent | github.com/agakadela/aga-verify-agent | Codex skill: task vs claims vs diff vs proof for *that commit*; rejects stale tests | ✓ | ✓ | partial | ✗ | ✗ | ✗ | checklist | ✗ | ✗ | Coding-task completion only; LLM skill |
| AgentCheck | github.com/emreordu/agentcheck | Git checkpoint before agent, deterministic diff after; CLI+VS Code | partial | ✓ | ✓ (deterministic) | ✗ | ✗ | diff | ✓ | ✗ | ✗ | Change-verification, no claims/downstream |
| Receipts | github.com/Dhruva-Aher/receipts | Re-runs commands for completion claims pre-merge | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✓ | ✗ | ✗ | Re-runs, no reality graph |
| ClaimReceipt | arXiv 2609.01992 | Evidence sufficiency/coverage for agent eval claims; committed evidence set | ✓ | ? | partial | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | Eval-claims focus |
| EA-Graph | arXiv 2608.04278 | Artifact-anchored verification memory for coding agents under upstream drift | ✓ | ✓ | ? | partial | ✗ | ✗ | ✗ | **✓** | ✗ | **Closest to Work Memory; must read in full** |
| Stale-constraint memory papers (TEPA 2608.07429; 2608.25553; 2609.08258) | arXiv | Staleness/revocation in agent memory | ✗ | partial | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ | Memory layer, not verification |
| archagent (BenedatLLC) | github.com/BenedatLLC/archagent | Architecture md → import-linter/dep-cruiser/ast-grep; deterministic checkers, LLM proposes | ✗ | ✗ | ✓ | ✓ | invariants | ✗ | per-invariant report | ✗ | ✗ | Adherence, not claim reconciliation → **import, don't rebuild** |
| NIST evaluation probes | nist.gov/programs-projects/building-evaluation-probes-agentic-ai | Adversarial-verifier probes in workflow → machine-readable audit trail; factual grounding vs curated corpus | ✓ | ✗ | partial | ✗ | ✗ | ✗ | audit | ✗ | ✗ | Document grounding, not system state |
| Decision Evidence Maturity Model / NovaFabric / Agent Flight Recorder | arXiv 2605.04093 / 2609.12582 / 2609.01931 | Tamper-evident, replayable evidence of agent runs | ✗ | ✓ | ✗ | ✗ | ✗ | ✗ | audit | ✗ | ✗ | Integrity of *record*, not truth of claims |
| Agent-Native Telemetry (ATP) | arXiv 2608.16178 | State-delta evidence ledger: Transitions/Observations/Relations/Checkpoints | ✗ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | Ops telemetry; candidate evidence format |
| AgentGUI | arXiv 2607.26300 | Observe/steer long-running agents; trajectory viz; 38% faster understanding | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | steering | ✗ | ✗ | Activity view, no reality/claims |
| Agent Trajectory Explorer; TraceView; Graphectory; Agent ATO | AAAI / arXiv 2606.22110, 2608.17195, 2609.08301 | Trajectory viz and feedback | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | partial | ✗ | ✗ | Process-centric |
| OpenTelemetry GenAI conventions | opentelemetry.io (status: Development) | invoke_agent / execute_tool spans; MCP conventions | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | Transport; unstable → adapter, not dependency |
| MCP / A2A / ACP | protocol specs | Tool access / agent-agent / editor-agent | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ACP reportedly folded into A2A (verify) |
| OPA/Cedar, AgentCore Policy, Dogwood (AWS), VIGIL, Agent Control Protocol | various | Pre-action authorization / runtime verification of action sequences | ✗ | ✗ | ✓ | ✗ | ✓ | ✗ | ✗ | ✗ | ✗ | Gate actions; don't judge claims |
| Microsoft agent-governance-toolkit | github | Governance/compliance mapping (NIST RFI) | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ | ✗ | ✗ | ✗ | Governance |
| Blast-radius tools (riftmap, Spiderbrain, Port, DataHub-based) | web/commercial | Downstream consumer impact of a change from dependency graph | ✗ | ✓ (commit) | ✓ | ✓ | ✗ | partial | PR report | ✗ | ✗ | **Overlaps "downstream impact" directly**; no claim reconciliation |
| Judge-correlation literature | arXiv 2609.22512, 2605.29800, 2606.29270, 2608.06940 | Correlated LLM errors; effective votes ≪ panel size | — | — | ✓ (motivates) | — | — | — | — | — | — | Supports H7 premise |
| Independence-aware eval (Zenodo 22368667), Maat (2609.34017) | — | Heterogeneous/deterministic contract governance | partial | ✗ | ✓ | ✗ | ✓ | ✗ | ✗ | ✗ | ✗ | Need read |
| Counterfactual explanation in RL (ACTER, COViz, minimal counterfactuals) | arXiv 2402.06503, 2312.11118 | Minimal state change that flips an agent's action | ✗ | ✗ | ✗ | ✗ | ✗ | partial | explain | ✗ | **✓** | RL policies, not SE claim verification; conceptual ancestor of DCRD |
| Automation-bias / approval-fatigue work | arXiv 2502.10036; HF/Data&Society; 2608.12355 | Oversight degrades with volume; agreement with wrong AI is main outcome | — | — | — | — | — | — | ✓ | — | — | Motivates H2/H6; needs own study |
| Agent governance-gap papers | arXiv 2606.31498 | What MCP/A2A/ACP cannot express | — | — | — | — | — | — | — | — | — | Supports integration positioning |

## Not yet searched (G1 gap list)
Property-based / metamorphic agent testing; W3C PROV and in-toto/SLSA attestations (for evidence schema); CodeQL/Semgrep SARIF mapping; LangSmith/Langfuse/Arize/Phoenix observability feature audit; Claude Code hooks/transcript format; SWE-bench-style benchmarks for claim verification; HCI studies on explanation and overreliance (Bansal et al.; Buçinca et al. — prior knowledge, not re-verified).

---
## UPDATE 2026-10-01 — complete SOTA pass

Detailed per-work records (all required fields, source status) are in `sota/01_closest_overlap.md`, `sota/02_patents_commercial.md`, `sota/03_verification_literature.md` (~55 works), `sota/04_human_standards_protocols.md`. This table was superseded where it conflicts.

### Corrections
- EA-Graph: does not claim verifier-vs-agent independence (full text read). Strongly overlaps Work Memory (content-hash anchors, evidence×freshness, refuse on STALE, UNPROVABLE).
- ACP: IBM's Agent Communication Protocol folded into A2A; Zed's Agent Client Protocol is separate and active.

### Added entries (one-line; see sota files for full records)
| System | Date/ID | Why it matters | Status |
|---|---|---|---|
| **Assay** | 2609.36170 (2026-09-28) | Closest overall: Merkle dependency-cone claim binding, blast radius = invalidation frontier, assertion cache, independent reviewer, model-free gate. No counter-state search, no UNKNOWN | read-full |
| EBTE | 2607.25364 | Claims vs independent facts → Allow/Review/Deny (tool calls) | read-page |
| StateProof, agent-claim-verifier, claim-verifier, Praxen, agent-receipts, claimcheck | 2026 OSS | Claim-vs-evidence verdicts; commodity | read-page |
| roam-code | OSS | Code graph, preflight impact, missing-check listing | read-page |
| Looping Is Not Reliability | 2607.24604 | Stale traces harm (34/135 vs 4/135); rejects independence from model diversity | read-page |
| RETRACE | 2608.08950 | Framing-independent patch verification (LLM) | read-page |
| Verification-Time Dependency | 2608.29912 | "Non-independent" labelling; evaluator-input counterfactuals | read-full |
| Assurance 2.0 defeaters | 2409.10665 | Defeaters + residual doubt ≈ UNKNOWN | snippet |
| SWE-ABS | 2603.00520 | Plausible-but-incorrect patch synthesis exposing weak tests | abstract |
| BSG-VA | 2607.28871 | 46% of passing tests non-discriminative | abstract |
| Counterfactual Fragility Certificates | 2609.00366 | Decision-flip under evidence failure (tabular) | abstract |
| BMC-Agent | 2605.21434 | LLM proposes, solver verifies, realism filter | read |
| DiffTestGen | 2607.16024 | Change-directed counterexample tests (collector candidate) | abstract |
| Dogwood (AWS) | 2026-08-06 | Temporal Cedar policies, action gating | read |
| Patents US12450494B1, US20250335185A1, US20230370274A1 | — | Adjacent; see PRIOR_ART.md | read |
| Judge-correlation evidence | 2609.22512, 2605.29800 etc. | ~2 effective votes of 9; ≤0.65 AUROC on false success | snippet/abstract |
