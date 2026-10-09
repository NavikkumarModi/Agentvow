# RISKS: Adversarial Review of AgentMirror (2026-10-01)

Reviewer stance: try to falsify. Severity: CRITICAL (kills or forces reframing of the core claim), MAJOR (invalidates a result or a sub-claim unless fixed), MINOR.
Source labels: [read] full source read this pass, [snippet] search summary only, [own] reasoning, [repo] AgentMirror docs.
Verified this pass: Assay repo page (OmShiv/assay-research) [read-page]; Maat 37% false-alarm figure [snippet]; Ekstazi/RTS safety literature [snippet]; Assurance 2.0 / eliminative argumentation / CoDefeater [snippet]; Knight and Leveson N-version results [snippet].

---

## A. Novelty and prior art

### A1 (CRITICAL) The core primitive is Assurance 2.0 / eliminative argumentation plus a decision rule, and the LLM-proposes-defeaters step already exists
- Claim attacked: "Decision-gated UNKNOWN via counter-state search" is a potential gap (NOVELTY_BOUNDARY item 1).
- Argument: Eliminative argumentation (Goodenough, Weinstock, Klein) and Assurance 2.0 (Bloomfield, Rushby) already define: enumerate doubts/defeaters against a claim, try to eliminate each with evidence, report unresolved ones as residual doubt. "Counter-state S' consistent with E that flips the decision" is a defeater not eliminated by evidence, filtered by consequence. CoDefeater (arXiv 2407.13717, ASE 2024) already uses LLMs to propose defeaters for assurance cases, i.e. the "LLM proposes, evidence disposes" architecture. The repo lists Assurance 2.0 under "ALREADY SOLVED" yet still counts the combination as potentially novel; the only residual delta is (i) automated, (ii) coding-agent claims, (iii) flip against a machine-readable rule. (i)-(iii) are application transfer, not mechanism.
- Evidence: arXiv 2405.15800, 2409.10665, 2407.13717 [snippet]. Rushby/Bloomfield explicitly address confirmation bias and "residual doubts".
- Mitigation: Reframe the contribution as "automating defeater elimination for agent claims with a decision-flip filter and testing whether it helps human approvers". Drop "novel mechanism" language. Add Assurance 2.0, eliminative argumentation, CoDefeater to PRIOR_ART E4. Do a full read of 2405.15800 before the gate.

### A2 (CRITICAL) For the first claim class the mechanism equals Assay + rule; for the second it equals Assay's `tests-pass` plus mutation/coverage evidence
- Claim attacked: claim classes (i) "no downstream impact", (ii) "tests cover this change".
- Argument: Verified from the Assay repo: nine predicates incl. `tests-pass`, `behavior-preserved`, `spec-satisfied`; gate checks coverage, freshness (cone hash), separation of duties, plausibility, monotonicity of test counts. Class (i) is cone analysis (Assay, roam-code, Ekstazi/STARTS RTS). Class (ii) "tests cover this change" is exactly what RTS and coverage/mutation tools compute (test-to-code dependency; mutation score shows whether tests could distinguish counter-states). "Counter-state that tests cannot exclude" is a mutant that survives. So the counter-state enumerator for class (ii) is mutation testing / SWE-ABS with an explicit decision threshold. The repo's pre-registration that (ii) "should separate the methods" has no argument behind it.
- Evidence: Assay repo [read-page]; Ekstazi and static RTS [snippet]; SWE-ABS in sota/03.
- Mitigation: Add mutation-testing (PIT/mutmut/Stryker) with survivor-count threshold as baseline B-MUT. If AgentMirror's enumerator is not strictly better than "mutation survivors in the dependency cone >= k => REVIEW", the mechanism is redundant. Falsifying experiment in section K.

### A3 (MAJOR) Counter-state "search" may collapse to a checklist of known defeater templates
- Argument: A typed graph with finite node/edge types yields a finite template set (consumer not visible, config override, test not exercising path, stale evidence, env difference, dynamic dispatch). If the enumerator is "for each template, check whether evidence excludes it", this is a static checklist (a lint), not a search. Calling it counter-reality search overstates it. Conversely if it is open-ended it is LLM-driven (A5).
- Mitigation: Publish the template taxonomy as the contribution or admit it; measure what fraction of flagged UNKNOWNs come from each template and whether a plain per-claim-class checklist matches recall.

### A4 (MAJOR) Independence vector is a design restatement of N-version / common-cause literature, which already shows that structural separation does not imply failure independence
- Argument: Knight and Leveson (1986) rejected independence at 99% confidence even for independently written versions; "separate evidence + separate mechanism" (the proposed SUPPORTED cap) does not establish independent failure. The vector labels provenance, not failure correlation. The rule "SUPPORTED needs one evidence separate on evidence+mechanism" is the same fallacy at coarser grain: two deterministic tools sharing the same parser, the same agent-edited test, or the same stale build cache are "separate" but common-mode. Also N-version-with-coding-agents (arXiv 2606.20158 [snippet]) replicates the correlation result for LLM agents; this is a direct citation for the premise and for why the vector can mislead.
- Mitigation: Either rename to "provenance labels" (no independence claim) or add shared-input analysis: edges for shared tool, shared parser, shared fixture, shared agent-authored artifact; cap SUPPORTED when any such edge connects the evidence to the claim. Cite N-version and common-cause failure (CCF) literature (e.g. IEC 61508 CCF beta-factor, defence in depth). Ablation required before claiming it matters.

### A5 (MAJOR) Patent and adjacent-system space unsearched; "no work found" is weak
- Already acknowledged. Also unsearched: SLSA / in-toto attestation use for claim binding (the repo plans to use in-toto as carrier, which means the evidence layer is explicitly commodity), model-based reasoning/abductive diagnosis (Reiter), counter-abduction, abstract interpretation may-analysis (sound over-approximation; "cannot be excluded" is the definition of may-alias/may-reach). The soundness vocabulary the project needs (sound over-approximation, precision loss) comes from abstract interpretation and RTS safety; claiming a new notion of "plausible counter-state" without that grounding invites rejection.
- Mitigation: Define the enumerator as an over-approximate may-analysis with explicit soundness assumptions (section E).

---

## B. Components and LLM use

### B1 (MAJOR) Several components are unnecessary for the research question
- Agent Graph (Goal to Plan to Action...), Work Harvester, Translator technical/business/plain tiers, protocol adapters, "reuse" (H5), Reality Graph richer than module cones: none is needed to test H7. Each adds a threats-to-validity surface and effort. H5 (reuse) is Assay's build cache; keep out of the research claim.
- Mitigation: v0.1 = claim extractor (manual/regex or LLM) + 2 evidence collectors + rule table + enumerator + CLI. Everything else is deferred behind an ablation showing it moves DCDR/harmful approvals.

### B2 (MAJOR) LLM usage in claim extraction is the weakest link and is outside the "no LLM in verdict path" guarantee
- Argument: Verdict = f(claim, evidence). If the claim is mis-extracted (too weak, too narrow, paraphrased to something checkable), a correct deterministic verdict is about the wrong proposition. Extraction error is silent and moves SUPPORTED/UNKNOWN. The rule is vacuous if the LLM decides what the claim is. Same for LLM-proposed counter-states: omission of a flip-state yields a false clean result and cannot be detected.
- Mitigation: For the benchmark, use templated claims with structured fields (no LLM extraction) to isolate the mechanism; separately measure extraction recall on real transcripts; render the extracted claim verbatim next to the source span; treat extraction failure as UNKNOWN, never as absent claim. Prefer deterministic extraction (structured final-report schema the agent must fill) and measure LLM uplift as an ablation.

---

## C. Evaluation flaws

### C1 (CRITICAL) DCDR is tautological if the same party defines the decision rule, the seeds, and the benchmark
- Claim attacked: "decision-changing" detection as the primary metric.
- Argument: The system flags S' iff decision(A|S') != decision(A|S_assumed) under an explicit rule table written by the authors. The benchmark seeds divergences that flip that same table. DCDR then measures consistency between the benchmark author's mental model and the rule table, not whether findings change real approver decisions. Any baseline that does not see the rule table (LLM reviewer, Assay) is handicapped by construction. A rule that flags everything flippable gives perfect recall; one that is narrow gives perfect precision on seeds.
- Mitigation: (1) Rule table and seeds authored by different people, rule table frozen and published before seeding. (2) Give every baseline the same rule table as a prompt/config (rule-aware LLM reviewer; rule-aware Assay obligations). (3) Construct validity: define "decision-changing" by external ground truth: real post-merge outcomes (reverts, CI breakage, incidents) from mined agent PRs, or expert panel ratings of "would a reasonable maintainer change their approve/reject" with inter-rater agreement (kappa) reported. (4) Report the metric as rule-conditional and keep human decision change as the primary outcome.

