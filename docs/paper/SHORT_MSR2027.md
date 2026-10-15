# Can an Agent's Passing Test Result Be Reproduced? A Feasibility Study of Attempt-Time Dependency Capture

*Short work-in-progress paper draft for MSR 2027 (4 pages plus 1 of references, IEEE template, double-anonymous). Written 2026-10-15 from `DRAFT.md` (v2, after adversarial review). Every number is from the repository's studies. Anonymisation checklist at the end must be completed before submission: the tool and repository names below are placeholders.*

## Abstract
An agent's statement "the tests pass" is true in the environment it ran in; whether a reader can reproduce it is a separate question. On 40 randomly drawn agent-authored pull-request tasks (pre-registered study B6; one Claude Code model, Python only), 22 runs were valid (the agent's target tests pass and fail without its changes). Replaying the agent's `pip freeze`, captured at the moment it ran its tests, in a clean sandbox reproduced 20 of the 22 passing results (91%, 95% CI 72-97), against 12 (55%, 35-73) for a zero-config reconstruction from the repository; capture alone reproduced 8 and reconstruction alone 0 (paired difference 36 points, 95% interval 15-55; exact sign test p = 0.008). Of the reconstruction's 10 misses, 7 were UNKNOWN because it found no dependencies to install, 1 produced no result, 1 was a credential skip, and 1 was a real test failure. The comparison is weak by design: the reconstruction is a heuristic, and capture replays the environment where the tests already passed, so we read it as an upper bound on replayability, not as a verification method. The study meets its pre-registered rule at the minimum power boundary (22 valid runs against a floor of 20) and is the fourth capture study, after three inconclusive or underpowered ones. It shows no case in which replay changed a verdict. We report the limits and the instrument defect that only real repositories exposed.

## 1. Introduction
Coding agents report that tests pass. Whether anyone else can reproduce that depends on state a reader cannot see: installed packages, environment variables, generated files. Prior work measures whether agents can build environments (SetupBench [1]), whether an agent's self-reported capabilities survive hidden probes (ResearchEnvBench [2]), and whether an agent's declared dependencies match a runtime trace (Vangala and Malik [3]). Tools that bind an agent's claim to a recorded run exist (truth, ProofRun, Proofrail, Trial; Section 5). We claim no new verification mechanism. The question here is empirical and narrow: **on real agent-authored pull requests, does recording the agent's Python dependency state when it runs its tests make its passing result reproducible more often than reconstructing the environment from the repository?** One possible gap, not verified against all prior work, is this measurement on a frozen patch with several replay contexts compared.

## 2. Method
**Task and contexts.** For each task the agent's patch is frozen. The same scoped target command (the tests the agent claims) is replayed in a clean sandbox (macOS `sandbox-exec` or Linux bubblewrap, network off for tests) under three environments: (i) *reconstruction*, a zero-config ladder (`pip install .[test|dev|...]`, a fixed list of requirements files, dependency groups, plus pytest); (ii) a *recipe* the agent writes, validated against a closed vocabulary; (iii) *capture*: the agent's `pip freeze` after its run, with `pip` dropped, `setuptools` and `wheel` kept, editable and direct-URL entries dropped and the project's own distribution removed. No language model decides any result; a result is pass, fail or UNKNOWN, and UNKNOWN is never converted into a pass.
**Sample and rule (pre-registered).** 40 tasks drawn at random from 747 structural candidates (agent-authored PRs with Python tests, fixed filter on the AIDev dataset) not used in earlier stages, at most two per repository (31 repositories). Claude Code ran each in an empty environment. A run is *valid* if the agent's target tests pass in its own environment and fail on the baseline without its changes. Rule fixed before the run: supported if capture >= 70% of valid runs and the net paired lead over reconstruction >= 15 points; underpowered if fewer than 20 valid runs. The 15-point threshold was set after earlier stages and before B6 data.
**Funnel.** 40 attempted, 1 setup failure, 39 ran, 30 with the agent's tests passing, 8 trivial (tests pass without the change), **22 valid** (19 repositories; 21 from PRs authored by one agent family).

## 3. Results
| outcome on 22 valid runs | count |
|---|---|
| both reproduced | 12 |
| capture only | 8 |
| reconstruction only | 0 |
| neither | 2 |

| context | reproduced / valid | 95% CI | / all 40 attempted |
|---|---|---|---|
| reconstruction | 12/22 = 55% | 35-73 | 17 |
| **capture** | **20/22 = 91%** | 72-97 | 26 |
| agent recipe (scoped) | 17/22 = 77% | 57-90 | 23 |

