# Forecast grounding — literature check and proposed paper (2026-10-09)

Status labels: **[read-abs]** = abstract/page fetched; **[snippet]** = search-result summary only. Nothing here is a novelty claim; the gate in `../NOVELTY_BOUNDARY.md` is still open.

## 1. The six sources cited by the external proposal — checked
| Cited as | What it is [read-abs] | Does it do "forecast consequences, then verify, with counterfactual pairs"? |
|---|---|---|
| Fail-Fast, Restart-Smart (2608.03222; Wang…Lo, 2026-08) | External 0.6B monitor predicts a SWE-agent run's failure from the visible trajectory prefix; saves 14.6–20.4% tokens at 5% FPR on SWE-bench Verified; transfers across policies. | No: external monitor, task-level failure, no agent-stated forecast, no counterfactual pairs. |
| Look Before You Leap (2609.11957; Althoubi, 2026-08) | Deterministic pre-action verification of shell commands (95.8% invalid caught at 10% FPR) and of edit-application formats. | No: checks the action against a fixed correct effect, not against the agent's forecast. |
| EnvTrustBench (2605.08828; Sheng, Wang, Zhou) | Generated environments + oracle; agents accept stale/incorrect/malicious environment evidence ("evidence-grounding defects"); 55 cases, 6 backbones, 5 scaffolds. | No forecasting; paired clean/perturbed design not stated in the abstract (full paper not read). |
| Verify Before You Commit (ACL 2026; Yuan et al.) | SAVeR: audits the agent's internal belief states before action commitment; six general benchmarks. | No: general reasoning, not external code consequences. |
| NCP-Bench (ICML 2026, narrative commitments) | **Not fetched**; cited by the proposal as long-horizon commitment consistency. | Unverified; appears unrelated to code. |
| Agentvow October 7 review "critical false-safe paths" | Our own RISKS.md. | **Already fixed** in later rounds (evidence/seal signing, key unreadable in the sandbox, sealed verdict channel, symlinks, parse crashes). Still open and documented: a hostile repository's own test code can fake test output; a fully privileged local agent can read the key. |

## 2. Closer prior art the external proposal did not mention (found now)
- **"Towards Evaluation of Implicit Software World Models in Coding LLMs" (2606.27406)** [read-abs]: a model reads code + a test and predicts the test outcome, exception class, memory, time and profiler output on 435 SWE-bench Verified tests; recall of failures is low (bias to predict "pass"); predictions are **not** made by an agent about its own edit and there are **no counterfactual pairs**. Closest neighbour.
- SURGE (surrogate code execution), ThrowBench (predict runtime exceptions, F1 19–38%), CoverageEval (line/branch coverage prediction) [snippet]: model-reads-code prediction tasks, isolated programs.
- **Agent Retrieval Bench `edit2ripple` (2607.24882)** [snippet]: identify files affected by an anchored edit (retrieval over a frozen snapshot).
- **SWE-Touch (2608.02499)** [snippet; numbers from a secondary blog]: counter-edits injected mid-task lower resolve rate by 7.7 points: an intervention benchmark of robustness, not forecasting.
- Executable Counterfactuals (2510.01539) [snippet]: causal-reasoning accuracy drops 25–40% from interventional to counterfactual questions on toy programs.
- Security-calibration study of verbalised confidence in generated code [snippet]: strong overconfidence at repository level.
- Selective-labels / abstaining-classifier evaluation: Chen, Li & Mao (ICML 2025); "Counterfactually Comparing Abstaining Classifiers" (NeurIPS 2023); labeling-induced abstentions (NeurIPS 2021); HALLMARK citation-verifier study [snippet]: scoring only committed decisions is biased unless abstention is random.
- Automated environment setup: Repo2Run (86% on its own benchmark; 44.8% under another metric), Installamatic, EnvBench, ExecutionAgent, RAT [snippet]: reachability of repositories is itself an active research area.

**Potential gap requiring further verification:** an *agent's own* pre-action forecasts of repository consequences, scored against execution-verified labels on **matched counterfactual repository pairs with identical task wording** (plus placebo pairs). Not found in this limited search.