### C2 (CRITICAL) Ground-truth leakage and benchmark built for own method
- Argument: Scenarios store "hidden ground truth" and "seeded divergences". Seeds are drawn from the same taxonomy as the enumerator templates (A3), so recall is circular. Real divergences that matter (flaky env, runtime config, semantic wrongness) are outside the taxonomy and absent from the benchmark. Seeding also produces unnaturally clean artefacts (the seeded divergence is the only anomaly), which flatters any detector. Maat shows scorers crediting any halt as a catch inflated results; 35 of 94 halts (37%) were false alarms from validator defects [snippet]. The same scoring trap applies here: if UNKNOWN counts as success when ground truth is "divergent", an always-UNKNOWN system scores perfectly.
- Mitigation: (a) Mine real agent PRs (SWE-bench-style agent trajectories, public Claude Code/Copilot PRs) with post-hoc outcomes; (b) held-out seed taxonomy written by an outside party; (c) report precision/FPR first, always-UNKNOWN and always-SAFE trivial baselines; (d) pre-registered scoring script that penalises UNKNOWN on true-clean cases (selective-prediction metric: coverage vs risk curve); (e) manually audit every flagged finding on a sample, as Maat's authors did.

### C3 (MAJOR) Baselines too weak or mis-specified
- Assay-style gate: must be run with Assay's real code (repo exists), obligations tuned, including `tests-pass`, `behavior-preserved`. A re-implemented straw version is not acceptable.
- RTS: use Ekstazi/STARTS/Pytest-testmon-style selection to answer "is any test affected by the diff and did it run"; also mutation testing (A2).
- StateProof-like / agent-claim-verifier: run as is.
- LLM reviewer: a single-prompt reviewer is a straw man. Use (a) a rule-aware LLM with tool access (can run tests, read repo), (b) Claude Code Review or equivalent, (c) a panel with temperature variance, (d) "LLM reviewer + same collectors" so that the diff is the counter-state step only. If (d) matches AgentMirror the mechanism is unnecessary and the deterministic wrapper is the only contribution.
- Always-REVIEW and always-APPROVE as floor baselines. Cost-matched baseline (tokens + wall clock).

### C4 (MAJOR) Heterogeneous baselines have different outputs; unifying them hides disagreement
- Mapping Assay PASS/BLOCK, LLM free text, and UNKNOWN sets to one decision label requires choices that decide the winner. Pre-register the mapping; run sensitivity analysis over mappings.

### C5 (MINOR) Hypothesis count H1–H7 with no multiplicity control; pre-register primary (H7 or harmful-approval rate) and treat the rest as exploratory.

---

## D. Circular verification and evidence contamination

### D1 (CRITICAL) Agent-adjacent evidence leaks into "independent" evidence
- Paths: (1) Claude Code transcript is written by the harness but contains tool outputs that hooks and agent-controlled commands can rewrite or truncate; PostToolUse hooks can modify what the model sees (the repo notes this). (2) The agent chooses which tool to run, with which flags (`pytest -k`, `--no-verify`, `|| true`), so a "tests passed" artefact is agent-selected. (3) Agent-written tests count as evidence of the agent's change (Assay's own limitation: "reviewers can accept weak tests"). (4) The agent can edit CI config, conftest, coverage config, lockfiles, or the repo's `.assay/` directory-like state. (5) Collectors run inside the agent's environment (same shell, PATH, git hooks, env vars) inherit its compromise. (6) Reality Graph edges are extracted from code the agent just modified, so graph truth is agent-influenced (e.g. adding a dynamic import hides a consumer).
- Argument: Independence vector marks "mechanism: separate" for pytest, but the test file, selection, and environment are agent-controlled; "authority: separate" is false if the agent can write the invariants/policy files.
- Mitigation: Collectors run in a fresh container from the committed tree at a recorded hash, with agent-untouched config (config taken from base branch, not head); tests changed or added by the agent are labelled agent-authored and cap at claim-only for claims they support unless validated by pre-existing tests/mutants; diff the test/CI/config files and surface that as a finding; run collectors from base-branch tooling. Add a "contamination edge" check: any evidence whose inputs intersect the agent's write set is capped.

### D2 (MAJOR) Verification Horizon / gaming
- Argument: Adversary-aware agents will optimise for the verifier: avoid files the extractor reads, split edits to stay under thresholds, write claims in unparseable phrasing so they are "not extracted" (and then no claim, no finding), add tests that exercise lines without assertions, hide consumers behind reflection/DI/config. A verifier whose output approvers rely on creates the target (Goodhart). Any measured benefit on non-adaptive agents will not carry to optimised agents.
- Mitigation: Include an adversarially prompted agent arm ("get this approved") in the benchmark; track the unextracted-claim rate as a first-class metric; treat un-extracted material changes as UNKNOWN-by-coverage (diff-driven, not claim-driven): every changed region must be accounted for or flagged.

---

## E. Counter-state completeness and soundness

### E1 (CRITICAL) "Cannot be excluded" is only meaningful relative to an explicit, bounded state space; as defined it is unsound or vacuous
- Claim attacked: "UNKNOWN when a decision-flipping S' cannot be ruled out by evidence."
- Argument: The state space is unbounded (runtime, data, concurrency, deployment, human processes). Two ways out, both bad: (a) Enumerate only graph-derived states: then "SUPPORTED/no findings" means "none of my templates fired", unsound with respect to reality; (b) Allow any S' consistent with E: then S' always exists (evidence never fixes all state), so UNKNOWN is emitted for everything, which is the opposite of the claimed suppression. "Plausible" is the only filter that separates these, and plausibility is not defined; an LLM judging plausibility makes it an LLM judge (F1). The constraint "P-compatible facts" does not bound it either.
- Evidence: Abstract interpretation and RTS both solve this by fixing an abstraction and proving soundness relative to it ("safe" RTS selects all tests whose behaviour may be affected, under assumptions); even Ekstazi's safety depends on dynamic dependency tracking and breaks on unmodelled inputs (resources, reflection, external state) [snippet]. Assay itself notes regex import parsers under-approximate dynamic imports [read-page].
- Mitigation: Define a closed counter-state vocabulary per claim class with a stated soundness assumption ("sound relative to static import graph + these runtime config keys"), and make the output scope-labelled: "no decision-flipping counter-state in the modelled space M; outside M: UNKNOWN". Never print an unscoped OK. Add an explicit "unmodelled-space" residual line always present. Measure, on mined real incidents, what fraction fall outside M (model coverage) as the headline limitation.

### E2 (MAJOR) False-alarm rate and scalability
- Argument: Each added template raises UNKNOWN rate. Real repos have dozens of unexcluded template hits per diff; approvers will learn to dismiss them (alert fatigue, the problem the suppression filter is supposed to solve). The suppression filter keeps only those flipping the rule, but the rule (e.g. "any unexcluded consumer of a changed public interface => REVIEW") will flip on a large share of changes. Maat's 37% false alarms came from validator defects, not model behaviour, a direct warning that collector bugs dominate. Dynamic languages and monorepos make graph construction slow and lossy; per-claim enumeration multiplies cost.
- Mitigation: Pre-register a false-alarm budget (e.g. <=1 REVIEW-required finding per 5 diffs on clean agent PRs) and measure the REVIEW rate on 200+ real clean agent PRs before any human study; collector self-tests with known-answer fixtures; defect-triage of the first 100 findings by hand.

### E3 (MAJOR) The decision rule is a policy, not a fact; flip is rule-relative and brittle
- Argument: A rule table "approve iff no unexcluded consumer ..." makes S' enumeration a function of rule granularity. Small rule edits change the result set. Different teams hold different rules; "decision-changing" is not a stable property of the system.
- Mitigation: Evaluate across >=3 rule tables of varying strictness; report sensitivity.

---

## F. The Reality Challenger as another LLM judge

### F1 (MAJOR) Where LLMs re-enter the verdict
1. LLM proposes counter-states: its recall bounds soundness; its prior biases (same family as the agent) correlate with the agent's blind spots, so the challenger shares the agent's omissions (the judge-correlation premise applies to the proposer).
2. Feasibility ("plausible") of a counter-state: if validated by LLM, it is an LLM judgement in the path; if by evidence checks, the check set must be pre-existing (else the LLM is writing the check, which is the agent-written test problem).
3. LLM-generated "evidence checks" (scripts) are executable artefacts with their own bugs (Maat defects).
4. Claim extraction (B2).
5. Translator: LLM paraphrase of the decision object (G2).
- Mitigation: Make LLM proposals optional and measure marginal recall over the deterministic template set; require every proposal to bind to a typed graph node and an existing collector (a proposal with no checker => UNKNOWN labelled "unchecked proposal", shown below the fold, never blocking); log proposer identity and family, and prefer a proposer from a different family than the agent, though per N-version results this reduces but does not remove correlation. Report ablation: template-only vs template+LLM.

