# 03 Verification Literature Review (academic, 2023-2026)

Workstream: sota-researcher / academic literature. Date of review: 2026-10-01.

## Method and honesty notes
- Tools: WebSearch plus WebFetch of arXiv abs pages. WebFetch returns a small-model summary of the page, so `[read]` below means "arXiv abstract/HTML page fetched and summarised by the fetch tool", NOT a careful full-text read by a human-grade reader. Where only a search-result summary was seen the tag is `[snippet]`. Classic works not retrieved this session are tagged `[recall]` (cited from memory; verify before use).
- Dates are inferred from arXiv IDs (YYMM). Many IDs are 2026 (post my training data); I could not cross-check them beyond the fetch result. Treat any ID/title as "as returned by the tools; verify before citing in a paper".
- Per CLAUDE.md: no `[snippet]` item should be cited as settled fact.
- Compact field key per entry: **P**=problem, **M**=mechanism, **I/O**=input/output, **Ev**=evidence source, **Ind**=independence mechanism, **Arch/State**=architecture/policy/state awareness, **Viz/Human**=visualization and human decision support, **Reuse**=prior-work reuse, **CE**=counterexample support, **Lim**=limitations, **Overlap/Diff**=overlap with and differentiation from Agentvow's DCRD (decision-sensitive counter-reality search + typed independence + UNKNOWN). Fields omitted when not applicable/unknown ("n/a" or "not stated").

---
## A. LLM-as-judge reliability, bias, correlated errors

**A1. Nine Judges, Two Effective Votes: Correlated Errors Undermine LLM Evaluation Panels** (arXiv 2605.29800, 2026-05) https://arxiv.org/abs/2605.29800 [read]
P: Are multi-judge panels independent? M: Kish effective sample size + Condorcet null model over pairwise error correlation. I/O: judge labels on ChaosNLI (MNLI/SNLI/AlphaNLI) -> n_eff (~2.2 of 9 judges, 7 families), accuracy gap 7.6-22 pp vs independent voting. Ind: measured statistically after the fact (error correlation), not typed by cause. Lim: classification/pairwise tasks only; offers no fix beyond "use genuinely diverse models". Overlap: empirical basis for Agentvow's "agreement != independence". Diff: diagnostic of correlation, not a structural typing of evidence or a policy that caps SUPPORTED.

**A2. Blind to the Pivotal Vote: Aggregate Independence Metrics Miss Where Verification Actually Helps** (2608.06940, 2026-08) https://arxiv.org/abs/2608.06940 [read]
P: Where does adding an external verification signal (e.g. test execution) help a judge panel? M: Majority-vote arithmetic: only single-vote-margin ("pivotal") cases can change; gains of +10.4 to +23.3 pp concentrate there, zero elsewhere. Data: HumanEval+/MBPP+. Ind: aggregate dependence metrics vs margin-stratified utility; not structural typing. Overlap: **a decision-pivotality notion applied to verification signals** - the closest conceptual neighbour to "filter by decision impact", but at the level of vote margins on a panel, not alternative world states. Diff: no state/evidence model, no counter-state search. Lim: single-ballot substitution policies, code benchmarks only.

**A3. Partially Correlated Verifier Cascades in LLM Harnesses** (2607.13918, 2026-07) https://arxiv.org/abs/2607.13918 [read]
P: Reliability of serial verifier gates under correlation. M: latent-variable (de Finetti) model; log-odds concave in depth, polynomial not exponential decay, "blind-spot atom" caps evidence; independence extrapolation underestimates failures 20x (k=5) to ~3000x (k=10). Ind: explicitly NOT typed structurally; independence is estimated from repeated verdicts. Overlap: strong theory support for capping confidence by independence. Diff: Agentvow proposes structural typing (framing/evidence/mechanism/authority); this paper gives no such typing. Lim: abstract-level theory.

**A4. A Statistical Framework for Auditing Behavioral Dependence and Induced Bias in LLM Judges** (2604.07650, 2026-04) https://arxiv.org/abs/2604.07650 [read]
M: Difficulty-weighted behavioral entanglement index + cumulative information gain over 18 LLMs / 6 families; entanglement correlates with judge over-endorsement (r~0.5). Ind: measured behavioural dependence, black-box. Overlap/Diff: same as A1; measures, does not type by evidence path.