## 3. Candidate papers (novelty and feasibility, honestly)
| # | Idea | Why it might be new | Weakness |
|---|---|---|---|
| A | **Counterfactual forecast test**: do a model's/agent's forecasts track the repository state or only the wording? (recommended) | Interventional pair design isolating repository-dependence; execution-verified labels with no LLM in labelling; flip-sensitivity and placebo-invariance metrics. Nearest work predicts on unpaired real tests. | Needs many model calls; only Claude models are reachable from this setup (a limitation to state); synthetic pairs risk low realism. |
| B | Abstention-aware evaluation of claim verifiers | Our own data show 81% of PRs never reach a usable run, so naive recall on the runnable subset is biased; bounds/weighting + semi-synthetic validation. | Statistical machinery exists (selective labels); contribution is application and a dataset. |
| C | Claim-scope ambiguity ("tests pass" = all / new / no-regression) | 7 of 11 CI-failing usable PRs fail the same tests at base: verdicts depend on the reading. | Mostly an annotation/NLP study. |
| D | Environment drift as a source of false agent claims | Our foamlib#453 false alert: results flip with dependency versions. | Needs an environment-building system at scale (reachability 19%). |
| E | Calibrated claim probabilities scored by an abstaining oracle | Combines B with elicitation in the hook. | Confidence elicitation is well studied; novelty in the oracle only. |

**Recommendation: A as the paper, with B as its external-validity section** (real agent PRs scored with abstention-aware bounds). A answers "is the agent's reasoning grounded in the repository?" with a falsifiable interventional test; B keeps it honest about what the instrument cannot see.

## 4. Design sketch of paper A: "Same Words, Different Repository"
**Question.** When the task text is held fixed and one causally relevant repository fact is changed, does a model's forecast of the consequences change in the correct direction (and stay put under irrelevant changes)?

**Units.** A *pair* = two small Python repositories identical except for one intervention, plus one fixed change description (a patch or an instruction). Intervention types: (1) add/remove a downstream consumer of the changed function; (2) make a signature change breaking/compatible for a caller; (3) add/remove a test that reaches the changed code; (4) delete/skip an existing test; (5) **placebo**: comment, whitespace, unrelated file. Generated by AST-level templates over seed repositories (and small real repositories for realism).

**Oracle (no LLM).** Execute tests at base and head in the Agentvow sandbox; static API diff; import graph; test inventory diff. Labels: tests-regress yes/no, which tests, API-break yes/no, impacted modules, tests-removed yes/no.

**Forecast.** Structured JSON before the edit is applied: predicted regressions (with probabilities), broken API, impacted modules, test-integrity risk, "unknown" allowed with a scoring penalty rule fixed in advance.

**Arms.** (i) wording-only (no repo access), (ii) read-the-repo (snapshot in context), (iii) tool-using agent (can grep/read/run but not execute the change), (iv) trivial baselines (always-uncertain; lexical risk model; base-rate). Models: Claude family reachable here; additional families only if API access is provided.

**Metrics.** Flip accuracy (forecast moves correctly across the pair), placebo invariance, Brier/calibration, discrimination (AUC), false-safe rate, coverage vs abstention, selective-risk curves. Pair-level clustering; bootstrap over pairs.

**Pilot.** About 30 pair types x 3 seeds = 90 pairs, 2-3 models, 3 repeats: verifies the generator, the oracle labels (hand-audited sample) and that the intervention really flips the label. Main study sized from pilot variance.

**Hypotheses (pre-registered later).** H1: read-the-repo forecasts beat wording-only on flip accuracy. H2: tool-using beats read-the-repo only for dependency-type interventions. H3: placebo invariance is high but not perfect. H4 (exploratory): forecast-vs-oracle divergence predicts a later false completion claim better than patch size/retry features.

**Threats.** Synthetic realism; label noise from flaky tests (run twice, keep deterministic); prompt sensitivity; model contamination of seed repositories; Claude-only coverage; forecasting prompts may change agent behaviour (ordering effects: forecast-then-edit vs edit-only controlled).

## 5. Steps and what exists today
1. Build the pair generator and run the oracle on 5 hand-made pairs (no model calls). Reuse: sandbox runner, API diff, import graph, per-turn change tracking.
2. Audit labels by hand; test that each intervention flips exactly the intended label.
3. Dry-run forecasting with one model on 10 pairs; check parsing, cost, baselines.
4. Pre-register (as `DETECTION_V2_PREREG.md` did), then run the pilot.
5. External-validity section on real agent PRs using the abstention-aware bounds (paper B), reusing the 140-PR dataset.