### F2 (MINOR) CoDefeater-style prior art (A1) means LLM defeater proposal is not itself publishable novelty.

---

## G. Human interface, automation bias, translator

### G1 (CRITICAL) The tool can create automation bias and complacency in the way it is designed to prevent them
- Argument: Parasuraman and Manzey: complacency rises with consistent reliability; the repo already notes this and plans AgentMirror-error trials, but v0.1 output status "NO DECISION-CHANGING FINDINGS" is a SAFE-adjacent message. With a tool that is mostly right, users will defer when it says "none", and miss the cases outside the modelled space (E1). Suppression of non-flipping findings removes the very information users would use to notice the tool is wrong. Juxtaposition of claim vs reality gives a veneer of ground truth ("independent reality") that the graph does not have. Explanations increase over-reliance in several studies (sota/04 §1.2).
- Mitigation: Replace "NO DECISION-CHANGING FINDINGS" with a scope-bounded string ("nothing flagged within modelled checks: [list]; not checked: [list]"). Never green. Keep a visible, cheap "suppressed N items that could not flip your rule" counter with expansion. Include tool-error trials (>=20% of trials) in the human study and report reliance-appropriateness (over/under-reliance on wrong AgentMirror outputs).

### G2 (MAJOR) Plain-language translator can misrepresent evidence
- Argument: R8 "never introduces facts not in the decision object" is unverifiable for an LLM translator; simplification silently drops scope and uncertainty (the stated risk), e.g. "tests pass" for "tests X, Y passed at hash H in env E excluding module Z". Hedging language ("probably") miscalibrates users. Templates are safer but less flexible.
- Mitigation: Template-based translation with typed slots for the default view; if an LLM paraphrases, constrain via a faithfulness check (every sentence must map to a decision-object field; entailment check by deterministic field comparison, number/identifier match). Test with comprehension questions in the human study (can the user state what is NOT verified?).

### G3 (MAJOR) Burden vs forcing function
- The research question says "without increasing review burden". A forcing function (making users read UNKNOWNs) increases time. The two goals trade off; an honest test shows a Pareto frontier. Measuring only time without accuracy, or only accuracy without time, will give a misleading win.
- Mitigation: Primary outcome pair: harmful-approval rate and time-to-decision, analysed jointly, with non-inferiority margin on time declared up front (e.g. <=+20%).

### G4 (MAJOR) Human study sample size and design
- Argument: Hidden within-subject effect of 10 to 15 percentage points in harmful approvals with 4 arms, difficulty covariates and tool-error trials needs far more than convenience samples of ~10-20 engineers. Learning effects across trials, demand characteristics (participants told the tool "checks reality"), and task realism (seeded diffs, no stakes) limit external validity. Seeded divergences measure detection of authors' taxonomy (C2).
- Mitigation: Power analysis against a stated smallest effect of interest; mixed-effects models with participant and task random effects; >=40 participants for a 3-arm within-subject design with ~12 diffs each, counterbalanced; pilot with 6 to 8 first. Include real agent-PR items with outcome-known labels, not only seeded ones. Report if inconclusive.

---

## H. UNKNOWN silently becoming SAFE (path audit)
Each item below is a path to "nothing shown" that a user will read as OK. Each needs a first-class rendered state.
1. No findings rendered as OK (v0.1 status "NO DECISION-CHANGING FINDINGS"). Must be scoped, never green.
2. Evidence absent treated as absence of divergence: enumerator iterates over existing evidence; no evidence for a template means no instance, not UNKNOWN. Make evidence-required templates fire UNKNOWN when their collector yields nothing.
3. Collector failure (timeout, crash, missing tool, permission): must produce COLLECTOR_ERROR which counts as UNKNOWN for dependent claims, visible in the output header.
4. Truncated graph (size caps, ignored directories, gitignored/generated code, vendored code, monorepo boundaries): coverage fraction must be reported; if below threshold, REVIEW.
5. Unsupported language/framework/file type in the diff: fail closed. Diff files outside any collector's scope listed as "unchecked".
6. Claim not extracted: no claim means nothing to reconcile. Diff-driven accounting (D2).
7. Suppression filter: findings dropped because rule lookup returned "no matching rule" (rule gap) must be UNKNOWN, not non-flipping. Default rule = REVIEW.
8. Stale evidence reuse: cache hit on cone hash while environment/config/runtime differs (section I).
9. Dynamic/reflective code and generated code (Assay under-approximation, RTS reflection).
10. Aggregation: a worst-of or any-of rollup that hides one UNKNOWN among many SUPPORTED; require monotone severity (any UNKNOWN keeps overall status non-OK).
11. Rule table versioning: change in rules between evidence time and decision time.
12. UI truncation or the "one click away" design (R6) hiding UNKNOWN categories.
- Mitigation: Property-based tests for "fail closed": inject faults in each collector and assert overall status never in {OK, NO FINDINGS}. Add this as a release gate and as a research claim (UNKNOWN-preservation rate under fault injection).

---

## I. Stale evidence and snapshot binding

### I1 (MAJOR) Snapshot hash binds source, not behaviour
- Argument: commit/tree hash does not bind: dependency versions (unpinned/transitive), OS/arch, env vars, system clock, network resources, database/service state, feature flags, container image digest, random seeds. Evidence VALID at hash H can be false in the deployment environment. Runtime vs repo state: the stated problem domain includes runtime/config divergence, but the snapshot binds the repo. Flaky tests: a single pass is not evidence of a pass; non-deterministic outcomes bound to a hash are samples. Reuse across agents (cache) propagates one flaky pass.
- Evidence: Assay doesn't handle non-determinism or runtime state [read-page]; Ekstazi-class tools address file deps but not external state [snippet].
- Mitigation: Snapshot = (tree hash, lockfile hash, container digest, env fingerprint, tool versions, seed); record N repeated runs for test claims (flakiness rate estimated; evidence strength = pass rate and variance); cap reuse when env fingerprint differs; "runtime state" evidence always labelled with timestamp and cannot satisfy a repo-level claim. Test: flaky-test injection and dependency-drift scenarios in the benchmark.

### I2 (MINOR) Freshness is time-blind: signed old evidence for an unchanged cone may rest on a since-fixed collector bug. Version collectors and invalidate on collector version change.

---

## J. Scope and strategic risks

### J1 (MAJOR) "First claim class reduces to Assay + rule" risk is real and the repo's mitigation is untested
- Already flagged; this review adds that class (ii) reduces to mutation/RTS (A2). If both reductions hold, the residual contribution is the human-facing decision view plus the UNKNOWN-first rendering, which is a UX contribution requiring only a human study, not a counter-state mechanism.

### J2 (MAJOR) Mechanism has no positive control
- No class is identified where the mechanism must succeed and others must fail. Without a constructed positive control (e.g. a change whose test suite passes but covers a path only via an unstubbed config switch), a null result is uninterpretable and a positive result is a design-by-construction artefact.
- Mitigation: Create 10 hand-made "traps" where baselines provably fail (e.g. tests pass but monkeypatched; consumer reached only via config), and check the mechanism catches them; then measure on organic data.

### J3 (MINOR) Dependence on fast-moving protocol targets (OTel GenAI "Development", MCP revision) is engineering risk; keep adapters out of v0.1.

---

## K. Cheap pilot before building v0.1 (the minimal falsifying experiment)

Pilot "P0: Can a rule-aware LLM reviewer with ordinary tools plus Assay/RTS/mutation do the same?" ~1 to 2 weeks, no AgentMirror code.

1. Data: 60 to 100 real agent PRs (public Claude Code / Copilot / Codex / SWE-agent PRs on repos with CI), each with the agent's claim of "tests cover this / no downstream impact" and an outcome label (later revert, bug-fix referencing the PR, CI break on main within 30 days, or expert panel label by 2 maintainers with kappa). Add 15 hand-made traps (J2).
2. Arms (all given the same rule table: "REVIEW if any unexcluded way the claim could be false that touches a public interface, config, or untested path"): (a) Assay real tool + obligations; (b) RTS (Ekstazi/STARTS/testmon) + mutation survivors threshold; (c) LLM reviewer with repo tools and the rule table; (d) hand-simulated AgentMirror enumerator: a human analyst applies the template taxonomy to the same PRs, with evidence collected by scripts. (d) is an upper bound on the mechanism; if (d) does not beat (a)+(b)+(c) on harmful-PR recall at a matched REVIEW rate, building the enumerator is unjustified.
3. Metrics: recall of harmful PRs at a fixed REVIEW rate (e.g. 20%), false-alarm rate on clean PRs, REVIEW rate overall, fraction of outcomes outside modelled space (E1), always-UNKNOWN baseline.
4. Pass condition: (d) beats best of (a)-(c) by >= 10 points recall at equal REVIEW rate with bootstrap CI excluding 0, and out-of-model fraction <= 40%.

