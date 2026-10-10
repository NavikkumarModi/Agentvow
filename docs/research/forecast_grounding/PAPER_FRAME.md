# Paper frame, re-scoped to the measurements (2026-10-10)

Status: a framing document, not a draft. It states what the evidence supports, what it does not, and what a paper could honestly claim. Novelty is **a potential gap requiring further verification** (full-text comparison with 2610.00425, SetupBench, ResearchEnvBench, ProofRun and reproducible-trajectories is still open; the patent search is not done; see `../NOVELTY_BOUNDARY.md`).

## 1. The question, restated
When a coding agent says "the tests pass", **can an independent party obtain a determinate verdict on that claim, and what does it take?** Three execution contexts are compared on the same frozen patch: the agent's environment, a replay from the repository's own declarations, and a replay from a recipe the agent itself declares. No LLM sits in any verdict.

The earlier headline, "agent-declared recipes close a large accountability gap", is **withdrawn as a general claim**. It holds only where hidden state exists by design.

## 2. What was measured (all numbers from this repository's own studies)
| Study | Design | Result | What it supports |
|---|---|---|---|
| Detection v2 (140 PRs) | real agent PRs, 70 CI-failed + 70 controls | a usable independent run for 27/140 (19%, CI 14-27) | 19% of PRs reached a usable zero-config run: a property of this tool and its criterion (base suite has a passing test), not a claim-level rate (only 26 of the 140 had a real tests-pass claim; the two arms are not independent). Whether this is the bottleneck for a developer using their own environment is not shown |
| Pilot (12 designed tasks, 36 runs) | traps with environment state hidden from the repository | zero-config replay 42-50%; agent's recipe 75-83%; 19/20 expressible recipes sufficient | A recipe recovers claims whose truth depends on state outside the repository. **Designed to favour the recipe; not a rate** |
| Stage A (instrument validity) | 24 runs, ablation, determinism | determinism held, 0 validator escapes; recipe 23/24 vs zero-config 10/24 | The instrument is reliable on designed tasks |
| Red team (pre-fixed expectations) | adversarial recipes and agents | several bypasses found and fixed (env fallback, shadow install, symlinked prepare, option injection) | The replay path fails closed |
| **Stage B1 (real repositories, N = 32, feasibility)** | real merged agent PRs, S0-sandboxed Claude Code **in a fresh empty virtualenv (no ambient state by construction)**, S1 tasks selected because zero-config already reproduces | repository-only replay 31/32 (97%); recipe replay 24/30 (80%) registered, 26/30 after the validator fix (post-hoc); exact `pip freeze` 31/32. The comparison is **asymmetric**: repository-only and freeze replays run the researchers' target-file command, the recipe replay runs the agent's own (often whole-suite) command | **Not testable here whether recipes help**: the ceiling (31/32) is set by the selection filter, so "recipe adds 0" is guaranteed by construction. Only 1/32 claims (telegram#4908) was true but non-portable |
| S2 screening | 246 + 56 attempts, extended CI-derived recipes | S2 = 2 tasks; extending the extractor to tox/make/uv/poetry yielded 0 more | The CI-parsing route yielded 2 of ~300 attempts, in one pool (AIDev), with a conservative extractor (drops expression lines, ignores lockfiles, per-repository try cap: 56 of 151 re-attempted). **S2 prevalence in the wild is unmeasured**; S2 labels were also unstable across days (package drift) |

## 3. Claims the evidence supports (candidate contributions)
1. **A measurement design**: claim-level accountability across execution contexts on one frozen patch, with the support basis stated (`agent_recipe` versus repository-native). Potential gap requiring further verification; each part has neighbours.
2. **A reachability funnel on real agent PRs** for this tool: 19% reached a usable zero-config run; losses were mostly environment. (Detection v2; scoped as in the table.)
3. **A bounded feasibility finding**: on real repositories that were selected because zero-config replay already reproduces, with agents working in an empty environment, 31/32 passing claims were reproduced from the repository alone. This shows the instrument works on real repositories and that, **absent ambient state, the failure mode is rare**. It does **not** show that recipes add nothing in general, and it says nothing about the pilot's gap outside these conditions (no ambient state, no S2 tasks, selection ceiling).
4. **Where a recipe is needed is hard to sample**: the CI-parsing route to S2 tasks yielded 2 of ~300 attempts; this characterises that route, not the prevalence of S2 situations.
5. **Instrument lessons, reported as findings**: an honest declaration can be rejected by the verifier's vocabulary (4/4 generated-fixture recipes in the pilot; `PYTHONPATH` in 2/32 real runs); a declared test command broader than the claim produces false non-reproduction (up to 3/32, 2 confirmed by rescoping); a flattened `-e dir` silently installed an unrelated PyPI package in monorepo replays. Each is a way a replay-based verifier can mislead and was found only by running on real repositories.
6. **A fail-closed, deterministic replay instrument** with an adversarial test suite (open source, MIT). An artifact, not a research claim.

## 4. Claims the paper must NOT make
- That recipes "close the accountability gap" in general, or that the pilot's 42% to 83% is a rate.
- That agents omit dependencies, that declared and actual dependencies differ, or that necessity/padding can be measured: these appear to be covered by prior work (2610.00425, SetupBench, ResearchEnvBench; `[snippet]`/abstract level only, no full text read, so treat as withdrawn-until-checked).
- That recipes do not matter, or that "the pilot's gap does not generalise": B1 removed ambient state and filtered on zero-config success; it cannot show either.
- 28/30 or any figure that rescopes test commands after seeing failures as a headline; only 24/30 (registered) and 26/30 (validator fix only) are reportable, labelled as such.
- Anything about dishonest agents: in every study the agents' claims were true in their own environment and no agent edited protected tests.
- Anything about other model families (Claude only), larger tasks (median change 45 lines), or natural bug reports (reconstruction tasks).
- That the S1 numbers are a population rate: S1 is conditioned on zero-config already working. 8 of 32 claims were the injected sentence "All tests pass." and the target is the researchers' file set, so B1 reproduces *tests*, not agents' own wording.
- Novelty of any single component without the SOTA gate.

## 5. Structure that fits the evidence
1. Problem: a completion claim is true under conditions the reader cannot see; measured consequence is the 19% reachability.
2. Instrument: recipes with preconditions, fail-closed replay, support basis. (Short; the artifact is the contribution.)
3. Study 1, designed hidden state (pilot, Stage A): shows what a recipe can capture and the validity of the instrument. Labelled as an instrument test.
4. Study 2, real repositories (B1): the main empirical result, negative and bounded; post-hoc instrument analysis kept separate from the registered table.
5. Where recipes would matter and why it could not be tested (S2 scarcity; CI not expressible).
6. Threats, including the selection effect, one model family, one run per task, N = 32 (feasibility, no confirmatory inference).
7. Related work, after the full-text comparison; novelty stated only as "potential gap" until the gate passes.

## 5b. Threats the review added
- The replay puts `src` and the repository root on `PYTHONPATH` in every replay (`runner.py`), which can make imports succeed that a clean CI checkout would not resolve; this inflates reproduction and made haliax's `PYTHONPATH` look unnecessary.
- Two jaseci recipes replay a single test (`-k`/`::`), not the claimed target file; they count as passes under the B1 definition.
- Only the 8 failing recipes were re-replayed after the instrument fixes; the 24 passes were not re-run.
- The shadow-name guard normalises `_` and `-` but, per the reviewer, not `.` (unverified).

## 6. Venue fit and what it would take to strengthen it
- As it stands: a **measurement / negative-result paper plus an artifact**, suited to a workshop or an MSR-style data/tool track; not to a venue wanting a positive method result.
- **Cheapest experiment that could falsify the frame** (adversarial review): re-run a subset of B1 tasks with the agent in a *preloaded ambient* environment, no zero-config filter, and one scoped target command for all three contexts (~$15, no new tooling). If repository-only replay falls well below 97% the "small gap" reading collapses; if it holds, the finding becomes defensible.
- To reach a stronger claim, one of: (a) a stratum with real hidden state at N >= 40 (needs a source other than CI parsing, for example agent-authored recipes validated against truth on repositories chosen without the zero-config filter); (b) a second model family; (c) natural bug reports instead of reconstruction tasks. Each costs real money or time and is a decision for the project owner.

## 7. Open items before any draft
Full-text read of 2610.00425, SetupBench and ResearchEnvBench; the patent search; the cause of the one non-portable case (`telegram#4908`); the adversarial review has been run (below); its verdict was *not defensible as written*, and the corrections above were applied.

## 8. Adversarial review, 2026-10-10 (independent subagent, read-only)
Verdict: **not defensible as written**; defensible after the edits above as a feasibility and instrument paper whose central question (do recipes help where hidden state exists in real repositories?) is explicitly untested. Blocking: (1) "recipe adds 0" was a ceiling effect of the S1 filter; (2) B1 removed ambient state by design. Major: asymmetric contexts, post-hoc 28/30, S2 and reachability overstated. Minor: injected claim sentence, unsupported literature assertion, novelty wording. Instrument: no false SUPPORTED found in the 24 passes; sync/tox/make translation touched only S2 screening (0 tasks). The numbers themselves reproduced from raw data; the detail of the jaseci single-test recipes and the `.` normalisation are the reviewer's observations, not yet re-checked by me.
