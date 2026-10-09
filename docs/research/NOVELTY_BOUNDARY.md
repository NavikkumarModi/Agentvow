# Novelty Boundary (G2) — revised after complete SOTA pass, 2026-10-01

**Gate status: NOT PASSED.** Blockers: (1) no queryable patent search (see PRIOR_ART.md §Patents); (2) most sources are page/abstract-level reads, not paper-grade (see source status in `sota/*.md`); (3) adversarial review not yet run; (4) safety-assurance / N-version-diversity / regression-test-selection / counter-abduction literature unsearched.

Detail lives in `sota/01_closest_overlap.md`, `02_patents_commercial.md`, `03_verification_literature.md`, `04_human_standards_protocols.md`.

## Rejected claims (do not make)
First: agent verifier; evidence verifier; claim-vs-transcript checker; architecture-aware agent; agent visualization; adversarial agent/verifier (NIST probes); human approval system; snapshot-bound verifier (Aga, AgentCheck, Receipts); verification memory / evidence cache (EA-Graph, Assay); claims bound to dependency-cone hashes (Assay); blast radius as the invalidation frontier (Assay); unprovable/unknown terminal state (EA-Graph; Assurance 2.0 "residual doubt"); separation-of-duties reviewer + mechanical merge gate (Assay); claims-vs-independent-facts routing to Allow/Review/Deny (EBTE); policy engine or runtime verification; tamper-evident agent records.

## ALREADY SOLVED (cite, don't claim)
- Claim extraction and claim-vs-record verdicts with no LLM in verdict path: backcheck, agent-receipts, claimcheck, Receipts, agent-claim-verifier, StateProof (verdict classes VERIFIED/STALE/UNVERIFIED/CONTRADICTED/uncheckable/NEEDS_REVIEW are commodity)
- Commit/hash staleness; refuse-on-stale; LLM quarantine from "proven": Aga, Receipts, EA-Graph, Assay, Looping-Is-Not-Reliability
- Cone/Merkle binding, cross-agent assertion cache, risk-proportional obligations, mechanical gate: Assay
- Architecture invariants (archagent); impact/preflight and missing-check listing (roam-code, Greptile/Qodo graph-aware review, RTS)
- Pre-action policy and temporal policy (OPA, Cedar, AgentCore, Dogwood, Microsoft AGT); tamper-evident records (NovaFabric, ATP, Flight Recorder)
- "Don't infer independence from model diversity": Looping-Is-Not-Reliability, judge-correlation papers (strong empirical premise)
- Decision-flip search *shape* on classifiers (counterfactual/abductive explanations; Counterfactual Fragility Certificates on tabular data)
- Counterexample feasibility/realism filtering (CEGAR, BMC-Agent); plausible-incorrect-patch synthesis against weak tests (SWE-ABS); evidence discriminativeness (BSG-VA)
- Defeaters with residual doubt (Assurance 2.0)
- Process-centric trajectory visualization