---

## L. Recommended kill criteria
Stop or reframe if any hold:
1. P0 (d) fails to beat the best of Assay / RTS+mutation / rule-aware LLM+tools by the pass margin at matched REVIEW rate.
2. Out-of-model fraction of real harmful outcomes > 50% (the modelled counter-state space does not contain what actually goes wrong).
3. REVIEW rate on clean real agent PRs > 30% under the rule table, or false-alarm share of hand-audited findings > 25% (Maat-style collector defects).
4. A "rule-aware LLM reviewer with the same collectors" matches AgentMirror within the CI on harmful-approval detection and review time (then the deterministic layer adds trust properties but not decisions; reframe as audit tooling).
5. Fault-injection shows any collector failure path rendering OK / NO FINDINGS (blocking bug), or contamination test (D1) shows agent-influenced evidence reaching SUPPORTED in >5% of adversarial trials and the cap cannot be fixed.
6. Human pilot (n>=8): harmful-approval rate with AgentMirror is not lower than the agent-summary arm, or time-to-decision rises >50% without accuracy gain, or users approve AgentMirror-error trials at a higher rate than the baseline (complacency effect).
7. A patent/prior-art search finds claim-vs-state counter-state enumeration with decision flip already described (then claims restricted to the human-study contribution).

---

## M. Verdict
NARROW and REFRAME; do not proceed as defined.
- Drop the claim that counter-state search is a new mechanism; reposition as "automated defeater elimination with decision-flip suppression, evaluated for whether it improves human approval decisions over Assay-style gates, RTS/mutation evidence, and rule-aware LLM reviewers".
- Narrow v0.1 to one claim class where the baselines are weakest, "tests cover this change" including agent-authored tests and runtime/config trap cases, with a closed, scoped counter-state vocabulary and explicit unmodelled-space reporting.
- Cut Agent Graph, harvester, multi-tier translator, reuse, protocol adapters from the research claim.
- Run P0 (section K) before writing the enumerator. The most likely outcomes are that RTS + mutation + rule-aware LLM recovers most of the value (reframe to the human-facing UNKNOWN-first view) or that the real failures lie outside the modelled space (kill the "reality model" framing).
- Treat the human study as the primary contribution and design it first (G3, G4).


---

## Adversarial review of prototype (2026-10-06)

Scope: `agentmirror/*.py`, `scripts/planted_faults.py`, `scripts/ci_labels.py`, tests, README and docs. Method: read the code, then reproduce each finding in throwaway git repos in a temp dir (no network, nothing under `data/` executed). `python3 -m unittest discover -s tests`: 45 tests, OK. "Repro" lines use helpers that build a tiny repo and call `decision.check` / `cli.collect_test_evidence`. Verdicts below are the tool's actual output.

Headline: the README claim "Fail-closed: ... all yield INSUFFICIENT EVIDENCE" does not hold. Five independent paths reach `NO CONTRADICTION FOUND` / `SUPPORTED` while the claim is false or unchecked (F1, F2, F3, F4, F5).

### CRITICAL

**F1. Evidence in `.agentmirror/evidence/` is forgeable by the agent, and the "agent-authored" rejection is self-declared.** `reality.py:154-163`: independence is `_INDEP_AGENT` only if the JSON itself says `"produced_by": "agent"`; any other or missing value is treated as a separate tool. `.agentmirror` is excluded from the tree hash and from `dirty` (`reality.py:38,48`), and the agent can write it.
- Repro: repo whose only test is `assertTrue(False)`; agent writes `.agentmirror/evidence/f.json` = `{"commit": "<HEAD sha>", "result": "pass", "counts": {"passed": 7}}`. `check(..., "All tests pass.")` -> `NO CONTRADICTION FOUND`, `SUPPORTED_BY_PRIOR_EVIDENCE`. With claim "7 passed." the count even "matches".
- Contradicts: README ("rejecting stale and agent-authored ones"), CLAUDE.md Independence rule, RISKS D1 (contamination gate) which is now an open release-blocker.
- Fix: never trust files from the agent-writable tree. Store evidence outside the repo (e.g. `~/.agentmirror/<repo-id>/`), and sign records with a key the agent cannot read (HMAC or OS keychain). Treat any evidence without a valid signature as `agent` (independence "same"). Bind the record to {commit, tree, base, command, tool version}. Add an adversarial test that plants a forged file and asserts UNKNOWN.

### MAJOR

**F2. Tests vanishing or being neutralised counts as success.** The differential rule only flags tests that passed at base and *fail* at head; a missing test is neither (`runner.py:57-77`). The head's pass count is never compared to the base's pass set.
- Repro (unittest -v, via `collect_test_evidence`): code broken (`f()` returns 2), agent deletes `test_two` and rewrites `test_one` as `pass`, claims "All tests pass." -> `SUPPORTED` ("1 passed, 0 failed", no count stated). Variant: whole class `@unittest.skip` -> `0 passed, 0 failed, 2 skipped` -> `SUPPORTED` (`runner.py:134` treats exit 0 with any `ran` as "pass"; skips count toward `ran`). A `conftest.py` with `collect_ignore` was caught only by the incidental "suite cannot run" rule; `addopts=-k` gave inconclusive (OK).
- Fix: (a) `vanished = base_passed_ids - (head_passed_ids | head_failed_ids | head_skipped_ids)`; any vanished test -> CONTRADICTED/REVIEW ("N tests that existed and passed at base no longer run"), unless the diff shows an explicit deletion and then surface it as a decision item. (b) result "pass" requires `passed > 0`; skipped-only is UNKNOWN. (c) Report files under test paths / conftest / pytest.ini / tox.ini / setup.cfg changed by the agent as a mandatory finding (the oracle changed with the code).

**F3. Default `--base` hides earlier breakage; failures present at base are labelled "environmental", even when 100% of tests fail.** `cli.py:87` defaults to `HEAD~1`. If the agent made 2+ commits, a break introduced in commit 1 is "also at base".
- Repro: commit 1 breaks `a.f`; commit 2 touches README; `--base HEAD~1` -> `0 passed, 2 failed` -> `NOT_CONTRADICTED` and overall `NO CONTRADICTION FOUND`. With `--base HEAD~2` the same repo is CONTRADICTED.
- Also `_from_runs` (`decision.py:182-192`): `0 passed, N failed` with all failures present at base is rendered as a no-contradiction status, i.e. a red suite yields a green-ish headline.
- Fix: require an explicit base for `--run-tests`, or derive it (merge-base with the default branch / the session start commit). If `passed == 0` or failed > 0 at head, never emit NO_CONTRA: cap at UNKNOWN with "tests are failing at the checked state, whether or not they also failed at base". Record `base` in the evidence record and refuse to reuse evidence computed against a different base (currently not stored: `runner.py:151-154`).

**F4. Import-graph blind spots turn real consumers into NOT_CONTRADICTED ("no downstream impact").**
- src layout (`src/pkg/core.py` imported as `from pkg import core`): module names are derived from the repo-root path (`reality.py:86-90`), so `pkg.core` never resolves -> no consumers -> `NOT_CONTRADICTED`. This is the most common modern Python layout.
- Rename `a.py -> b.py` while `user.py` still does `import a`: `git diff --name-only` shows only `b.py`; `a.py` is not in `changed_py` and `user.py` imports a module that no longer exists -> `NOT_CONTRADICTED`.
- Delete `a.py` (imported by `user.py`) plus edit `c.py`: deleted files are not in `graph.imports` (`decision.py:56`), their importers are never found -> `NOT_CONTRADICTED`. (Deleting alone is UNKNOWN, by accident.)
- `from importlib import import_module; import_module("a")` is not flagged as a dynamic import: only `.attr == "import_module"` and `__import__` are (`reality.py:113-115`) -> no gap, `NOT_CONTRADICTED`.
- Fix: resolve modules against sys.path roots (detect `src/`, `pyproject` package-dir, `setup.cfg`), and when a project has an unresolved-first-party-import rate above a threshold treat that as a gap. Build the graph at *base* as well as at head and use base-graph dependents of every deleted/renamed/changed file (`git diff -M --name-status` for old names). Detect bare `import_module`, `importlib.util`, `exec`, `eval`, and string module references as gaps.