The registered rule is met (capture 91% >= 70%; lead 36 >= 15 points), at the minimum power boundary. The Newcombe interval for the paired difference is 15-55, so its lower bound equals the threshold. Intention-to-treat counts over all 40 attempted tasks point the same way (26 against 17).
**Why reconstruction misses.** 7 UNKNOWN because the ladder found no dependencies to install (a manifest-less repository), 1 with no ladder result, 1 credential skip (also missed by capture), 1 real failure (3 failing tests). The headline gap is therefore mostly a statement about a weak zero-config comparator.
**The two capture misses.** One repository whose importable package is not at its root, after capture removed the project's own distribution (a design limit); one test suite that skips without an API key (a credential outside the captured packages).
**Post-hoc checks (not part of the rule).** Requiring one executed passing test changes one reconstruction result (a pass with only skipped tests), giving 11/22 and a net lead of 41 points. The 8 capture-only runs lie in 8 different repositories; a repository-level cluster bootstrap (19 repositories) gives a net-lead interval of 18-65 points. Both are descriptive.
**Skipped passes and path leniency.** Among passing results, reconstruction has 1 of 12 with zero passed tests, capture 1 of 20 with some skipped tests alongside passes. The replay puts the repository root and `src` on the import path in every arm; the effect of this leniency was not measured (2 of the 20 capture passes touch files under `src/`).

## 4. Development history and an instrument defect
Capture was first tested in three earlier studies on tasks selected because reconstruction had failed: 5/11 against 0/11 (inconclusive against the registered bar); 5/8 against 2/8 (below the registered minimum of 10 valid runs); 9/18 against 3/18 (inconclusive). After the third, five capture failures reported a "missing dependency" although the package was pinned in the captured list. The cause was the tool's own 700 MB environment-size guard killing the install, after which tests ran in a partial environment; the message is now "environment could not be built". Raising the limit to 3 GB recovered 4 of the 5 (post-hoc). A fixed resource limit that silently converts build failures into dependency verdicts is a general risk for replay-based verification. The capture design changed between stages, which is why B6 was run on fresh tasks with a frozen protocol; readers should still weigh it as the fourth study.

## 5. Related work
*(Each item read in full from its PDF or README on 2026-10-15; README descriptions are the authors' own.)* SetupBench [1] (93 tasks; success is a validation command run after the agent's last action; no check of the agent's completion claim) and ResearchEnvBench [2] (44 repositories; a hallucination metric compares self-reported success with hidden probes) establish auditing a self-report against an independent probe. Vangala and Malik [3] (3 agents, 4 languages, 50 tasks) audit an agent's declared dependencies against a runtime trace and call never-loaded declared packages overclaimed; they do not audit a passing-test claim. Tools that bind a claim to a recorded run: truth (a language model parses the claim, fixed rules decide, a "tests pass" claim needs a recorded run, it never runs the command itself), ProofRun (runs the check in the agent's environment and binds it to a code-state hash, reports stale on change), Proofrail (checks claims against a commit range) and Trial (a rules-file convention). As described in their READMEs, none re-executes the result in a separate clean environment and compares contexts; this is an absence claim from README text, and our searches may have missed work. Patents on hashed test environments and environment fingerprints exist (US11379349B2, CN120780274A) and are not reviewed by counsel.

## 6. Threats and limits
One model, one run per task, Python only, small repositories (many hobby projects; the two capture misses are the two with real infrastructure), valid runs conditioned on the agent's success (21 of 22 from one PR-author family). Capture is taken from the claimant's own environment, so "independent" means independent of the sandbox, not of the claimant. All replays ran on one macOS host on the same day with live package indexes (yanked or platform-specific wheels may break a pinned capture later). The target tests are the verified object, not the agent's sentence. No run shows replay changing a verdict or catching a false claim, and no deceptive agent was studied. Reproduction is not correctness.

## 7. Conclusion
For a random sample of real agent PRs, the agent's recorded Python packages reproduced 91% of valid passing results in a clean sandbox, against 55% for a weak zero-config reconstruction. This supports only that the agent's environment is usually replayable and that the repository alone often does not say how. The missing evidence for a full study is a strong reconstruction baseline (CI and Dockerfile parsing), 50 or more valid runs across agents and PR-author families, replay weeks later and on Linux, and a case where replay changes a decision.

## Data and tool availability
Task identifiers, prompts, analysis scripts and the open-source replay tool are available at an anonymised URL; model outputs and environment snapshots are not released. The CLI version and exact model ID per run were not recorded, a reproducibility gap.

## References (to format)
[1] A. Arora, J. Jang, R. Zilouchian Moghaddam, SetupBench, arXiv:2507.09063. [2] Y. Wang et al., ResearchEnvBench, arXiv:2603.06739. [3] B. P. Vangala, T. Malik, Code That Works, Environments That Don't, arXiv:2610.00425.

## Before submission (not done)
1. Venue fit decided by the owner: MSR 2027 technical papers, short work-in-progress track (official page: abstract due 20 Oct 2026 and paper 23 Oct 2026 AoE, 4 pages plus 1 of references, IEEE template, double-anonymous). Verify against the live call.
2. Anonymise: remove the tool name, repository URL, author-identifying text from the artifact and from third-person citations of the owner's own prior work; the public GitHub repository carries the author's name.
3. Convert to the IEEE LaTeX template and fit 4 pages (drop section 4 detail or the recipe row if needed).
4. Owner reads and approves every claim; no submission is made by the assistant.