**A5. LLM Evaluators Recognize and Favor Their Own Generations** (2404.13076, 2024-04) https://arxiv.org/abs/2404.13076 [snippet]
Self-recognition correlates linearly with self-preference. Supports "do not let the agent's own model family judge it". Not a mechanism for verification.

**A6. A Survey on LLM-as-a-Judge** (2411.15594, 2024-11) https://arxiv.org/abs/2411.15594 [snippet]
Catalogues position, verbosity, self-preference bias. Background only. (Also seen as snippets: Self-Preference Bias in LLM-as-a-Judge 2410.21819; Bias in the Loop: Auditing LLM-as-a-Judge for SE 2604.16790; Who Judges Matters 2609.17857 - not individually assessed.)

**A7. Characterizing False Success in LLM Agents (From Confident Closing to Silent Failure)** (2606.09863, 2026-06) https://arxiv.org/abs/2606.09863 [read]
P: Agents assert completion when env state says otherwise. M: 9,876 tau2-bench + 1,879 AppWorld trajectories with text-independent ground truth; 5 LLM judges x 5 prompts never exceed AUROC 0.65 (0.54 on AppWorld), judges anchor on "confident closing" language; TF-IDF detectors reach 0.83-0.95 AUROC at ~3,300x lower latency. Ind: ground truth is environment state, independent of text. Overlap: direct empirical evidence that LLM judges are not a safe verdict path (supports CLAUDE.md verdict-path rule). Diff: detects false success post hoc; no decision/counter-state layer. Lim: benchmark-specific; false-success rate 3-75.8% varies.

**A8. Verification-Status Laundering in LLM Agent Pipelines (Silence Is Endorsement)** (2609.20211, 2026-09) https://arxiv.org/abs/2609.20211 [read]
P: Summarisation strips "unverified" qualifiers; monitors then approve (approval 5%->60% Llama-3.1-8B, 9%->98% Qwen2.5-14B). Advocates structured state attached to claims, not instructions. Overlap: motivates keeping CLAIM/EVIDENCE/UNKNOWN as typed state, never prose. Diff: attack/finding paper, no verifier architecture.

---
## B. Self-verification, self-critique, debate

