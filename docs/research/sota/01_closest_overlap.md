# 01 Closest-overlap deep reads and hostile overlap assessment

Date of research: 2026-10-01. Author: sota-researcher.

## Source-status key (stricter than the repo's two-label scheme)
- **[read-full]**: complete PDF text extracted locally (pdftotext) and read by me. Applies to EA-Graph, ClaimReceipt, Assay (partly: sections searched and summary read, not every line), and Verification-Time Dependency (2608.29912, intro, constructs, and Counterfactual Auditability section skimmed).
- **[read-page]**: the arXiv abstract page, HTML page, or GitHub README/tree was fetched with WebFetch. WebFetch passes pages through a summarising model, so this is NOT verbatim full text. Details below come from that summary. Treat as a README/abstract-level read; do not cite as a full-text read in a paper without re-checking the PDF.
- **[snippet]**: search-result summary only.
- **[unavailable]**: could not be fetched.
Fields I could not establish are written "not stated in source read" rather than guessed.

## Headline findings (read first)
1. **Assay (arXiv 2609.36170, 2026-09-28) is the closest single work found and was NOT on the prior target list.** It binds agent claims to the Merkle hash of the dependency cone of covered code, defines staleness as hash mismatch, equates blast radius with the invalidation frontier, reuses claims across agents as a "build cache for assertions", separates doer from independent reviewer, and gates merges mechanically with no model in the path. It overlaps Agentvow's evidence-reuse, snapshot-binding, downstream-impact, deterministic-verdict and independence-of-reviewer elements. It has no counter-reality search and no UNKNOWN/unprovable verdict.
2. **EA-Graph (2608.04278) overlaps the Work Memory / evidence-reuse element strongly** (sub-path artifact identity, content-hash anchors, evidence x freshness lattices, refusal on STALE, terminal UNPROVABLE state, LLM quarantine). It has no cross-agent independence mechanism, no claim extraction from agents, no policy/architecture layer, no UI, no counter-reality search.
3. **backcheck, agent-receipts, claimcheck, Receipts, Aga, AgentCheck** collectively already cover claim-vs-evidence verdicts with STALE/UNVERIFIED/CONTRADICTED/uncheckable classes at the transcript/diff/test level. The "claim-reality reconciliation" element in its simplest form is solved many times.
4. **Decision-sensitive counter-reality search: none of the works read does it.** Nearest conceptual neighbours are (a) ClaimReceipt's claim-sufficiency definition (evidence E is sufficient iff no two executions with equal retained evidence differ in claim truth), which is a definitional/identifiability notion with no search and no decision rule, (b) EA-Graph's UNPROVABLE terminal state (a changed dependency whose content is unavailable), which is a one-hop special case of "unexcludable alternative state" with no decision-flip filter, (c) the Counterfactual Auditability construct in 2608.29912, which perturbs an *evaluator's inputs* to ask whether its decision would change (a statistical test of a model's behaviour, not a search over states of the world), and (d) Assay's blast radius/obligation levels, which are a deterministic risk-proportional gate, not counter-state enumeration. Verdict: **the mechanism remains a potential gap requiring further verification**; see per-work sections and the verdict section.

---

## Per-work records

