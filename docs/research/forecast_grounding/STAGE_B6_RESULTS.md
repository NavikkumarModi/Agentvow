# Stage B6 (final registered test of attempt-time capture, unfiltered cohort) — results, 2026-10-12

Pre-registration: `STAGE_B6_PREREG.md` (committed before the run; one deviation, the disk stop, logged there including the interim look). All 40 planned tasks were attempted ($26.23 of the $30 cap), drawn at random from 747 structural candidates **without reading any earlier reconstruction result**, 31 repositories, Claude Code under the S0 sandbox, empty virtualenv, one run per task. Replay size limit 3 GB in every replay subprocess. Raw data stay local.

## Denominators (nothing excluded because capture failed)
| | count |
|---|---|
| A: attempted | 40 |
| setup failures (clone or base commit unavailable) | 1 (extending-move#252) |
| runs | 39 (5 agent errors) |
| P: agent's target tests pass in its own environment | 30 |
| trivial (target tests also pass without the changes) | 8 |
| not solved | 9 |
| **V: valid (P and non-trivial)** | **22** (19 repositories) |

## Result (on V; same scoped target command in every context)
| context | reproduced / V | 95% CI | / P | / A (intention to treat) | outcomes on V |
|---|---|---|---|---|---|
| E_repo: zero-config reconstruction | 12/22 = 55% | 35-73 | 16/30 | 17/40 | 12 pass, 8 inconclusive, 1 fail, 1 not run |
| **E_capture: the fuller capture** | **20/22 = 91%** | 72-97 | 25/30 | 26/40 | 20 pass, 2 inconclusive |
| E_recipe, scoped | 17/22 = 77% | 57-90 | 21/30 | 23/40 | 17 pass, 5 rejected before replay |
Paired on V: both reproduce 12; **capture-only 8; repository-only 0**; neither 2. Net paired lead (b - c)/V = **+36 points**.

## Pre-registered reading: **SUPPORTED**
The rule required R_c >= 70% and a net paired lead >= 15 points (and V >= 20). R_c = 91%, lead = +36 points, V = 22. The "no incremental value" condition (R_c <= R_r + 10, or lead < 10) was not met.

## The two capture misses (distinct classes, from saved summaries)
- localstack#12976: "missing dependency: localstack": the capture drops the project's own distribution, and this repository's importable package does not sit at the repository root, so the project was not importable; a capture-design limit (not examined further).
- instructor#1667: tests skipped because `GOOGLE_API_KEY` is not set: the agent's result depended on a credential outside the captured packages; capture cannot and should not carry secrets.
Recipe: 5 of the 22 valid runs had a recipe rejected by the validator (a `prepare` form, `--ignore-requires-python`, a declared `GOOGLE_API_KEY`, a declared `HOME`, `PYTHONPATH`): the same vocabulary friction as B1-B5.

## Interim look and consistency
After the disk stop (21 of 40 attempts) the interim figures were 13 valid, capture 11/13, repository-only 6/13 (logged in the pre-registration before the run resumed; the plan was not changed by them). Final: V = 22, capture 20/22, repository-only 12/22. The 19 later tasks added 9 valid runs, of which capture reproduced 9 and repository-only 6.
Across the registered stages: B3 (simple capture, filtered cohort) inconclusive 5/11; B4 underpowered 5/8; B5 inconclusive 9/18 (post-hoc 13/18 once the replay size guard was raised); **B6 (repaired capture, 3 GB limit, unfiltered cohort) supported 20/22**.

## What this does and does not show
- **Shows:** for a random sample of real agent-PR tasks, recording the agent's installed Python packages and replaying them in a clean sandbox independently reproduced 91% of valid passing results, against 55% for reconstructing the environment from the repository; no result was reproduced by reconstruction that capture missed. Capture also exceeded the agent's own declared recipe (77%), mostly because the validator rejects some honest recipes.
- **Does not show:** that the reproduced results are correct (reproducibility is not correctness: the replay reproduces the agent's own passing run, with its dependency pins), nor anything for system packages, services, generated files or secrets (the two misses touch the last two), other model families, large changes (median small), natural bug reports, or other languages. Capture replays the agent's own environment, so it says what the agent's environment did, not that the repository is self-sufficient.
- Limits: V = 22 of 40 attempts (more than half of the attempts are lost to agent errors, unsolved or trivial tasks); 21 of 22 valid runs come from PRs authored by one agent family (OpenAI Codex), although our runs use Claude Code; one run per task; reconstruction tasks; third-party code stays local; the comparator E_repo is the zero-config heuristic ladder, not every possible reconstruction.
- Meaning under the pre-registered consequence: supported, so an evidence-carrying execution capsule (source state, test invocation, Python environment, configuration at claim time) is a justified next investment; system-level state and secrets are the first things a fuller capsule must address.

## Robustness analyses (post-hoc, 2026-10-14; `research/preconditions/analyze_stageb6_robustness.py`; not part of the registered rule)
- **Executed-test requirement.** A reproduction must have at least one executed passing test. One repository-context "pass" (`vehicle_speed_estimation#7`) had 3 tests skipped and none passed; with the requirement, reconstruction is 11/22 (50%, CI 31-69), capture-only runs 9, reconstruction-only 0, net lead 41 points; capture is unchanged at 20/22.
- **Repository clustering.** The 22 valid runs come from 19 repositories (three with 2 runs). The 8 capture-only runs of the registered analysis lie in 8 different repositories; 8 repositories show a net capture advantage and none a net reconstruction advantage. A repository-level bootstrap (20,000 resamples of the 19 repositories, seed fixed): capture rate 95% interval 76-100%, reconstruction 26-73%, net lead 18-65 points, no resample with a lead at or below zero. Leave-one-repository-out: capture 90-95%, net lead 35-45 points (smallest without `joewandy/hlda`, which has two capture-only runs).
- **Reading.** The registered result is not driven by a single repository or by the all-skipped run. What these do not address: one model, one PR author family (21 of 22 valid PRs were authored by OpenAI Codex, the runs by Claude Code), small N, Python packages only.