**F5. `backward_compatible` check misses common breaks and reports NOT_CONTRADICTED.** `api_diff.py`.
- Optional -> required positional param (`def f(a, b=1)` -> `def f(a, b)`): `added` only counts params absent from the old signature (`api_diff.py:46`) -> not flagged.
- Removing `from .m import thing` re-export from `__init__.py`: ImportFrom is not part of `public_api` -> not flagged.
- Annotated constants (`X: int = 1`) removed, return-type changes, decorators, sync->async: not flagged.
- A renamed file: old path is absent from the change list (rename detection) -> the removed API is never compared.
All four returned `NOT_CONTRADICTED` -> overall `NO CONTRADICTION FOUND`. Fix: diff with `-M --name-status` and compare old paths; add AnnAssign/ImportFrom/`__all__` to the API; treat "required-ness increased" as breaking; list every unchecked category in the finding, and downgrade to UNKNOWN when the diff touches `__init__.py`, `__all__` or has renames.

**F6. Exit code 0 for `INSUFFICIENT EVIDENCE`.** `cli.py:104` returns 1 only for REVIEW. A script or CI gate doing `agentmirror check && merge` proceeds on UNKNOWN. Also an uncaught `CalledProcessError` (bad `--base`, single-commit repo with default `HEAD~1`, no `sandbox-exec`) exits 1, indistinguishable from REVIEW.
- Repro: `cli.main(["check", "--repo", R, "--base", "HEAD~1", "--transcript", t])` with no test evidence -> prints INSUFFICIENT EVIDENCE, returns 0.
- Fix: exit codes 0 = NO_CONTRA only, 1 = REVIEW, 2 = INSUFFICIENT, 3 = tool error; document it. Catch collector errors in `collect_test_evidence` and convert to a visible UNKNOWN finding.

**F7. CI ingestion semantic holes (`ci.py`).**
- A red CI is ignored when any local run exists: `decision.py:129` only looks at CI when `not runs`. Repro: CI "unit tests" failure + a local passing record -> `SUPPORTED` (CI red alone -> CONTRADICTED). Fix: CI failure on the same commit must always contribute a finding; disagreement between CI and local run is itself REVIEW.
- `skipped` and `neutral` conclusions are counted as pass (`ci.py:41`): a skipped test job (path filters, `if:` conditions, fork PRs without secrets) -> `SUPPORTED`. Fix: only `success`; skipped/neutral -> UNKNOWN.
- Name heuristic is a gate for fail-open: a failing `build (3.12)` job that runs pytest is ignored while a green `tests` job gives SUPPORTED. Step 11 itself documents 6 of 27 raw failures turning into SUPPORTED and "34 SUPPORTED" cannot be called verified. Fix: any failing/cancelled/timed-out check on the commit that is not on an explicit allow-list of non-test jobs forces UNKNOWN (deny-list by name is the wrong default direction); require the repo's branch-protection required-checks list when readable.
- No pagination: `per_page=100` only (`ci.py:35`); a failing test job on page 2 is invisible. Legacy commit statuses (Jenkins, CircleCI) are never read here although `ci_labels.py` reads them. In-progress/queued checks are silently dropped. The remote slug comes from `origin` in the agent-writable `.git/config`: pointing it at a repo the agent controls yields green fake checks. Fix: paginate (`--paginate`), read `/status`, treat non-completed as UNKNOWN, take the slug from the user rather than from the repo config, and verify the PR/commit really belongs to that repository.
- Status API vs checks API: duplicate names across matrix/reruns are not de-duplicated; a rerun flipping a job is not distinguished.

**F8. Snapshot binding gaps.** (`reality.py:36-49, 160`)
- `dirty` ignores gitignored files, so changing an ignored file that tests read (`.env`, generated fixtures, a local `conftest`) leaves `dirty=False`, `tree=""`, and old evidence stays VALID. Repro: change an ignored file -> `dirty False, tree unchanged`.
- A clean HEAD accepts evidence recorded on a dirty tree for the same commit (`commit == snap.commit and (not snap.dirty or ...)`): record made on dirty state T, then `git checkout .` -> evidence from different code is VALID. Repro confirmed (freshness VALID).
- Untracked-but-ignored files are also missing from the overlay in `collect_test_evidence`, so the tested state is not the user's state; the evidence says "exact state".
- Tree hash gaps: symlinks are followed (`is_file()`), dir-symlinks and submodule gitlinks hash as `<missing>`; mode bits are not hashed; hash input has no length framing (`path\0content` concatenation); whole files are read into memory. Evidence is not bound to base, command, interpreter, or tool version.
- Fix: bind to `git write-tree` of an index built with `git add -A` into a temporary index (plus an explicit list of ignored files that exist), require `rec.tree == snap.tree` always (clean trees too), include `base`, `command`, python version, and lockfile hash in the record; treat gitlinks/symlinks explicitly.

### MINOR

**F9. Parse and id-extraction mis-extractions in `runner.py`.**
- Test output can forge counts: a test printing `Ran 999 tests in 0.1s` makes `parse_counts` report 998 passed + 1 failed (`runner.py:86`, first match wins, anywhere in output). The same applies to `skipped=` and `PASSED x` / `... ok` lines. Agent-authored tests control stdout. Fix: use a machine format (`pytest --junitxml`, `unittest` with a custom TextTestResult / `python -m xmlrunner`) written to a file outside the repo, not regexes over mixed stdout.
- unittest `subTest` failures print `test_s (m.C.test_s) (i=1)`; that id is not in the base passed set -> `uncomparable`, regression missed (`regressions: 0, uncomparable: 2`), and `passed` becomes **-1** (negative counts) because a test with failing subtests is both counted by Ran and by failures. Fail-closed here (UNKNOWN), but a real regression is reported as a non-event.
- pytest ids containing spaces (`test_p[a b]`): `PASSED (\S+)` drops them entirely (base passed ids = [] in repro) and truncates failed ids to `test_p.py::test_p[a` (`runner.py:21,24`); ids collide (`[a b]`, `[a c]`). Fix: parse the junit XML.
- `xfailed/xpassed/deselected` are ignored; `xpass(strict)` and `-k` deselection from `addopts` are invisible. Pytest summary is read from the last 3 lines only; plugin footers push it out (fail-closed to inconclusive, but loses data).
- Flaky tests: a single run at base and at head; a flaky pass at base then fail at head is a false CONTRADICTED, a flaky fail at base masks a real break. No retry or variance recorded (RISKS I1 now has a concrete bug surface).
- `--test-cmd` is `.split()` with `str.format`: quoted args (`-k "not slow"`) break, and any `{`/`}` raises. `sandbox-exec` missing -> uncaught `FileNotFoundError`.

**F10. Sandbox soundness (`runner.py:80-82`, `(allow default)`).** Verified by running a probe under the actual profile: network TCP connect is denied, writes to the real `$HOME` denied, BUT: reads are unrestricted (`os.listdir(real_home)` works; `pwd.getpwuid().pw_dir` bypasses the `HOME` override; `~/.ssh`, keychain-adjacent files, browser profiles, and `~/.claude` are readable); `/private/tmp` and `/private/var/folders` are world-writable to the test, so it can read/write other tools' temp data and the sibling base worktree; with `allow default` mach lookups, DNS (mDNSResponder) and `open`/LaunchServices are not blocked by the file/network rules (not exercised in this review, no network access was made; treat as an unverified but plausible exfiltration/escape channel). Process exec, signals and subprocess grandchildren are unrestricted. The env is scrubbed to PATH/HOME, which is good, but `PATH` may carry credential-bearing shims. HOME is `repo.parent.parent/"home"`: for `cli` runs that is `$TMPDIR/home`, shared between base and head runs and across invocations (cross-run state/cache poisoning, nondeterminism); for `run_pair` on `/Users/u/proj/repo` it creates `/Users/u/home`. `sandbox-exec` is deprecated.
- Fix: `(deny default)` with explicit read allow-list (repo, interpreter prefix, stdlib/site-packages, system libs), deny `file-read*` for `$HOME` and `/private/var/db`, deny `mach-lookup` except what Python needs, per-run HOME, per-run temp dir; or run in a container/VM. State plainly in docs that running untrusted repo tests with this profile is not safe against data exfiltration through allowed channels.

**F11. Claim extraction under-reports what is unchecked.** A sentence that matches a checkable pattern is not also scanned for `_GENERIC` ("All tests pass and it's safe to merge." lists only the tests claim), and claims outside the four generic phrases ("dropped the legacy table", "performance unchanged") are invisible; the status can be NO_CONTRA with most of the agent's message unaddressed. README says "unchecked claims ... yield INSUFFICIENT EVIDENCE"; true only for the four phrases. Negations ("could not confirm all tests pass") match `TESTS_PASS`. Count extraction is loose: `sizes` accepts `passed`, `passed+skipped` or any single suite's count, so a coincidental number matches. Fix: always emit a "not checked" list of every non-matching sentence that makes a factual claim (or at least say how many sentences were not examined), and require the count to equal the sum of suites.