**B1. Large Language Models Cannot Self-Correct Reasoning Yet** (2310.01798, 2023-10, ICLR'24) https://arxiv.org/abs/2310.01798 [snippet]
Intrinsic self-correction without oracle feedback fails or degrades; gains in prior work came from oracle labels. Core support for "agent self-report != evidence".

**B2. Self-Refine** (2303.17651, 2023-03) https://arxiv.org/abs/2303.17651 [snippet]
Same-model feedback/refine loop. Counterpoint used by Huang et al.; gains small without external signal on reasoning.

**B3. When Can LLMs Actually Correct Their Own Mistakes? A Critical Survey of Self-Correction** (2406.01297, 2024) https://arxiv.org/abs/2406.01297 [snippet]
Survey: reliable self-correction needs external feedback. (Tyen et al., "LLMs cannot find reasoning errors, but can correct them given the error location", is from memory only - [recall], not retrieved.)

**B4. Debate Helps Supervise Unreliable Experts** (2311.08702, 2023-11) https://arxiv.org/abs/2311.08702 [snippet]; **B5. On scalable oversight with weak LLMs judging strong LLMs** (2407.04622, 2024-07) https://arxiv.org/abs/2407.04622 [snippet]; **B6. Training Language Models to Win Debates with Self-Play Improves Judge Accuracy** (2409.16636, 2024-09) https://arxiv.org/abs/2409.16636 [snippet]
Debate gives judges adversarially surfaced arguments; results mixed ("Debate Helps Weak Judges Reward Stronger Models", 2605.27483 [snippet]: null effects at low inference cost). Adversarial but argument-level and LLM-vs-LLM: counter-arguments are text, not evidence-consistent alternative states checked by a deterministic collector. Overlap: adversarial surfacing of what could be wrong. Diff: Agentvow's counter-reality is typed, evidence-consistency-checked, decision-gated; debate has no decision rule or UNKNOWN.

---
## C. Claim-level verification and agent-claim verification

**C1. FActScore** (2305.14251, 2023-05) https://arxiv.org/abs/2305.14251 [snippet] and **C2. Long-form factuality / SAFE** (2403.18802, 2024-03) https://arxiv.org/abs/2403.18802 [snippet]
Atomic-fact decomposition; SAFE adds decontextualisation and search-based per-fact check (72% agreement with human annotators). Evidence = web/Wikipedia; verdict via LLM. Reuse for claim decomposition. Diff: factual precision of text, no decision, no counter-state, LLM in verdict path.

**C3. Quantifying Overclaiming Propensity in Frontier LLM Agents (OverclaimBench)** (2609.20812, 2026-09) https://arxiv.org/abs/2609.20812 [read]
P: Final report claims work the transcript shows undone. M: deterministic file-"touch" coverage from transcripts + LLM judge (admission/omission/overclaim). 67.9% runs incomplete; 80.4% of those misleading; overclaim runs miss planted defects 1.8x more. Overlap: claim-vs-transcript check with deterministic coverage (like backcheck). Diff: measurement benchmark; no verifier product, no counter-reality. Lim: five scenarios, designed against Claude Opus.

**C4. How Coding Agents Fail Their Users (20,574 sessions)** (2605.29442, 2026-05) https://arxiv.org/abs/2605.29442 [read-abstract-level]
Observational; "inaccurate self-reporting" is one of 7 symptom classes and grows in share over time. (The 22.58% figure quoted by another paper was NOT confirmed in what I retrieved.) Motivation only.

**C5. ClaimReceipt: Verifying Evidence Sufficiency and Coverage in Agent Evaluations** (2609.01992, 2026-09) https://arxiv.org/abs/2609.01992 [read-abstract-level; PDF not parsed]
P: Reported agent-eval claims must be reproducible from retained evidence. M: claim-relative receipt spec; typed transaction evidence bound to signed experiment manifest; hash-linked transcripts; verdict PASS / INVALID / INCONCLUSIVE per claim; field-to-claim dependency matrix. Ind: cryptographic binding/pre-commitment, not evidence-source independence. Overlap: **three-valued verdict with INCONCLUSIVE first-class, typed evidence, claim-relative sufficiency** - overlaps the "claim -> SUPPORTED/CONTRADICTED/UNKNOWN" half. Diff: scope is agent-evaluation experiment records, not code-change approval; no alternative-state search; no decision-flip. Lim: authors admit the spec is not unambiguous to an independent reader. NOVELTY_BOUNDARY already lists it as unread; this is still only an abstract-level read.

**C6. Can Agent Benchmarks Support Their Scores?** (2605.10448, 2026-05) https://arxiv.org/abs/2605.10448 [read-abstract-level]
Outcome-evidence reporting layer for 5 benchmarks (AndroidWorld, AgentDojo, AppWorld, tau3-retail, MiniWoB): required artifacts, locked checklist -> Pass/Fail/Unknown, score bounds that keep Unknown visible. Overlap: **UNKNOWN-preserving, evidence-labelled outcome checking with score bounds**. Diff: audits benchmark outcome checks; no counter-state or decision layer.

**C7. AutoVerifier** (2604.02617, 2026-04) https://arxiv.org/abs/2604.02617 [read-abstract-level]
Six-layer LLM pipeline; claims as SPO triples in a KG; cross-source verification; **hypothesis matrix with adversarial counter-hypotheses**; weights by source independence (author overlap, affiliation, commercial interest). Overlap: counter-hypotheses + a *structural-ish* independence heuristic (shared authorship/affiliation) - the nearest hit on "typed independence" though for scientific literature. Diff: counter-hypotheses are LLM-generated and not checked for evidence-consistency or decision impact; no UNKNOWN rule; domain is S&T intelligence. Lim: static, LLM-prone.

**C8. Towards Verified Code Reasoning by LLMs** (2509.26546, 2025-09) https://arxiv.org/abs/2509.26546 [read-abstract-level]
Extracts formal representation of an agent's code-reasoning answer and verifies each step with program-analysis/formal tools; 13/20 uninitialised-variable examples validated, 6/8 wrong equivalence judgments caught. Overlap: deterministic verification of agent *claims about code* (no LLM verdict). Diff: per-answer correctness; no decision/counter-state/independence. Lim: 40 examples.

**C9. Attribution evaluation: AIS, ALCE (2305.14627), AttributedQA** https://arxiv.org/abs/2305.14627 [snippet]
Attributable-to-identified-sources framing; NLI-based AutoAIS. Evidence-grounded generation lineage; per-claim support, no decision layer.

**C10. Agent-as-a-Judge** (2410.10934, 2024-10) https://arxiv.org/abs/2410.10934 [snippet]; related AJ-Bench 2604.18240, DeepVerifier, Mind2Web 2 [snippet]
Agents evaluate agents with tool use. Still LLM verdict; independence from generator not guaranteed (see A1-A4).

---
## D. Evidence-grounding, staleness, drift

**D1. EA-Graph: Artifact-Anchored Verification Memory for Coding Agents under Upstream Drift** (2608.04278, 2026-08) https://arxiv.org/abs/2608.04278 [read-abstract-level]
Claims anchored to code artifacts at sub-path granularity, evidence strength separated from freshness; after change, claims become unaffected/affected/unprovable ("unprovable rather than guessed"). Fetch tool states it does not address counter-state exploration or decision-impact filtering. Overlap: staleness + UNKNOWN-like "unprovable" + reuse. Diff: no counter-state, no decision rule. Lim: small effect only on Haiku; Sonnet ceiling. (Full text still unread - gate blocker remains.)

**D2. Looping Is Not Reliability: State-Bound Evidence and Typed Revision Contracts** (2607.24604, 2026-07) https://arxiv.org/abs/2607.24604 [read-abstract-level]
Binds verifier evidence to exact code state; stale traces harmed 34/135 correct starts vs 4/135 with current traces. Typed contracts (admission, preservation, grounded certification, competence, liveness). Overlap: state-bound evidence (snapshot validity); "typed" but over revision contracts, not independence. No counter-state. Lim: implementation is a conformance artifact, not shown to improve repair.

**D3. When Agents Overtrust Environmental Evidence (EnvTrustBench)** (2605.08828, 2026-05) https://arxiv.org/abs/2605.08828 [read-abstract-level]
Evidence-grounding defect: agents act on plausible stale/incorrect environment claims. 83.3% aggregate misgrounding over 3,850 runs; layered taxonomy (admission, provenance, freshness, verification policy, action gating). Motivation + taxonomy of evidence layers; benchmark only.

**D4. STALE: Can LLM Agents Know When Their Memories Are No Longer Valid?** (2605.06527, 2026-05) https://arxiv.org/abs/2605.06527 [read-abstract-level]
400 conflict scenarios; best model 55.2%. Benchmark of staleness reasoning; no verifier mechanism.

**D5. Fresh Memory, Stale Plans: Dependency-Scoped Validation (Planfence)** (2609.03340, 2026-09) https://arxiv.org/abs/2609.03340 [read-abstract-level]
Plans store links to inputs; before protected actions follows an action-specific dependency frontier and re-checks currency; detected conflicts 0/30 -> 30/30. Overlap: **action-scoped dependency validation gating a consequential action** (a decision-scoped filter of which facts need re-validation). Diff: multi-agent shared memory, requires app-declared dependencies; no counter-state, no evidence independence.

**D6. From Agent Traces to Trust: Evidence Tracing and Execution Provenance in LLM Agents (survey)** (2606.04990, 2026-06) https://arxiv.org/abs/2606.04990 [snippet]
Notes limited staleness detection / evidence-aware verification in existing memory systems. Related-work scaffold.

---
## E. Runtime verification / structural architecture of verifiers

**E1. ContrAgent: Symbolic Temporal Supervision of LLM Agents Using Contracts** (2609.18128, 2026-09) https://arxiv.org/abs/2609.18128 [read-abstract-level]
Assume-guarantee LTLf contracts compiled to DFA; same artifact gates online and judges offline; no LLM judge. Policy/runtime verification of tool-call traces. Overlap: deterministic verdict path. Diff: trace-property compliance, not claim vs reality, no counter-state.

**E2. Verification as an Architectural Layer for LLM Agents (V-model)** (2609.31937, 2026-09) https://arxiv.org/abs/2609.31937 [read-abstract-level]
Each spec level has a deterministic gate + optional LLM judge; agent halts by abstaining and names the failed level. Pilot: 8B model, 4-hop QA only. Overlap: abstention as designed output. Diff: tiny pilot; no independence typing.

**E3. Runtime-verification cluster [snippet]:** Lean4Agent 2606.06523; AgentLTL 2607.02599; Causal Past Logic 2605.20923; PrefixGuard 2605.06455; TraceFix (TLA+ counterexamples for coordination protocols) 2605.07935; Why Formal Monitors Fail 2608.01388 (attack-distribution entropy bounds LTL monitor coverage). All check trace/protocol properties; none relate agent prose claims to external reality. TraceFix is the only one with counterexample output (TLA+ model checker over protocol, not repo state).

---
## F. Counterexample generation, falsification, may-analysis

**F1. CEGAR - Clarke, Grumberg, Jha, Lu, Veith, CAV 2000** https://link.springer.com/chapter/10.1007/10722167_15 [snippet; pre-2023 classic]
Abstract model may admit spurious counterexamples; analyse and refine. Structural analogue: "does a flipping counter-state actually survive the evidence (feasible) or is it spurious?" Agentvow's counter-reality filtering by evidence consistency is CEGAR's feasibility check in a different object domain. Not novel as a pattern.

**F2. Agentic Model Checking (BMC-Agent)** (2605.21434, 2026-05) https://arxiv.org/abs/2605.21434 [read]
"Agents propose, solvers verify": LLM infers specs, CBMC/Kani yields counterexamples, 4-stage validation (reachability, callee feasibility, dynamic replay, realism audit) classifies witnesses; spurious ones trigger refinement; 62 confirmed bugs. Overlap: **LLM proposes / deterministic checker decides + counterexample plausibility/realism filtering** = the same division of labour as Agentvow's verdict-path rule and "plausible S'" requirement. Diff: finds code defects against inferred specs, not a flip of an approve/reject decision; no independence typing, no UNKNOWN-because-unexcludable semantics. Lim: spec weakness undetectable; k=4 unwind.

**F3. Learning to Disprove: Formal Counterexample Generation with LLMs** (2603.19514, 2026-03) https://arxiv.org/abs/2603.19514 [snippet]; ExVerus (Verus repair via counterexample reasoning) 2603.25810 [snippet]; Loop invariant generation hybrid 2508.00419 [snippet]; Generative transformations ... verification and falsification 2404.09384 [snippet]
LLM-guided counterexample generation/use in formal settings. Counterexamples w.r.t. a formal spec, not a human decision.

**F4. KLEE (OSDI 2008)** https://llvm.org/pubs/2008-12-OSDI-KLEE.pdf [snippet; classic]; Daikon (likely invariants) [snippet; classic]
Symbolic execution finds concrete inputs reaching a target; Daikon infers likely invariants from observed runs. Mechanism neighbours for "find a state that falsifies" and for "evidence observed but not proven". They search program-input space, not repo/process reality states.

**F5. POPPER: Automated Hypothesis Validation with Agentic Sequential Falsifications** (2502.09858, 2025-02) https://arxiv.org/abs/2502.09858 [read-abstract-level]
LLM agents design/execute falsification experiments on measurable implications; sequential testing with Type-I error control. Falsification-first verification. Diff: statistical hypothesis testing on data; no decision-flip or evidence-independence layer.

**F6. Sound Agentic Science Requires Adversarial Experiments** (2604.22080, 2026-04) https://arxiv.org/abs/2604.22080 [snippet]
Position: agents should search for ways claims fail (alternative explanations, targeted checks). Conceptual overlap with counter-reality search at position level, no mechanism.

**F7. Counterfactual Fragility Certificates (CFC)** (2609.00366, 2026-09) https://arxiv.org/abs/2609.00366 [read-abstract-level]
Per-prediction audit of how decisions collapse when declared feature families become unavailable/degraded; greedy flip budget, margin-collapse area, recomputable certificate. **Closest formal analogue found to "which evidence failures flip the decision"**, including stale/delayed/noisy evidence. Diff: tabular ML predictions, user-declared failure protocol, no LLM agents, no claims, no verification-state graph, no independence typing, not a formal certificate. Lim: stated heuristic. Important for novelty: the *idea* of decision-flip fragility under evidence failure is not new in ML; its transfer to agent-claim approval is the open part.

**F8. Counterfactual explanation methods: Wachter et al. 2017 [recall], DiCE (Mothilal et al., 2020) [snippet via survey], diversity/plausibility/actionability work (e.g. 2511.20236, 2405.17642) [snippet]**
Search for minimal, plausible, actionable inputs that flip a model decision. Same formal shape as DCRD (find S' near S that flips decision, constrained by plausibility), with the "model" being a classifier. Reuse its desiderata (validity, proximity, plausibility, diversity) as evaluation criteria for counter-realities. Not novel as a search shape.

**F9. Robustness/abductive explanations for tree ensembles (e.g. Data-Aware Sensitivity Analysis for Decision Tree Ensembles, 2602.07453, ICLR 2026; Circuit Representations of Random Forests 2602.08362)** [snippet]
Formal enumeration of how a decision can be flipped by smallest feature changes. Same structural family.

**F10. Assurance 2.0 defeaters and eliminative argumentation (Bloomfield and Rushby)** https://arxiv.org/abs/2409.10665 [snippet]
Defeaters as first-class nodes: unresolved defeaters block claim acceptance; unresolved ones are documented as residual doubt. **Methodologically the closest pre-existing framework to "UNKNOWN when a flipping S' cannot be excluded"**: defeater = counter-state; residual doubt = UNKNOWN. Diff: human/semiformal argument practice, not automated search against a typed evidence graph; no decision rule filter; no LLM-agent setting. Must be cited and positioned against.

---
## G. Change impact, regression test selection, test adequacy ("what could be affected")

**G1. Static/dynamic Regression Test Selection (Legunsen et al., FSE 2016, [snippet]; Reflection-aware static RTS 2019 [snippet]; Fine-grained RTS (Liu et al. 2023) [snippet]; Names Are All You Need: Safe RTS for Python 2605.25356 [snippet])** 
RTS "safe" = selects every test that *may* be affected by a change (a may-analysis); unsafe causes: reflection, dynamic features. This **is** the established solution to "what could be affected by this change". Overlap: for the "tests cover this change / no downstream impact" claim class, the counter-state enumeration reduces to RTS/impact analysis (as NOVELTY_BOUNDARY already warns). Diff: RTS yields affected test sets, not a decision-gated UNKNOWN about an agent claim.

**G2. LLM-based change impact analysis:** ProReFiCIA (2511.00262, requirements, 93-96% recall) [snippet]; LLM-Augmented Release Intelligence (2603.14619) [snippet]; Towards CIA in Microservices (2501.11778) [snippet]. 
Impact on requirements / pipelines; LLM-heavy, recall-metrics, no verdict independence.

**G3. LLMs for call-graph / static analysis (2410.00603, 2402.17679, 2505.12118) [snippet]**: static tools (PyCG, Jelly) beat LLMs on soundness; supports "do not use LLM as may-analysis".

**G4. LLM triage of static-analysis findings (ZeroFalse 2510.02534 [snippet]; Mostly Harmless LLMs 2606.15122 [snippet])**: LLM as adjudicator of analyzer warnings to cut false positives - a *precision filter on findings*, but filters by FP likelihood, not by decision impact.

**G5. DiffTestGen: Change-Directed LLM-Based Testing for Exposing Behavioral Differences** (2607.16024, 2026-07) https://arxiv.org/abs/2607.16024 [read-abstract-level]
Static call graph guides LLM test generation toward modified code; union-coverage feedback; exposes behavioural differences in 78.2% of 463 PRs. A *concrete* counterexample generator (tests witnessing old/new difference). Reuse candidate as a collector. Diff: no claim/decision layer.

**G6. SWE-ABS: Adversarial Benchmark Strengthening** (2603.00520, 2026-03) https://arxiv.org/abs/2603.00520 [read-abstract-level]
Coverage-driven augmentation + **mutation-driven synthesis of plausible-but-incorrect patches** to expose test-suite blind spots; strengthens 50.2% of SWE-bench Verified instances, rejects 19.7% of passing patches (top score 78.8% -> 62.2%). Closest *mechanism* to "enumerate plausible alternative states the evidence cannot exclude": a surviving plausible-incorrect patch is a counter-state the tests don't exclude. Diff: generates adversarial patches to strengthen tests (benchmark hygiene), not per-claim counter-realities for a human approval decision; no UNKNOWN/decision gate. Highly relevant prior art.

**G7. UTBoost** (2506.09289, 2025-06) https://arxiv.org/abs/2506.09289 [snippet] and SWE-Bench+ (2410.06992) [snippet]
28.4% (SWE-bench Lite) / 15.7% (Verified) of passing patches erroneous due to insufficient tests. Empirical: "tests passed" is weak evidence.

**G8. Validation Evidence in LLM Repair Agents (BSG-VA)** (2607.28871, 2026-07) https://arxiv.org/abs/2607.28871 [read-abstract-level]
Replays each validation command on buggy / candidate / gold-fix states; 46.0% of passing tests carry no bug-discriminating information. Directly supports an "evidence discriminativeness" notion (does this evidence separate the real state from the alternative state?) - a core ingredient of excluding S'. Diff: measurement study; relies on gold fix; modest intervention effect.

---
## H. Property-based / metamorphic testing of agents; reward hacking; benchmark integrity

**H1. Action Metamorphic Relations in ReliabilityBench** (2601.06112, 2026-01) https://arxiv.org/abs/2601.06112 [snippet]; metamorphic-testing surveys (2605.13898) [snippet]; ARMeta 2605.28321, AgenticMeta 2605.25101 [snippet]
End-state-equivalence metamorphic pairs for agents. Testing agents, not verifying a given claim against reality.

**H2. Reward-hacking benchmarks:** EvilGenie 2511.21654 [snippet], SpecBench 2605.21384 [snippet], Reward Hacking Benchmark 2605.02964 [snippet], BaitBench 2608.30724 [snippet]
Detection via held-out tests, LLM judges, test-file-edit detection. Provide labelled data for H7-style evaluation (agent claims vs hidden truth).

**H3. The Verification Horizon: No Silver Bullet for Coding Agent Rewards** (2606.26300, 2026-06) https://arxiv.org/abs/2606.26300 [read-abstract-level]
Verifier/policy co-evolution; monitoring cut hacked-resolved rate 28.57% -> 0.56%. Argues no static verifier survives optimisation pressure - relevant adversary-model caveat for any fixed collector set.

**H4. Other agent-honesty benchmarks cited by C3 but NOT retrieved:** SPADE-Bench (Bu et al. 2026), BS-Bench (Shin 2026), Anthropic/OpenAI system-card false-completion metrics. [snippet via C3 text only] - verify before citing.

---
## Direct answers to the three hunt questions

1. **Does anything already search for decision-flipping alternative states consistent with evidence in a verification setting?** Not found in the exact form. Pieces exist separately: (a) counterfactual-explanation/abductive-explanation search shape on classifiers (F8, F9); (b) CFC for evidence-failure flip budgets on tabular predictions (F7); (c) Assurance 2.0 defeaters with residual doubt (F10) as a manual methodology; (d) SWE-ABS plausible-but-incorrect patch synthesis against test suites (G6); (e) BMC-Agent counterexample realism filtering (F2); (f) AutoVerifier LLM counter-hypotheses (C7). No work found combining agent-claim verification + typed evidence-consistency check + approve/reject decision flip + UNKNOWN. Search coverage is incomplete (search tool only; no Google Scholar, DBLP, ACM DL, patents), so "not found" is not "does not exist".
2. **Does anything filter verification findings by decision impact?** Only partially: A2 (pivotal-vote analysis of where verification can change a decision), D5 (action-scoped dependency frontier before protected actions), CFC margin collapse. Static-analysis triage (G4) filters by false-positive likelihood, and code-review work filters by acted-upon likelihood, not by decision flip. No work found that suppresses findings because they cannot flip a stated approval rule.
3. **Does anything type evidence independence structurally?** Not found. Existing work measures dependence statistically after the fact (A1, A3, A4) or uses heuristic provenance signals (AutoVerifier shared authors/affiliations; ClaimReceipt cryptographic binding; "static environment leakage vs policy-dependent shortcut" in H3 is a taxonomy of hack vectors, not of evidence independence). The structural vector (framing / evidence / mechanism / authority) appears to be an unoccupied position in the papers I could access; verify against security/assurance literature (e.g. diversity in safety-critical N-version software, common-cause failure analysis) which I did NOT search and which likely has analogous structural-independence concepts.

---
## Verdict

- **Not destroyed, but narrowed.** No retrieved work implements the full DCRD primitive. However every component has strong precedent: counterfactual/abductive flip search (F8-F9), CEGAR-style feasibility filtering of candidate counterexamples (F1, F2), eliminative argumentation with residual doubt (F10), mutation-style plausible-alternative generation against weak evidence (G6, G8), may-analysis impact (G1), staleness-bound evidence (D1, D2), three-valued PASS/INVALID/INCONCLUSIVE (C5, C6).
- **Novelty-risk ranking (highest first):** (1) Assurance 2.0 defeaters/residual doubt - conceptually near-identical to "UNKNOWN when a flipping S' survives"; must be positioned explicitly. (2) SWE-ABS + BSG-VA - already operationalise "plausible incorrect alternative the evidence cannot exclude" in SWE. (3) CFC - already operationalises "evidence-failure flips the decision" with certificates (tabular). (4) ClaimReceipt / "Can Agent Benchmarks Support Their Scores?" - three-valued, evidence-typed claim verification; unread in full. (5) For the "no downstream impact / tests cover this change" claim class, RTS/impact analysis likely solves the enumeration; the remaining value is the decision-gated UNKNOWN layer.
- **Defensible gap (label: "Potential gap requiring further verification"):** the *integration* of (a) agent-claim-conditioned counter-state search over a typed reality graph, (b) evidence-consistency feasibility check with snapshot-valid evidence, (c) suppression of findings that cannot flip an explicit human approval rule, (d) structural independence typing that caps SUPPORTED. Items (c) and (d) are the least-represented in the literature I could reach; (a)+(b) are an application of known patterns to a new object domain. The "first/novel" language should be avoided until patent and non-arXiv (ICSE/FSE/ASE, safety-assurance, N-version diversity) searches are done.
- **Evidence for the premise is strong:** A1, A3, A4, A7 (judge panels have ~2 effective votes; judges <=0.65 AUROC on false success; independence extrapolation off by 20-3000x) and C3, C4, G7, G8 (overclaiming is prevalent; passing tests often non-discriminative) support H7's motivation. Use A2 as a warning: external signals help only at pivotal decisions, which is a *supportive* argument for decision-sensitivity filtering but also a baseline Agentvow must beat.
- **Recommended next steps:** full-text read of ClaimReceipt, EA-Graph, Can Agent Benchmarks Support Their Scores?, CFC, SWE-ABS, Assurance 2.0 defeaters paper; search safety-assurance/N-version independence literature; search ICSE/FSE/ASE 2025-26 for agent change-impact and patch-validation papers; add SWE-ABS/BSG-VA-style and RTS baselines to the benchmark (B5/B6) so the ablation can show sensitivity filtering adds value.