### 1. EA-Graph
- **Name**: EA-Graph: Artifact-Anchored Verification Memory for Coding Agents under Upstream Drift
- **Date**: 2026-08-04 (v1). Authors Hsu, Chi, Everett (NYCU).
- **URL**: https://arxiv.org/abs/2608.04278
- **Problem**: After upstream drift, previously verified claims may be silently false though the project builds; prose notes do not preserve what a claim was checked against.
- **Mechanism**: State M=(G,C,ANCH,META,DISP). Graph G has code nodes (function-level), artifact nodes with identity (store,path,subpath), and effect edges read/write/kill. Alias chains are resolved to the leaf definition. Each claim is anchored to a content hash of the exact span used. META is an independent pair (evidence in UNKNOWN<PARTIAL<PROVEN, freshness FRESH|STALE). Rules: query answers carry the meet of evidence along the derivation path; STALE anything => query refused with rebuild obligation; LLM-proposed edges enter at PARTIAL, never PROVEN. Withdrawal query returns unaffected / affected / unprovable.
- **Input**: prior verification claims, per-claim anchor sets, new upstream content.
- **Output**: per-claim unaffected / affected / unprovable; disposition RETAIN or WITHDRAW kept separate from claim status.
- **Evidence source**: deterministic extraction and content hashes; claims recorded by agent sessions (in the evaluation the claims come from the agent's own session records).
- **Independence mechanism**: independence is between evidence and freshness lattices, and between two derivations (source-extracted OPS vs. consulted anchors) to check anchor completeness. No independence between verifier and the claiming agent is engineered beyond "LLM quarantine". The earlier fetch summary that claimed "independence between the verification process and the agent's policy" is not supported by the full text; discard it.
- **Architecture awareness**: effect graph of code to persistent artifacts (function-level code granularity). Not architectural invariants.
- **Policy awareness**: none.
- **State awareness**: strong. Content-hash anchors at sub-path granularity; staleness is a hash comparison.
- **Visualization**: none in the paper (a figure of the model only).
- **Human decision support**: none; consumer is the next agent. The paper stresses refusal rather than human-facing explanation.
- **Prior-work reuse**: yes, this is the core. Claims persist across sessions and are withdrawn only if anchors change. Reduced implementation evaluates only the withdrawal query Q1 (Q2 dependence and Q3 impact are defined but not evaluated; write/kill edges not populated; PARTIAL/UNKNOWN grades and multi-hop meet not exercised).
- **Counterexample support**: none. UNPROVABLE (changed dependency, replacement content withheld) is the nearest relative: it says "no evidence in reach can settle this claim". There is no enumeration of alternative states and no decision rule.
- **Limitations (as stated)**: synthetic generated repos, 42 sessions, 7 worlds; Sonnet ceiling effects left preregistered contrasts non-significant; no efficiency or repair-quality claim; efficiency not tested (eager hashing); only reduced implementation.
- **Overlap with Agentvow**: HIGH for snapshot-bound evidence reuse and for the evidence-vs-freshness separation; HIGH for "UNKNOWN is a first-class terminal result"; MEDIUM for downstream-impact queries (Q3).
- **Possible differentiation**: Agentvow reconciles claims made by *any* agent against an independent graph (EA-Graph stores the claims of the sessions themselves); Agentvow adds independence vectors, policy/architecture rules, human-facing decisions, counter-reality search with a decision-flip filter. Must cite EA-Graph for the unprovable state and evidence/freshness separation and not claim these.
- **SOURCE STATUS**: [read-full] (pdftotext of the arXiv PDF; sections 1 to ~4.4 read in detail, rest skimmed through earlier fetch summary).

### 2. ClaimReceipt
- **Name**: ClaimReceipt: Verifying Evidence Sufficiency and Coverage in Agent Evaluations
- **Date**: 2026-09-02. Authors Zhu, Chang (Blossom AI).
- **URL**: https://arxiv.org/abs/2609.01992
- **Problem**: Whether an agent-evaluation claim is recomputable from retained evidence (sufficiency) and whether the retained records cover the committed experiment set (coverage).
- **Mechanism**: A claim-relative receipt spec frozen before implementation (hash-pinned); typed transaction evidence, signed experiment manifest, assignment matrix and ingress commitment; a selective verifier recomputes claims and returns PASS / INVALID / INCONCLUSIVE (INCONCLUSIVE_COVERAGE when a terminal receipt is withheld). Four layers: transport integrity, semantic evidence, coverage, external truth (explicitly out of scope).
- **Input**: buyer-seller agent transaction records (1,392 historical, 30 prospective), manifests.
- **Output**: per-contract verdict; may license descriptive reporting while blocking causal policy claims.
- **Evidence source**: platform-retained typed records; external truth explicitly not provable by the platform.
- **Independence mechanism**: role-separated keys, encrypted openings for an auditor; the paper itself says its host does not independently hold roles and that independent ingress witnessing is future work.
- **Architecture/policy/state awareness**: no architecture; "policy" only as coverage policy in the manifest; state = committed manifest hash, not code snapshot.
- **Visualization / human decision support**: none (verdict tables).
- **Prior-work reuse**: none beyond deterministic replay of retained records.
- **Counterexample support**: no search. It does contain a formal sufficiency definition: E is claim-sufficient iff for all executions tau1,tau2, retained evidence equal implies claim truth equal. This is the identifiability condition under which a counter-reality (two worlds with the same evidence, different claim truth) cannot exist. This is the closest *formal* relative of Agentvow's "cannot be excluded by available evidence" predicate, but it is used to design schemas, not to search per decision.
- **Limitations**: single domain (buyer-seller sims); own frozen spec "not yet unambiguous to an independent reader"; no second domain or independent implementation.
- **Overlap with Agentvow**: LOW for coding agents; MEDIUM on INCONCLUSIVE as first-class verdict and the sufficiency definition.
- **Possible differentiation**: Agentvow applies the same identifiability idea at oversight time to enumerate the specific unexcluded states relevant to a pending approval. Cite ClaimReceipt for the sufficiency definition and "universe/coverage" framing.
- **SOURCE STATUS**: [read-full] (PDF text; abstract, intro, problem formulation, design, limitations read; mid-section tables skimmed via grep).

### 3. backcheck (Vector Institute)
- **Name**: backcheck. **Date**: repo is 2026 (no explicit release date in page). **URL**: https://github.com/VectorInstitute/backcheck
- **Problem**: Coding agents claim tests ran/committed/passed without support.
- **Mechanism**: Rust CLI reads Claude Code session JSONL transcripts; deterministic per-tool parsers (pytest, git, linters, edits) produce a record of what ran; claims in the agent prose are pattern-matched and compared. Zero LLM calls. Separate test-integrity flags (skip markers, weakened assertions). Source files seen: claims.rs, evidence.rs, hook.rs, report.rs, session.rs, tamper.rs, transcript.rs, verify.rs, runners/.
- **Input**: transcripts at ~/.claude/projects/. **Output**: supported / inconclusive / contradicted / unsupported / qualified, plus integrity flags.
- **Evidence source**: the agent's own tool-call records in its transcript. **Independence**: "the agent's account cannot influence the record of it", i.e. prose vs. record separation, but both are the same session's artefacts (the record is produced by the harness, not by the model's prose).
- **Architecture/policy awareness**: none. **State awareness**: partial (stale-green detection via transcript order, per README; not hash-bound). **Visualization**: none. **Human decision support**: verdict list. **Prior-work reuse**: none (cross-session references read as unsupported). **Counterexample**: none.
- **Limitations**: regex claim detection; Claude Code only; no system reality beyond transcript.
- **Overlap**: HIGH for the simplest claim-reconciliation (tests ran, commit happened) and no-LLM-verdict discipline. **Differentiation**: Agentvow's evidence is independent of the agent's session where possible and covers claims the transcript cannot (downstream impact, architecture). Reuse backcheck as an importer/collector rather than rebuild.
- **SOURCE STATUS**: [read-page] (README + src listing).

### 4. Aga Verify Agent
- **Date**: no dates on page (13 commits). **URL**: https://github.com/agakadela/aga-verify-agent
- **Problem**: Verify that an agent actually completed the task. **Mechanism**: Codex skill (SKILL.md, agents/, references/) running pipeline task -> claims -> changed code -> proof -> next action; proof must match the exact commit; stale proof rejected. LLM-executed skill, not a deterministic program.
- **Input**: task text, agent final answer, base+candidate commits, CI/test output. **Output**: VERIFIED / PARTIALLY_VERIFIED / NOT_VERIFIED / MISALIGNED / UNSAFE_TO_MERGE + next action.
- **Evidence source**: raw test/CI output and diffs; agent prose counts as claims only. **Independence**: prose-vs-proof separation only. **Architecture/policy**: none stated; high-risk areas (auth, payments, migrations) explicitly out of scope. **State**: yes, commit-bound. **Visualization**: none. **Human decision support**: verdict + next action. **Reuse / counterexample**: none.
- **Limitations**: not code review, no runtime testing, no high-risk changes.
- **Overlap**: HIGH for commit-bound proof; MEDIUM for task-scope (MISALIGNED). **Differentiation**: LLM in the verdict path (violates Agentvow rule); no reality graph.
- **SOURCE STATUS**: [read-page].

### 5. AgentCheck
- **Date**: v0.1.3 shown; no date. **URL**: https://github.com/emreordu/agentcheck
- **Problem**: Review of agent changes before commit. **Mechanism**: Git-backed checkpoint before the agent runs; deterministic diff after; heuristic findings (deps, migrations, config, secrets, test correlation by naming) and transparent risk score; CLI, @agentcheck/core, VS Code extension.
- **Input**: repo state at checkpoint (including .env). **Output**: report/JSON, findings with evidence, verdict e.g. "LOOKS ROUTINE".
- **Evidence**: local git analysis. **Independence**: fully deterministic, no agent claims consumed. **Architecture/policy**: none. **State**: yes (checkpoint vs now). **Visualization**: diff report in VS Code. **Human decision support**: yes (risk verdict). **Reuse/counterexample**: none. **Claims**: not consumed.
- **Limitations**: naming-based test analysis, no semantic or coverage, secrets heuristic.
- **Overlap**: MEDIUM (snapshot-bound deterministic evidence + human verdict). **Differentiation**: no claims, no downstream reasoning. Candidate evidence provider.
- **SOURCE STATUS**: [read-page].

### 6. Receipts (Dhruva-Aher)
- **Date**: perf measured 2026-09-30, historical Codex run 2026-07-17. **URL**: https://github.com/Dhruva-Aher/receipts
- **Problem**: Agent summaries may not match repo changes. **Mechanism**: extract completion claims from transcripts, re-run claimed commands in a local sandbox, inspect diff for weakened tests and sensitive paths; MERGE / FIX / ESCALATE.
- **Evidence**: independent re-execution (strong independence of mechanism) and git diff. **State**: before/after repo. **Visualization**: Vite UI with frozen replay demos. **Human decision support**: yes, claim-vs-evidence receipts. **Reuse**: local history file only. **Counterexample**: none. **Architecture/policy**: sensitive-path list only.
- **Limitations**: only extractable, safely re-runnable claims; three frozen fixtures; real-world applicability unproven.
- **Overlap**: HIGH for claim -> independent re-run -> verdict -> human decision. **Differentiation**: no persistent reality model, no impact/UNKNOWN reasoning.
- **SOURCE STATUS**: [read-page].

### 7. archagent (BenedatLLC)
- **Date**: none stated (241 commits). **URL**: https://github.com/BenedatLLC/archagent
- **Problem**: Prose architecture invariants drift from code. **Mechanism**: markdown invariants table compiled to import-linter / dependency-cruiser / ast-grep / Hypothesis / fast-check configs; checkers run; results mapped to invariant IDs; LLM only proposes. Commands check, drift, evaluate.
- **Evidence**: static analysis, git history, config scans. **Independence**: deterministic checkers. **Architecture**: yes, that is its purpose. **Policy**: invariants as policy (not authorization). **State**: working tree, not snapshot-bound evidence records. **Visualization**: reports. **Human decision support**: per-invariant report. **Reuse / counterexample**: none (property-based test stubs are *inside* checkers, not counter-reality of agent claims). **Claims**: not consumed.
- **Overlap**: MEDIUM-HIGH for architecture-awareness; **Differentiation**: adherence checking, no claim reconciliation. Import its checks as collectors.
- **SOURCE STATUS**: [read-page].

### 8. NIST evaluation probes
- **Date**: project started April 2026, ongoing. **URL**: https://www.nist.gov/programs-projects/building-evaluation-probes-agentic-ai
- **Problem/mechanism**: probes embedded in agentic workflows act as adversarial verifiers of cited reports against curated document corpora; faithfulness, completeness, sufficiency of each citation; structured audit trail with rationales.
- **Input**: research questions + authoritative corpora. **Output**: cited reports, per-citation evaluation, audit trail.
- **Independence**: each probe independent via defined rubrics (LLM-based status not stated on the page). **Architecture/policy/state/viz/reuse/counterexample**: none stated. **HDS**: audit trail.
- **Limitations (stated)**: narrow factual grounding.
- **Overlap**: LOW for coding agents; the "adversarial verifier" label overlaps the *word* only (it adversarially checks citations, not counter-states). **Differentiation**: system-state rather than document grounding.
- **SOURCE STATUS**: [read-page].

### 9. Decision Evidence Maturity Model (DEMM) and DEMM-Bench
- **Date**: 2605.04093 submitted 2026-04-29; DEMM-Bench 2606.20634 on 2026-05-30. Author Solozobov. **URL**: https://arxiv.org/abs/2605.04093 , https://arxiv.org/abs/2606.20634
- **Problem**: Whether available telemetry can answer property-level audit questions about a specific agent decision (the "container fallacy").
- **Mechanism**: property-level reconstructability: evidence classed as sufficient/insufficient/etc. (four classes plus "conflicting"), five-tier rubric, Decision Trace Reconstructor with adapter fallbacks; DEMM-Bench: 64 cases, eight regimes, eight degradation conditions, eight queried properties (actor, authority, action, policy, decision basis, resource touch, lifecycle, verification strength).
- **Input**: telemetry/JSONL/protocol traces. **Output**: sufficiency verdict per property; completeness 53.6% to 100% on synthetic and three real incidents.
- **Independence/architecture/viz**: none stated. **Policy awareness**: policy is one of the queried properties. **State**: reconstructability of policy bundle/budget/lifecycle/cache state. **HDS**: audit. **Reuse**: none. **Counterexample**: snippet from search said a counterfactual-replay probe asks "if policy bundle, budget, lifecycle or cache state changed, would the evidence re-derive the decision or name the blocking property" (that is from the benchmark/related Zenodo works per search summary: [snippet]); it audits *recorded decisions after the fact*, not oversight of pending approvals, and is about governance evidence sufficiency.
- **Limitations**: completeness reflects implementation behaviour, not external validation.
- **Overlap**: LOW-MEDIUM (evidence sufficiency reasoning); **Differentiation**: governance audit of the record vs. truth of agent claims about a codebase.
- **SOURCE STATUS**: 2605.04093 [read-page]; 2606.20634 [read-page]; counterfactual-replay probe detail [snippet].

### 10. Agent-Native Telemetry (ATP)
- **Date**: 2026-08-17. Authors He, Yu. **URL**: https://arxiv.org/abs/2608.16178
- **Problem**: Text logs are costly and unverifiable for agent consumption. **Mechanism**: Agent Telemetry Protocol and State-Delta Evidence Ledger: Transitions, Observations, Relations, State Checkpoints; content-addressed schemas; producer signatures; hash-chained batches. **Results**: 96.4% payload reduction vs OTel JSON, 88.8% fewer context tokens, all 500 adversarial mutations detected.
- **Evidence**: operational state deltas (AIOpsLab, OTel Astronomy Shop). **Independence**: integrity only. **Architecture/policy/viz/HDS/reuse/counterexample**: none. **State**: yes (checkpoints).
- **Overlap**: LOW; a candidate evidence-record format. **SOURCE STATUS**: [read-page].

### 11. NovaFabric
- **Date**: 2026-09-11. Author Seyedkazemi Ardebili. **URL**: https://arxiv.org/abs/2609.12582
- **Problem/mechanism**: Run Capsule (15-entity schema), DSSE signatures, RFC 3161 timestamps, Merkle log, redaction attestation, four-mode replay; reuses OTel, in-toto, W3C PROV.
- **Limitations (stated)**: mocked replay succeeded for model responses (10/10) but 2/10 for tool-using workflows; stream completeness 0.652; 61.6 req/s cap; six defects (four fixed).
- **Overlap**: LOW; integrity of record, not truth of claims. **Differentiation/Use**: evidence-schema and standards precedent (in-toto/PROV). **SOURCE STATUS**: [read-page].

### 12. Maat
- **Date**: 2026-09-27. Author Uliana Elina. **URL**: https://arxiv.org/abs/2609.34017
- **Problem/mechanism**: deterministic validation of agent-to-agent handoffs against a versioned workflow contract ("anchor"), no LLM in validation or scoring.
- **Output**: verdicts, halt/continue, cost. **Result**: +7.7% to +29.1% when attributed to verified defects, 17-53% model-call cost cut, but 37% of alarms in hand review were validator defects (the author reports post-publication audit lowering initial 2.9-26.5% gains).
- **Independence**: no LLM in path (mechanism-independent). **Policy**: contract = policy. **Others**: no architecture, viz, HDS, reuse, counterexample.
- **Overlap**: LOW-MEDIUM (deterministic contract gate between agents). **Differentiation**: handoff contracts vs. reality graph. Its 37% validator-false-alarm finding is a useful warning for Agentvow's own checkers.
- **SOURCE STATUS**: [read-page].

### 13. Beyond LLM-as-a-Judge (Zenodo 22368667)
- **Date**: 2026-09-05 v1. Author Sourav Kumar. **URL**: https://zenodo.org/records/22368667 (DOI 10.5281/zenodo.22368667; code github.com/itzsouravkumar/beyond-llm-as-a-judge, not read).
- **Problem**: LLM-judge panels have correlated errors (a nine-judge panel ~2.2 independent votes, as quoted by the record).
- **Mechanism**: Evaluator Conflict Score weighting disagreement across heterogeneous verifiers (semantic LLM, deterministic symbolic, programmatic, retrieval); conflict-gated cascade escalating verification.
- **Independence mechanism**: heterogeneity of paradigms plus conflict gating (scalar score, not a vector).
- **Others**: no architecture/policy/state/viz/reuse/counterexample.
- **Overlap**: LOW-MEDIUM; supports the independence premise. **Differentiation**: Agentvow's independence is a typed vector over framing/evidence/mechanism/authority and *caps* SUPPORTED, versus a scalar disagreement trigger. **Note**: the record is a single-author preprint; repo not inspected.
- **SOURCE STATUS**: [read-page] (Zenodo record page); code [unavailable/not read].

### 14. When Stale Constraints Go Unchecked
- **Date**: 2026-08-26, final 2026-08-28. Author Nakayashiki. **URL**: https://arxiv.org/abs/2608.25553
- **Problem/mechanism**: with a limited verification budget, 16 LLMs rarely re-verify settled-seeming constraints (stale-consistent decisions in about 75-77% of episodes); allocating budget to critical paths recovered +61 to +81 points.
- **Overlap**: LOW; but it is empirical support for "reuse must be gated by snapshot validity, and re-verification should be targeted". Not a verifier. Authors note it is "not a scheduler".
- **SOURCE STATUS**: [read-page].

### 15. TEPA
- **Date**: 2026-08-07 (rev 08-10). **URL**: https://arxiv.org/abs/2608.07429
- **Problem/mechanism**: keyed precedents revoked when newer contradictory evidence arrives under the same key; audit trail retained; 0.950 vs 0.210 under full reversal. Memory-layer revocation, no verification of claims.
- **Overlap**: LOW (staleness semantics only). **SOURCE STATUS**: [read-page].

---

## Additional works found that are closer than (or as close as) the target list

### A. Assay (closest overall)
- **Name**: Assay: Claims That Decay With the Code. Content-Addressed Evidence Graphs for Accountable AI-Assisted Software Delivery.
- **Date**: 2026-09-28. Authors Tiwari, Vass, Singh. **URL**: https://arxiv.org/abs/2609.36170 (Python tool with MCP server; repo link on the paper).
- **Problem**: Coding agents lose context and make unverified claims; context tools (repo maps) and governance (review) are disconnected.
- **Mechanism**: Claim = (predicate, subject modules, scope, bindings, evidence, attestor, timestamp). Bound to the Merkle hash of the dependency cone over a condensation DAG of modules. Stale iff the cone hash changed (derived from the index, not stored); a stale claim cannot be accepted without re-attestation. Failed claims are recorded as evidence. Roles: doers produce claims, reviewers independently accept/counter/refute/escalate (up to three rounds), humans resolve escalations. Risk-proportional obligation levels 0-3 from radius fraction, radius size, max risk (churn + fan-in). Merge gate with eight mechanical checks (coverage, freshness, HMAC signatures, exit codes, plausibility of test command, evidence monotonicity such as test count not dropping, reviewer independence, escalation resolution), no model consulted.
- **Input**: repo parse (regex or tree-sitter; Python/JS/TS/Go/Rust/Java/Kotlin/Ruby/C), attested claims, evidence (exit codes, counts, command output).
- **Output**: 600-token context briefs; gate PASS/BLOCK; obligation level; stale-claim list; append-only signed ledger under .assay/.
- **Evidence source**: attested command evidence plus index; claims by agents are claims only.
- **Independence mechanism**: separation of duties enforced at append time (no self-review; reviewer distinct from doer). Signing key outside agent reach (described, not enforced). This is *role* independence, not a typed independence vector, and nothing prevents the reviewer being another LLM from the same family.
- **Architecture awareness**: module dependency graph, fan-in, churn. No invariants.
- **Policy awareness**: repository-overridable obligation thresholds and review-round limits.
- **State awareness**: strong, Merkle cone binding; evaluated: cone binding is sound and minimal; self-hash misses 23-68% of required invalidations; re-verifies 7.9-81.9% vs 100% for repo-hash.
- **Visualization**: none described (briefs and CLI).
- **Human decision support**: briefs, obligation justification, human sign-off on escalations; not plain-language decision objects.
- **Prior-work reuse**: yes: "ledger as a build cache for assertions"; same predicate and subject reusable across agents if fresh.
- **Counterexample support**: none. The paper explicitly states it does not explore what-if scenarios; gate validates a single proposed change against current and historical evidence. Future work: "what tests would need to pass".
- **Limitations (stated)**: regex parser under-approximates dynamic imports; directory-level modules coarse; gate checks plausibility not sufficiency; key security not enforced; no model-in-loop evaluation (SWE-bench trial future work).
- **Overlap with Agentvow**: VERY HIGH on snapshot-bound evidence reuse, dependency-based blast radius = invalidation frontier, deterministic verdict path, reviewer independence, risk-proportional human escalation. LOW on counter-reality, UNKNOWN semantics, independence vectors, plain-language UI.
- **Possible differentiation**: Agentvow's Reality Graph is agent-independent and typed beyond module dependencies; it adds UNKNOWN with survivor enumeration and the decision-flip filter; independence as a vector with SUPPORTED cap; claims from heterogeneous agents. Agentvow must not claim "claims bound to dependency-cone hashes", "blast radius = invalidation frontier" or "evidence ledger as build cache" as novel.
- **SOURCE STATUS**: [read-full] (PDF text extracted and keyword-searched; main sections read via full fetch summary and raw text grep; I did not read every paragraph).

### B. Verification-Time Dependency on a Disappearing Evaluator (Counterfactual Auditability)
- **Date**: 2026-08-28 (v8.3). Authors Ku, Siddiqui. **URL**: https://arxiv.org/pdf/2608.29912
- **Problem**: A model-mediated decision may be unreproducible later because the evaluator is retired. **Mechanism**: Decision-State Commitment, Independent Verifiability (verifier separately trusted from decision producer; otherwise labelled non-independent), and Counterfactual Auditability: under a specified perturbation, would the evaluator's output have changed, requiring executable evaluator or contemporaneously preserved counterfactual evidence; stability-calibrated tests; Verification-Time Preservation Package. Empirical: 52% and 30% modal-decision reversal between model versions.
- **Counterexample support**: perturbs *inputs to a model evaluator* and measures decision reversal. It is not a search over world states constrained by independent evidence, and not about coding agents. **Independence**: explicit rule that common-control verification must be labelled non-independent (useful design precedent).
- **Overlap**: LOW-MEDIUM (vocabulary and independence labelling). **SOURCE STATUS**: [read-full] (PDF text extracted; abstract, intro, section 4 partially read).

### C. Others found (all [read-page] unless noted)
- **Looping Is Not Reliability** (2607.24604, Alibaba, v2 Sept 2026): state-bound evidence for code repair; stale traces harm 34/135 correct starts vs 4/135 with current traces; rejects inferring verifier independence from model-family diversity (phi = 0.641 within Qwen family). Empirical support for snapshot binding and for Agentvow's independence premise. No claim reconciliation, no counter-state search.
- **Explanation-Bound Tool Execution (EBTE)** (2607.25364, 2026-07-28): converts agent explanations to structured action claims verified against independently held server facts (intent certificates, tool registry, policy, risk snapshot) -> Allow / Review / Deny. Same *shape* as claim-vs-independent-reality plus policy awareness, but for tool-call authorization, not codebase claims; no graph, reuse, or counter-state search. Overlap MEDIUM on "claims vs independent facts, Review route".
- **RETRACE** (2608.08950, 2026-08-09): independent patch verification by backward reconstruction of the problem from the patch alone and reconciliation; LLM-based, same backbone for both paths. Independence of *framing* mechanism only (withholds the issue). Relevant as a framing-independence precedent; LLM in verdict path.
- **Evidence-Ledger Adjudication** (2607.26512): claim/evidence relations (supports/contradicts/missing/mixed) for writing; LLM-based; not code.
- **DEMM-Bench** (2606.20634): see item 9.
- **Agents label decision-relevant facts "unknown" instead of finding out** (toolboxmd/agentsmd issue 145) and related claim-audit tools: **agent-receipts** (0xelitesystem), **claimcheck** (bugyal), **agent-observer / agentsmd#162** (toolboxmd). agent-receipts: verdicts VERIFIED / STALE / UNVERIFIED / CONTRADICTED from transcript exit codes, filesystem and git; gaming signals (skip markers, `|| true`, `--no-verify`); regex claim extraction. claimcheck: diff + report + test log -> verified / unsupported / refuted / uncheckable, "a finding with no evidence is not emitted". Overlap HIGH with the simple claim-vs-evidence verdicts; confirm that STALE/UNVERIFIED/uncheckable verdict classes are already commodity. [read-page] for the two repos; agentsmd issues [snippet].
- **roam-code** (Cranot): SQLite code graph, 28 languages, `roam preflight` (what a change could affect incl. tests), `guard-pr` (what changed, which checks required/ran/missing), ChangeEvidence packets, SARIF, signed run ledger. Does NOT validate agent claims; states findings are leads. Overlaps the "downstream impact + missing checks" evidence-collector layer. [read-page].
- **Zero-trust / provenance-graph neighbours** [snippet only]: ARM (denied actions as first-class provenance nodes with counterfactual edges, a security-flow notion unrelated to claim verification), FAVA, AgentFlow, Grade, Agentproof (static verification of agent workflow graphs, e.g. "can this graph reach a destructive tool"). They reason about the *agent's own workflow* graph, not the system under change.
- **Designing for Doubt / informed abstention** (2606.02965): pre-condition-aware pause that names what is missing; 144 scenarios; abstention is on the agent side. Related to UNKNOWN-as-result, not to reality graphs. No counterfactual enumeration.
- **Uncertainty/UQ for agents** (2609.07395 etc.) [snippet]: probabilistic confidence; contradicts Agentvow's "no confidence from missing evidence" stance rather than overlapping.

---

## Direct answer: does any of these already do decision-sensitive counter-reality search?

Definition tested: given claim C and action A, enumerate counter-realities S' from a typed reality graph that (i) cannot be excluded by available snapshot-valid independent evidence and (ii) flip the approval decision under explicit rules; verdict CONTRADICTED if evidence excludes the agent's state, UNKNOWN if a flipping S' survives; suppress non-flipping findings.

| Work | Enumerates unexcluded alternative states? | Decision-flip filter? | Verdict | Source status |
|---|---|---|---|---|
| EA-Graph | No; UNPROVABLE is a per-claim terminal state for a changed dependency with withheld content (a special case) | No | Partial relative | read-full |
| ClaimReceipt | No; defines sufficiency as absence of same-evidence/different-truth pairs, and returns INCONCLUSIVE; no search | No | Formal relative | read-full |
| Assay | No (paper states it explores no what-if) ; blast radius is the *deterministic* invalidation frontier; obligation levels are a risk-proportional rule | Partly: obligation thresholds act as a decision rule but over "affected modules", not over unexcluded states | Not done | read-full |
| Verification-Time Dependency (Counterfactual Auditability) | Perturbs evaluator inputs, not world states | Measures decision reversal rate for a model | Different object | read-full |
| backcheck, agent-receipts, claimcheck, Receipts, Aga, AgentCheck | No | No | Not done | read-page |
| archagent | No (Hypothesis/fast-check stubs search for property violations in code, not claim-reality alternatives) | No | Not done | read-page |
| NIST probes, DEMM, ATP, NovaFabric, Maat, Zenodo 22368667, TEPA, 2608.25553 | No | No | Not done | read-page |
| roam-code | No; reports what a change could affect and what checks are missing (a list, not unexcluded states filtered by flips) | No | Closest *engineering* neighbour of the "unverified consumers" listing | read-page |
| RL counterfactual explanation literature (ACTER, COViz, etc., from SOTA_MATRIX) | Yes in RL policy space (minimal state change that flips the agent's action) | Yes (action flips) | Conceptual ancestor, different domain | snippet (per SOTA_MATRIX; not re-read by me) |

Conclusion: **No work I read implements the full mechanism; the nearest are partial.** Three caveats keep this a "potential gap requiring further verification": (1) the paper search was bounded and the 2026 arXiv volume in this area is large; (2) the mechanism, for the first claim class (no downstream impact), can be re-described as "dependency analysis (Assay / roam-code / blast-radius tools) + a threshold rule + evidence exclusion (EA-Graph/Assay freshness)". An examiner can argue that "unexcluded consumer of a changed interface => REVIEW" is simply Assay's coverage check plus obligation levels. (3) Formal-methods literature on counterexample-guided reasoning, abstraction refinement, and abductive/counter-abduction (search surfaced "counter-abduction" and CTL counterexample visualisation) was not read and may predate it conceptually. I did not search patents.

## Verdict: what is solved, engineering, potentially novel

### ALREADY SOLVED (cite, do not claim)
- Claim extraction and claim-vs-record verdicts with deterministic checkers and no LLM in the verdict path (backcheck, agent-receipts, claimcheck, Receipts).
- Stale-evidence rejection by commit/hash, including UNVERIFIED/STALE/CONTRADICTED classes (Aga, Receipts, agent-receipts, Assay, Looping-Is-Not-Reliability evidence).
- Binding claims to content/dependency hashes, staleness as hash comparison, blast radius = invalidation frontier, reuse of valid claims across agents as an assertion cache (Assay, EA-Graph).
- Evidence-vs-freshness separation, "refuse when stale", LLM quarantine from PROVEN, and an explicit terminal "unprovable" result (EA-Graph).
- Sub-path/granular artifact identity and alias-resolved anchors (EA-Graph).
- Separation-of-duties/independent reviewer, mechanical merge gate with obligations proportional to blast radius, human escalation (Assay).
- Architecture invariants via deterministic tools (archagent); static impact/preflight and missing-check listing (roam-code); integrity/tamper-evident records (NovaFabric, ATP); claim-sufficiency formalisation (ClaimReceipt); verifier independence should not be inferred from model diversity (Looping-Is-Not-Reliability, Zenodo 22368667).
- Claims-vs-independent-facts routing to Allow/Review/Deny for tool calls (EBTE).

### ENGINEERING / COMBINATION
- A unified, importable evidence schema (SARIF, OTel, git, CI, in-toto/PROV precedents).
- A Reality Graph richer than module dependency cones (typed nodes: interfaces, consumers, tests, invariants, policies) fed by existing collectors (roam-code, import-linter, dependency-cruiser, archagent).
- Cross-agent evidence reuse over *heterogeneous* agents (Assay's cache is the baseline; extension is engineering).
- Claim decomposition into verification obligations; plain-language decision objects; Agent Map view; source-agnostic ingestion.
- Independence as a typed vector (framing/evidence/mechanism/authority) used to cap SUPPORTED: only weak precedents (Assay role separation; Zenodo scalar ECS; 2608.29912 "non-independent" labelling). Treat as design contribution, not as a novel mechanism, until an ablation shows it changes outcomes.

### POTENTIALLY NOVEL (unverified; "Potential gap requiring further verification")
- **Decision-sensitive counter-reality search**: enumerating unexcluded counter-states that flip an explicit approval rule, returning UNKNOWN with the surviving flipping states and suppressing non-flipping findings. No read work does this; the closest are ClaimReceipt's sufficiency definition (no search), EA-Graph UNPROVABLE (per-claim, no flip filter), Assay's obligation gate (deterministic, no counter-states), RL counterfactual explanations (different domain).
- The *combination* "UNKNOWN that is gated by decision relevance" (reporting only unknowns that can change the human's approve/reject), as an anti-alert-fatigue mechanism. Assay and roam-code report the whole affected set or whole missing-check list. Needs a human-decision study to be a research result.

### Risks to state in the paper / next gate
- For the first claim class, the mechanism may reduce to Assay/roam-code impact analysis plus a rule (already flagged in NOVELTY_BOUNDARY.md). The benchmark must include Assay-style cone-binding + obligation gate as a baseline (B5/B6 level) and show that counter-reality filtering improves decisions beyond it.
- Update NOVELTY_BOUNDARY.md rejected-claims list (not edited by me): add "first dependency-cone-bound claims / blast-radius-as-invalidation-frontier / assertion build cache (Assay)", and "first unprovable/unknown terminal state (EA-Graph)". Correct the earlier summary of EA-Graph independence: the full text does not claim verifier-vs-agent independence.
- Still unread: Assay repo and code, Zenodo repo, patents, formal counterexample-guided verification literature, 2609.08258, 2609.01931 (Flight Recorder), other 2606-2609 agent-governance papers. Recommend a second pass on "counter-abduction" and regression-test-selection (Ekstazi-style) literature before claiming the mechanism.