**F12. Whole-repo run vs scoped claims.** "Tests pass" is verified against the whole configured suite (or a user-given cmd). Claims about a subset ("test_foo passes") are not matched to that subset; with no count the verdict is for the full suite and with a count that differs it becomes UNKNOWN. Not a fail-open, but the finding text claims more than the check does.

### Benchmark validity (planted-fault study, `scripts/planted_faults.py`, `PLANTED_FAULTS.md`)
- **Circular oracle.** Oracle = "raw passed count dropped"; the tool's detector = "tests that passed before now fail" from the same run. A fault is "oracle-confirmed" only if the test suite already notices it, so 24/31 is a sensitivity of the *id-matching plumbing* to test-detectable faults, not detection of agent errors. The document says so; the README line "24/31 oracle-confirmed breaks flagged, 0 false alarms" is shorter and loses "oracle = tests detect it". Suggest rewriting: "24/31 test-detectable planted faults were attributed correctly".
- **Tuned on the test set.** The three fixes in "How we got there" (0 -> 21 -> 24 of 31) were made against the same 31 variants; no held-out repos/PRs. Final numbers are a training score. The "suite cannot run" rule (+3) is exactly what import/syntax faults hit.
- **Non-independent samples and operator bias.** 31 variants come from 12 PRs in 2 repos; `import_break` and `syntax_break` on the same file are the same event (both are module-level failures), so effective n is much smaller than 31 and the 77% has no interval. Eight operator flips (`==`,`!=`,`<`,`>`,`return True/False`,`and/or`,`in`) on lines the PR added only; only the first file is used for import/syntax faults; `k=2` per PR; 9 behaviour mutants in total (4/9 = 44%, the only informative row). No equivalent-mutant handling other than the oracle.
- **Selection.** 15 PRs were those with tests runnable in the sandbox, claim regex-matched (`STRICT`), agents restricted to Claude_Code/Copilot/Devin; 2 small repos. Selection is on tool-friendliness.
- **Bypasses the product path.** The script calls `decision._tests` with a hand-built `Evidence` (`planted_faults.py:75-77`), skipping `load_prior_evidence`, `check()`, `--base` defaulting, overlay of uncommitted work, the CLI's HOME and worktree handling. F1-F3 are all invisible to it. Its "0 false alarms" says nothing about the forged-evidence or vanished-test paths.
- **False-alarm denominator is weak.** Benign comments cannot change tests; 0/12 is guaranteed by construction. 0/15 clean states only shows determinism on one run of each (flakiness not measured, as the doc admits).
- **No negative controls for the new failure modes** (deleted tests, skipped tests, forged evidence, renames, src layout). Suggested additions: add those as planted-fault classes; a held-out repo set; report counts with Wilson intervals by *PR cluster*.
- `ci_labels.py`: label "failure" for *any* failing/cancelled check, including lint/Sonar/title checks (Step 10 admits 6/27 are "other"); head SHA is the final PR commit, which may postdate the PR-body claim; `per_page=100` with no pagination; the `none` class is not distinguishable from API errors/rate limits except for the PR fetch. It is described as ground truth in S0 Step 9 ("27 PRs claim 'tests pass' while CI fails"); that wording over-claims, and Step 11's "13 CONTRADICTED, 34 SUPPORTED" mixes a name-heuristic classifier with a name-heuristic oracle (circular for "SUPPORTED").

### Statements that over-claim (and suggested replacement)
1. README "Fail-closed: ... all yield INSUFFICIENT EVIDENCE" -> "Several known paths fail open (RISKS adversarial review F1-F5)".
2. README "rejecting stale and agent-authored ones" -> "rejecting records that declare themselves agent-authored; records are not signed and an agent can forge them".
3. runner.py header "Evidence ... marked as produced by a separate tool (not the agent)" -> accurate only for records the runner wrote; no integrity protection.
4. README "evidence is bound to a content hash of the working tree (tracked + untracked files)" -> "non-ignored files only; clean trees ignore the recorded tree".
5. README "counts only tests that passed before and fail now as regressions" -> add "tests that disappear or are skipped are not counted".
6. README Evidence line "0 false alarms" -> "0 of 34 control variants, which by construction cannot change test outcomes (benign comments) or do not (clean)".
7. `decision.py` docstring "missing evidence, collector errors, parse gaps and unchecked claims all yield UNKNOWN" -> false for F2, F4, F5, F7.
8. Status string `NO CONTRADICTION FOUND` is emitted when `0 passed, N failed` at head (F3); the headline implies a pass.

### Priority order for fixes
F1 (signed, out-of-repo evidence), F2 + F3 (vanished/skipped tests, mandatory base, never NO_CONTRA with red tests), F6 (exit codes), F7 (CI never ignored on red), F4/F5 (graph and API diff on base and head, rename/delete aware, src layout), F8 (tree binding), then F9-F12, sandbox hardening, and extend the planted-fault study to include the new adversarial classes with a held-out set before reporting any number again. Gate: add the fault-injection / contamination tests promised in RISKS H and D1 as release blockers; none exist in `tests/` today.


## Adversarial review of integration surface (2026-10-07)

Scope: adapters, hook, report, envsetup, ci, runner, decision (new policy), action.yml, VS Code extension, tests. Reproductions ran in `/private/tmp/claude-501/rv2` with `AGENTMIRROR_HOME` set to a temp dir; nothing under `data/` or `~/.claude`, no network. Earlier resolved items (F1-F12 of 2026-10-06) are not repeated. 121 existing unit tests pass; none of the items below is covered by them.

### CRITICAL

**G1. Editable installs make the BASE run execute HEAD code; a real regression is reported `NO CONTRADICTION FOUND`.** `collect_test_evidence` runs base and head in throwaway worktrees, but the interpreter (`--python`, default `<repo>/.venv`, or the `--setup auto` venv) has the project installed editable from the REAL repo. With a src layout (or any editable finder winning over cwd) both worktrees import the user's current code.
- Repro: repo `r14` with `src/pkg/__init__.py` (`f()` returns 1), test asserts `f()==1`; commit 2 changes `f()` to return 2. venv built with `pip install -e .`. `agentmirror check --base HEAD~1 --run-tests --python <venv>/bin/python --test-cmd "{py} -m unittest -v"` printed `STATUS: NO CONTRADICTION FOUND ... tests: 0 passed, 1 failed ... All failures also occur without the change`. Exit 0.
- Why: the base run saw head code, so the failing test is "known-failing at base". The differential rule inverts into a fail-open on exactly the commonest developer setup. `envsetup._pip` runs `pip install -e .` with `cwd=repo` = the user's real repo, which also writes `*.egg-info`/`build` into the user's tree (the profile allows repo writes), contradicting "the user's tree is never touched".
- Fix: per run, put the worktree (and `worktree/src`) first via `PYTHONPATH` and verify with a probe (`python -c "import <top-level pkg>; print(__file__)"` must resolve inside the worktree, else result = inconclusive "environment is bound to another checkout"); in `--setup auto` install into each worktree separately (`-e` of the worktree, never of the real repo) or non-editable. Add a regression test with a src-layout editable fixture.

**G2. Evidence signing does not stop a test process (or the agent) from forging evidence; the HMAC key is readable inside the sandbox.** `(allow default)` allows reads everywhere, so `~/.agentmirror/key` is readable by the agent-written test.
- Repro: sandbox profile from `runner._profile` read the 32-byte key (`KEY_BYTES_READ 32`). A test in `tests/test_zz.py` found the real repo via `git rev-parse --git-common-dir`, signed `{"result":"pass","counts":{"passed":1,...}}` with that key, wrote `.agentmirror/evidence/testrun_forged.json` into the real repo, then `os._exit(0)` so the genuine run became inconclusive. The decision accepted the forged record as signed, independent, VALID evidence ("forged: 1 passed, 0 failed"). It only degraded to UNKNOWN because the genuine record was counted as "partial".
- Conditions for the sandboxed path: the real repo lies under `/private/tmp`, `/private/var/folders` or `$TMPDIR` (all write-allowed by the profile; CI scratch dirs, temp clones, this very scratchpad). An unsandboxed agent (hook mode) needs no condition, as README admits. So signing protects only against content that arrives by git (a pulled branch or fork), not against the agent being checked.
- Fix: (1) do not round-trip evidence through an agent-writable directory in the same invocation: `collect_test_evidence` should return the records to `check()` in memory; (2) deny `file-read*` of `~/.agentmirror` and `file-write*` of everything outside the worktree/tmp in the profile (see G6); (3) keep the key in the OS keychain or a root/other-uid helper if the claim "agent-authored evidence is rejected" is to hold; (4) put `.agentmirror/evidence` out of the repo (`~/.agentmirror/evidence/<repo-id>/`).