## COMBINATION / ENGINEERING
- Unified evidence schema carried by in-toto Statement + custom predicate, CloudEvents transport, PROV export, SARIF input (no new standard needed)
- Typed Reality Graph richer than module cones (interfaces, consumers, tests, invariants, policies, runtime config), built from existing collectors
- Cross-agent reuse over heterogeneous agents (Assay's cache is the baseline)
- Claim → verification-obligation decomposition; plain-language decision objects; approval scope semantics (US12688261 is adjacent); source-agnostic ingestion (Claude Code hooks, OTel adapter, Zed ACP, MCP, A2A)
- Independence as a typed vector (framing/evidence/mechanism/authority) capping SUPPORTED: weak precedents only (Assay role separation, 2608.29912 "non-independent" labelling, ClaimReceipt binding). Design contribution until an ablation shows it changes outcomes.

## POTENTIALLY NOVEL — "Potential gap requiring further verification"
1. **Decision-gated UNKNOWN via counter-state search**: for claim C and action A, enumerate counter-states from a typed graph that snapshot-valid independent evidence cannot exclude and that flip an explicit approval rule; report UNKNOWN with the surviving flipping states; suppress findings that cannot flip the rule. No work read does this. Nearest: Assurance 2.0 defeaters (manual), SWE-ABS (benchmark hardening), CFC (tabular), EA-Graph UNPROVABLE (per-claim), Assay gate (affected set, no counter-states).
2. **Decision-impact suppression as an anti-fatigue mechanism** (report only unknowns that can change approve/reject). Partial neighbours: pivotal-vote analysis, Planfence frontier. Needs a human study to count as a result.
3. **Claim-vs-reality juxtaposition built for a human decision**, evaluated against agent-summary, transcript and LLM-reviewer arms with seeded divergences and Agentvow-error trials. Absence of such a study is from a limited search.

## Honest assessment
Novelty risk: MEDIUM-HIGH for the system, MEDIUM for items 1–2 pending a real patent search. **For the first claim class ("no downstream impact"), the mechanism reduces to Assay/roam-code/RTS impact analysis plus a threshold rule.** The contribution survives only if (a) a claim class is chosen where enumeration is non-trivial (e.g. "tests cover this change", runtime/config/stale-evidence divergences, where evidence-exclusion matters), and/or (b) the benchmark and human study show decision-gated UNKNOWN beats an Assay-style gate and an LLM reviewer on harmful approvals, UNKNOWN recognition and review time. Required baselines added: Assay-style cone gate, RTS/impact analysis, StateProof/agent-claim-verifier, SWE-ABS-style adversarial alternatives, LLM-reviewer (Anthropic auto-mode-style classifier).

## Smallest mechanism worth implementing (revised)
Keep the claim-reality reconciler and evidence store as thin engineering. Spend research effort on the counter-state enumerator + decision rule + UNKNOWN reporting, on two claim classes: (i) "no downstream impact", (ii) "tests cover this change / verified". Pre-register that class (i) is expected to match Assay; class (ii) is where discriminative-evidence reasoning (BSG-VA, SWE-ABS ideas) should separate the methods. LLM only proposes counter-state candidates; evidence checks decide.

## Next gates
1. Run the manual patent queries (`sota/02_patents_commercial.md` §A.2), ideally with a practitioner.
2. Full-text reads: ClaimReceipt, Assay (+repo), Assurance 2.0 defeaters, SWE-ABS, CFC, "Can Agent Benchmarks Support Their Scores?", Zenodo 22368667.
3. Search: safety-assurance, N-version diversity / common-cause failure, regression test selection (Ekstazi-style), counter-abduction.
4. Run the adversarial review (master plan §30) and write RISKS.md.

## Adversarial review (2026-10-01)
Gate remains NOT PASSED. Full findings in `RISKS.md`. Boundary changes:
- Move to ALREADY SOLVED / reframe: "enumerate defeaters, eliminate with evidence, report residual doubt" (eliminative argumentation, Assurance 2.0), including LLM-proposed defeaters (CoDefeater, arXiv 2407.13717). Item 1 under POTENTIALLY NOVEL is reduced to: "decision-flip-filtered, rule-conditional, scope-labelled UNKNOWN for coding-agent claims, with measured effect on human approval". No mechanism-novelty claim.
- Claim class (ii) "tests cover this change" is not safe ground either: surviving mutants / RTS give the same signal (RISKS A2). Add mutation testing and RTS to required baselines, plus a rule-aware LLM reviewer with the same collectors.
- Independence vector: stays "design contribution"; cite Knight and Leveson and common-cause-failure literature; may not cap SUPPORTED on separate labels alone (RISKS A4).
- Add to rejected claims: "independent reality model" (the graph is built from agent-modified code and agent-influenced evidence; RISKS D1) and "cannot be excluded" without a stated bounded state space (RISKS E1).
- Surviving claim candidates: item 2 (suppression) and item 3 (claim-vs-reality view for humans), both contingent on a human study with tool-error trials; item 1 contingent on pilot P0 passing (RISKS K).
- Remaining blockers: patent search; full reads of Assurance 2.0 defeater papers, CoDefeater, SWE-ABS; abstract-interpretation / may-analysis and SLSA/in-toto prior art not yet reviewed in depth.

## Update 2026-10-09 (pass 2; details in NOVELTY_GATE_2026-10-09.md)
Gate remains **NOT PASSED** (patent search still not done). New rejected claims: "agent claim checker with a block-once Stop-hook feedback loop" (orthogon agent-verify), "rule-engine verdicts with commit-and-dirty-hash staleness" (truth-mcp, ProofRun), "baseline-aware differential test gate" (Phoenix), "run the tests to check a 'tests pass' claim" (agent-verify). Honest assessment: **system novelty is low**; what remains are empirical questions (effect on human approval; execution-based detection on real agent PRs; generalisation of the new-test-failure policy), each marked "Potential gap requiring further verification".