### MAJOR

**G3. Hook-mode arbitrary file clobber through symlinks.** `run_hook` does `(out/"report.html").write_text(...)` and `decision.json` with `out = <cwd>/.agentmirror/last`; the repo is agent-controlled and symlinks are followed.
- Repro: `ln -s victim/zshrc repo/.agentmirror/last/report.html`; stdin `{"cwd": repo, "last_assistant_message": "All tests pass."}` -> `agentmirror check --hook`; `victim/zshrc` was replaced by `<!doctype html>...` (`PRECIOUS CONTENT` lost). Same for `.agentmirror/evidence` and the `testrun_*.json` writes in `cli.collect_test_evidence`. The hook runs outside any agent sandbox, so this is a sandbox escape from "agent can write repo files" to "overwrite any file the user owns" (content is mostly fixed HTML/JSON, with agent text HTML-escaped but `$(...)`/`;` unescaped).
- Fix: create `last/` with `O_NOFOLLOW`/`os.open(..., O_CREAT|O_EXCL)` into a temp name then `os.replace`; refuse if any component of `.agentmirror` is a symlink (`os.path.realpath(out).startswith(realpath(repo))`); better, write outside the repo (G5).

**G4. `git` and git hooks of the checked repo run unsandboxed, in hook and CLI mode.**
- Repro: `.git/hooks/post-checkout` created `hookproof.txt` when `agentmirror check --run-tests` ran `git worktree add` (hook ran as the user with cwd = the temp worktree, outside `sandbox-exec`). `git config core.fsmonitor "<cmd>"` ran `<cmd>` on every `git status` in `reality.snapshot`, i.e. even without `--run-tests`.
- Impact: whoever can write `.git/` (an agent allowed to edit the repo, or a tarball/zip with a bundled `.git`) executes code at the moment AgentMirror runs, outside the sandbox, and gets code execution from "may edit files" in agent harnesses that protect `.git` less than the verifier's own process. Also `diff.external`, `core.pager` (not exercised).
- Fix: every git call through one helper with `-c core.fsmonitor= -c core.hooksPath=/dev/null -c core.untrackedCache=false -c protocol.allow=never` and `GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null`; `git worktree add --no-checkout` then `checkout` with hooks disabled; warn when `.git/config` contains `fsmonitor|hooksPath|filter|external`.

**G5. Forged or stale verdict channel (`.agentmirror/last/*`, VS Code status bar).** `decision.json` and `report.html` are plain files in the repo; the extension trusts them and the two are not even cross-checked (status bar from `decision.json`, page from `report.html`). A branch/PR that contains `.agentmirror/last/decision.json` with `"status":"NO CONTRADICTION FOUND..."` flips the status bar green on checkout/pull (create/change event), and the agent can write it at any time. Compared with the signed-evidence design this is a real gap: evidence is signed, the verdict that humans actually see is not, and the commit/tree is not compared with the current HEAD.
- Fix: write the verdict to `~/.agentmirror/last/<hash(repo realpath)>/` (not in the repo) and have the extension read from there; include `commit`, `tree`, `created_at`, a random run id and an HMAC (node `crypto` with the user key) and have the extension show "stale" when HEAD or the tree differs; derive the status bar and the page from the same signed file. State plainly that this defends against repo content, not against a same-uid agent.

**G6. VS Code: workspace-chosen executable runs even in an untrusted workspace; setting scopes and CSP incomplete.**
- `agentmirror.command` / `.python` / `.testCommand` have no `"scope"`, so `.vscode/settings.json` of a cloned repo sets them. `extension.js:55` does `cp.execFile(cfg.command, ...)` with `cwd = workspace root`: `{"agentmirror.command": "./evil.sh"}` runs the repo's script as soon as the user invokes any "AgentMirror: Check ..." command. Only `runTests` is gated by `isTrusted` (`extension.js:44`); `command` is not. `package.json` declares `untrustedWorkspaces: limited` with no `restrictedConfigurations`, so VS Code does not ignore these workspace values in Restricted Mode. The README claim "by default nothing is executed ... disabled in untrusted workspaces" is therefore wrong for the `command` setting.
- Fix: `"scope": "machine"` (or `machine-overridable`) on `command`, `python`; `"capabilities.untrustedWorkspaces.restrictedConfigurations": ["agentmirror.command","agentmirror.python","agentmirror.testCommand","agentmirror.runTests","agentmirror.useCI","agentmirror.base"]`; in code refuse relative/in-workspace `command` paths; activate only if `vscode.workspace.isTrusted` or run nothing but report display otherwise.
- Webview: the injected CSP `default-src 'none'; style-src 'unsafe-inline'; img-src data:` lacks `form-action 'none'; base-uri 'none'; frame-src 'none'` (`default-src` does not cover `form-action` or `base-uri`). `report.html` is read from the repo without validation (`extension.js:68`), so a hostile file can show a forged green banner, a login-looking form and links. `injectCsp` only replaces the first literal `<head>`; with none it prepends the meta before `<!doctype>` (quirks mode). Scripts are disabled so exfiltration is limited to form/link navigation, but phishing/spoofing is real. Fix: add those directives, extract the body and re-render from the validated JSON instead of trusting HTML, size-limit the read (`readFileSync` of a huge file blocks the extension host).
- `installHook` writes a hook file into the agent-writable repo; the agent can later edit or replace it (the instrument under the control of the object it verifies). Document it, or install in user-level config.

**G7. Env-missing misattribution turns a real regression into "your environment is missing a dependency".** `runner.py` computes `repo_local_names(repo)` on the HEAD worktree only.
- Repro: base has `core.py` and two passing tests importing `core`; the agent renames it to `core_v2.py`. Result: `UNKNOWN ... inconclusive: missing dependency in AgentMirror's environment: core (pass --python with the project's virtualenv ...)` and `baseline_*` are discarded; the correct result is CONTRADICTED (2 regressions). The same masks deleted packages. The opposite direction (a data dir named like a 3rd-party module, e.g. `yaml/`, hides a genuinely missing module; `repo_local_names` is shallow: top-level names plus `src`, `lib` only, and counts any directory) is by reading, not reproduced.
- Fix: a missing module that exists in the BASE tree (or appears in base passing ids / is imported by a test that passed at base) is a regression, not an env problem; also require the module not to be provided by `importlib.util.find_spec` in the base worktree.

**G8. `--setup auto` runs install/build code with network allowed and unrestricted reads.** `profile_with_network` is `(allow default)(deny file-write*)...` with no network denial and no read restriction; verified: the profile reads the signing key (32 bytes) and contains no `(deny network`. A malicious `setup.py`/build backend/requirements entry (`-r`, git URLs, `--index-url`) can read `~/.ssh`, `~/.aws`, the AgentMirror key and send it out. README advertises this path "for CI/servers". Also: the size watchdog counts only `venv` + `HOME/tmp`; writes to `HOME/.cache|.cargo|.rustup`, `/private/tmp`, `/private/var/folders` and the repo are uncounted (the "700 MB" guard can be exceeded by a build that downloads a toolchain into HOME), sparse files count by apparent size (false kills, fail-closed), polling is every 2 s.
- Fix: install only wheels (`--only-binary=:all:`) by default, deny reads outside venv/repo/stdlib, allow network only to the index host (proxy), count `home` and the repo in the watchdog; never run `-e` of the user's real repo (G1); document that `--setup auto` on an untrusted repo is not safe.

**G9. Platform: everything fails closed but the hook/Action cannot ever produce a test verdict off macOS.** With `sandbox-exec` absent (simulated by a PATH containing only git): CLI -> `agentmirror: tool error: FileNotFoundError ... sandbox-exec` (exit 3); hook -> `could not check this turn (FileNotFoundError...)`; `--setup auto` -> same after building the venv. No unsandboxed fallback exists (good: confirmed no path runs repo code without `sandbox-exec`), but there is no preflight or message that says "tests can only run on macOS", and the Action has no `--run-tests`, so on ubuntu a "tests pass" claim is only ever checked via CI. Code that runs outside the sandbox: `python -m venv`, all `git` calls (G4), `shutil.copy2` overlay. Fix: preflight `shutil.which("sandbox-exec")` with an explicit UNKNOWN reason; state in README that Linux has no sandbox support.

**G10. CI evidence is authored by the PR.** `ci.py` trusts any check named like a test job on the head SHA. A same-repo PR can add `.github/workflows/x.yml` with a job named `tests` that does `true`; `--ci` then reports SUPPORTED. (Fork PRs run the base workflows, but a same-repo agent branch does not.) Fix: if the change touches `.github/workflows/`, CI config, `tox.ini`, `noxfile.py`, `pyproject.toml` test config or `conftest.py`, downgrade CI-based SUPPORTED to NOT_CONTRADICTED/UNKNOWN with that reason; compare job names with the base commit's required checks.

### MINOR

**G11. GitHub Action comment handling.** `gh pr comment --edit-last` edits the last comment by the authenticated user, not the comment carrying `MARKER` (the marker is emitted but never searched for). With `GITHUB_TOKEN` this overwrites any other bot's last comment (stale bot, labeler); with a PAT passed as token it overwrites a human's comment. Fix: find the comment id by marker via `gh api repos/.../issues/$PR/comments --paginate` and PATCH it, else create. Other findings: no script injection found (all inputs via `env:`); `base` goes to `--base` after argparse (an option-like value is rejected, not executed); `uses: ...@main` in the example is an unpinned supply-chain edge (pin a SHA); `python -m pip install "${{ github.action_path }}"` interpolates a GitHub-controlled value, fine but prefer an env var; the example workflow is safe for `pull_request` but must warn never to switch to `pull_request_target` with `actions/checkout` of the head. Fork PRs: token read-only, comment step falls back to the job summary (correct). `--ci-sha` + the origin slug are acceptable inside Actions (F7 already lists the local-origin risk).

**G12. `_md` escaping is incomplete for GitHub.** Observed output of `_md`: `@everyone @octocat @org/team` unchanged (pings/notifies users and teams); `org/repo#9` -> `org/repo\#9` (GitHub's reference autolinker works on rendered text, so `\#` probably still links; unverified on GitHub); `:rocket:` `:tada:` unchanged (emoji shortcodes can imitate the status icons; `:white_check_mark:` is accidentally broken by the `_` escape); bare URLs get `\.` but may still autolink the prefix (unverified); U+202E bidi override, zero-width space and U+2066 pass through untouched; `$...$` math is not escaped. Newlines are collapsed (good), `<`, `|`, `` ` ``, `[`, `!` are escaped (good), so the `MARKER` cannot be spoofed from the body and no HTML or table break could be injected. Fix: insert a zero-width-free neutraliser for `@` (`@​` is itself invisible-character abuse; use backticks around code-ish text or `&#64;`), escape `:`, strip Cc/Cf categories (bidi, zero width), escape `$`, and cap the total comment size (65536 chars) across all findings.

**G13. Hook parsing and resource limits (`adapters.py`, `claims.py`, `cli.run_hook`).**
- Quadratic regex: a single "sentence" of `1,1,1,...` takes 0.07 s (4 KB), 0.26 s (8 KB), 1.03 s (16 KB) in `claims.extract` (about 4x per doubling, so ~16 s at 128 KB, beyond the hook's 60 s timeout near 256 KB); agent-controlled text (final message, PR body) can stall the hook/Action. Fix: cap input (`text[:20000]`) and per-sentence length before regexes, and make the digit-run patterns possessive/anchored.
- Deep nesting: 100 000 nested `[` -> `RecursionError` from `json.loads` (not caught by `except ValueError` in `final_message_from_text`); 700 levels parse but ~1000+ levels overflow `_texts`. In the hook the generic `except Exception` converts this to "Nothing was verified" (fail-closed, fine); in `--session` mode it is exit 3. Fix: catch RecursionError, iterate instead of recursing, cap line size.
- `transcript_path` is any readable file: `final_message` reads it fully (`fh.read()`; `/dev/zero` or a FIFO hangs/OOMs) and, for plain text, puts lines matching claim patterns into the report (repro: a file containing `... password=hunter2 tests pass` appeared verbatim in the `systemMessage`). Fix: `os.fstat` regular-file check, a 5 MB read cap, require the path under the harness's known transcript directory.
- `cwd` from the payload: any git repo on disk gets `.agentmirror/last` written into it (and clobbering via G3). A nested `role:assistant` dict anywhere in a line (for example structured tool output echoed in a user line) is treated as assistant text, so the "final message" can be attacker text from tool output; Claude Code's format is handled but the sniffing is generous.
- `run_hook` takes only `a.test_cmd[0]`, does not parse `name=`/`name@subdir=` specs (a `--test-cmd "tests=..."` would be executed as the literal word `tests=python`), and `.format` raises on braces.

**G14. Policy and `no_baseline` logic (`decision.py`, `runner.py`).**
- `no_baseline` is set whenever `baseline_passed` is empty. This includes "the agent added the whole test suite in this change" (greenfield) and "tests existed but none passed at base". Then `new_failing = 0` and `--new-test-failures review` is silently disabled exactly where it is most needed. Moreover `any(e.counts.get("no_baseline"))` zeroes `new_failing` for ALL suites when only one suite lacks a baseline.
- `attention` is raised from `uncomparable`, which also counts subTest/space-in-id mismatches (RISKS F9), so policy `review` can fire on a harmless parameterised test.
- A relative `--python` path (`../venv/bin/python`) fails inside the worktree (`sandbox-exec: execvp() ... No such file`) and is reported as an inconclusive run, not as a usage error. Resolve it to absolute before use.
- The tool leaves an untracked `.agentmirror/` (evidence, reports, home) in the user's repo: `git add -A` by the agent/user commits signed records and reports, so evidence ends up in PRs. Add `.agentmirror/` to `.git/info/exclude` on first write.
- `envsetup`: `pkill -9 -f <venv>/bin/pip` treats the path as a regex and prefix-matches (`.../bin/pip3`); a TMPDIR containing regex metacharacters makes it a no-op. The venv root comes from `mkdtemp`, so unrelated-process kills are unlikely; use the process group only (already done) and drop the pkill or `re.escape` it. Concurrent runs use distinct `mkdtemp` roots (no collision found). Venv paths with spaces are passed as argv (no shell) and a sandbox `subpath` string; a `"` in the path would break the profile quoting (escape it). `dir_size` does not follow directory symlinks on Python 3.13 (3.12 and earlier follow in `rglob("*")`? not tested) so a symlink loop hang was not reproduced.

### Over-claims to fix
1. vscode/README.md "by default nothing is executed" -> the extension executes `agentmirror.command` (G6) and `git` (G4).
2. README/vscode README "test running is disabled in untrusted workspaces" -> only `runTests` is; `command`, `python` and `testCommand` come from workspace settings.
3. README "Evidence integrity: ... stops casual forgery" is accurate, but the sandbox paragraph implies tests cannot tamper; G2 shows a sandboxed test can read the key.
4. README Action row "Shell step tested locally; the Action itself not run on GitHub" is honest; add that comment-editing may overwrite another bot's comment (G11).
5. README/vscode README "report webview has scripts and network disabled": true for scripts and fetches; form submission and base URL are not restricted (G6).
6. runner.py docstring "Evidence is bound to the commit and marked as produced by a separate tool" and `"network": "denied"` in the record: not true for G1 (code from another checkout) and for installs (G8).
7. `decision.py`/README "never blocks": true by exit code, but a hook that takes longer than its timeout (20 min extension timeout, 60 s hook timeout, `--run-tests` default) yields no message at all, silently.

### Priority
G1, G2, G3, G4, G6, G5, G7, G10, G8, then G9, G11-G14; add a regression test for each (src-layout editable, forged-evidence test, symlinked `.agentmirror`, hostile `.git/config`, renamed-module env_missing, workflow-touching PR, settings scope in `package.json`).


## Status of the integration-surface review findings (2026-10-07, after fixes)
Fixed with regression tests (`tests/test_security_fixes.py`, `vscode/test/helpers.test.js`): G1 (worktree isolation: PYTHONPATH + import-origin probe; installs from a copy and removes the project, never editable in the real repo); G2 (sandbox cannot read the signing key or credential stores, writes only inside the worktree; the first fix failed because the sandbox matches canonical paths, caught by its own test); G3 (symlink-safe writes); G4 (hardened git: no hooks/fsmonitor); G6 (machine-scoped settings, restrictedConfigurations, stricter CSP, sealed hook results verified by the extension); G7 (module that existed at base is not a "missing dependency"); G9 (explicit refusal without the sandbox); G10 (CI authority marked unknown, caveat in text); G11 (Action updates only its own marked comment); G12 (@mentions, emoji shortcodes, invisible characters); G13 (bounded input, depth cap).
Open: G5 residual (a fully privileged local agent can read the key and forge seals/evidence); G8 (installs have network and broad reads); G14 `no_baseline` also disables the `review` policy for greenfield suites; CI job-name heuristics; unrestricted reads apart from denied locations; no memory cap.
