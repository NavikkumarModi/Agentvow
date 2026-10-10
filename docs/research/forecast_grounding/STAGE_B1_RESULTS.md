# Stage B1 (feasibility) — results, 2026-10-10

Protocol: `STAGE_B.md` (sections 0-11). **32 valid tasks (< 40): this is a feasibility result with no confirmatory inference.** Real merged agent PRs from 22 repositories re-posed as tasks (repository at the PR's base commit plus the PR's test files, no git history or remote), the agent (Claude Code, installed default model) run **under the S0 macOS sandbox** in a fresh empty virtualenv with prompt C1P (recipe requested, `prepare` mentioned), one run per task, **$13.30 in total ($0.42 per run)**, no agent errors, no run touched anything outside its task. Raw data and saved patches stay local (`data/preconditions/`; third-party code).

## What happened
- In **all 32 runs the target tests passed in the agent's own environment**; no agent edited the tests it was given; all 32 wrote a recipe; 24 of 32 final messages contained a tests-pass claim the extractor recognised (for the other 8 the fixed sentence "All tests pass." was used).
- Reproduction of the agent's result (target tests pass) in clean contexts, **same frozen patch**:

| context | reproduces | by stratum |
|---|---|---|
| repository-only replay (zero-config) | **31/32 = 97%** [84, 99] | S1 29/30, S2 2/2 |
| agent's recipe replay | 24/30 = 80% [63, 90] (2 recipes rejected before replay) | S1 24/30, S2 0/2 |
| agent's exact `pip freeze` (control) | 31/32 = 97% [84, 99] | S1 29/30, S2 2/2 |

- **Paired comparison (descriptive): recipe-only reproduces 0 runs, repository-only reproduces 7 runs where the recipe did not, both 24.** The pre-registered hypothesis H1 (recipe replay reproduces more than repository-only replay) is **not supported** on these tasks, and the pilot's large gap did **not** generalise to real repositories of this kind.
- Recipe replay determinism: 30/30 twice-identical.

## Why the 8 recipe replays did not reproduce (classified by hand from the saved records)
- **Instrument vocabulary (2, both S2 haliax tasks):** the agent declared `PYTHONPATH=tests:src:.`, which the recipe validator rejects by design; the repository-only replay passed without it, so the declaration was unnecessary as well as inexpressible.
- **Instrument limitation (2, jaseci):** the recipe installs a sub-package (`pip install -e jac`) in a monorepo; the isolation guard (fail-closed) refuses because the project copy is installed under a different distribution name than the one the cleanup step removes. Repository-only and freeze replays passed.
- **Declared test command broader than the claim (3):** the recipe ran the whole suite (`python -m pytest`, `pytest -q`); unrelated tests failed in the clean replay (26, 1 and 2 failures) while the target tests pass in every other context. These are scope mismatches between what was replayed and what was claimed, not missing preconditions; the verdict was UNKNOWN (no false CONTRADICTED).
- **True but non-portable (1, python-telegram-bot#4908):** the target tests pass in the agent's environment but fail identically in **all three** clean contexts, including the exact `pip freeze`: the claim depends on state outside the declared packages (cause not identified). This is the only run that looks like the hidden-state phenomenon, 1 of 32.

## Reading it honestly
- **Selection effect, important:** S1 tasks were selected *because* the zero-config ladder already reproduced the PR's own head tests. That makes repository-only replay likely to succeed on a similar patch by construction, so 97% is an upper-bound-flavoured number for repositories whose setup is declarable, not a general rate. The earlier detection study (140 PRs, 19% reaching a usable run) shows the general rate is much lower; this study conditions on reachability.
- **S2 (setup knowledge outside the repository's declarations), the stratum where recipes should matter, has 2 tasks** and cannot support a conclusion. Even there repository-only replay passed in this run although zero-config had failed for those PRs at validation time: the S2 label was not stable across environment builds on different days (package resolution drift), a measurement problem in itself.
- **The pilot's designed traps overstated the effect for realistic repositories.** The pilot remains valid as an instrument test (it showed what a recipe can capture when hidden state exists); it should not be quoted as a rate.
- **What the recipe adds, empirically, on real tasks:** nothing in reproduction, and some friction (4 of 8 failures are instrument limits, 3 are test-scope mismatches). What it may still add (not tested here): a stated, checkable list of preconditions for claims whose environment is not declarable.
- Hidden-state measures: the session audit found any undeclared environment/install in 8 of 32 runs; the "ambient import" measure remains noisy on real repositories (transitive dependencies) and is not used for conclusions.
- Limits: one model, one run per task, 32 tasks in 22 repositories (25 Codex-authored PRs, 7 Copilot), reconstruction tasks (not natural bug reports), tasks chosen by our own tooling's reachability, small median change (45 lines); models may have seen these public repositories.

## What this changes
1. **The central research claim must be re-scoped**: "agent-declared recipes close a large accountability gap" is supported only for designed hidden-state tasks. For real repositories with declarable setup the gap is small (about 3% non-reproducible, 1 case).
2. **A defensible, narrower contribution remains:** (a) a measured rate of locally-true-but-non-portable claims on real PRs (1/32 here, on declarable repositories), (b) the reachability funnel (19% of real PRs reach a usable run), (c) a validated, adversarially tested replay instrument with an explicit support basis. Whether any of this is novel is unestablished.
3. **Instrument fixes suggested by the failures (not yet made):** recognise sub-package installs in monorepos and clean them up before the isolation check; replay the *claimed* tests (or report the broader command's failures against a baseline) when a recipe's test command is broader than the claim; tell the agent that `PYTHONPATH` is not accepted.
4. **S2 needs a different route** (extend the CI-derived recipe vocabulary to tox/make/uv/poetry, or find repositories where CI is the only setup record); until then the question "does a recipe help where it should?" is open for real repositories.

## Addendum (2026-10-10, POST-HOC): instrument fixes and a re-replay of the non-reproducing recipes
Written after seeing the B1 results; the fixes and this analysis are not part of the protocol, and the table in the first section stays as the registered result.
**Fixes made:** (1) `pip install -e <dir>` was flattened to the bare name, which pip reads as a PyPI package: for the jaseci monorepo the replay installed an unrelated PyPI package called `jac` (a real validator bug; now a path `./dir`); every distribution installed from the project copy is now removed after setup and a monorepo sub-package's source folder stays importable from each worktree. (2) When a declared test command runs more than the claim covers, Agentvow reports the tests the change added or changed (NOT_CONTRADICTED, never SUPPORTED); this rule did not apply to B1 because B1's target tests are already in the base commit. (3) Agent guidance and the validator message now say that `PYTHONPATH`/`PATH` and tool-configuration variables are not accepted and that the repository's own source folders are already importable.
**Re-replay from the saved patch and recipe (no agent), 8 runs whose recipe replay had not reproduced:**

| run | before | after the fixes | with the test command scoped to the claimed tests |
|---|---|---|---|
| jaseci #1897, #1992 | inconclusive (isolation failure) | **pass** (SUPPORTED) | pass |
| ComfyUI-Lora-Manager #487 | fail (whole suite; unrelated failures) | fail | **pass** |
| b2500-meter #135 | fail (whole suite) | fail | **pass** |
| python-telegram-bot #4908 | fail (also fails in repository-only and freeze contexts) | fail | fail |
| haliax #206, #208 | recipe rejected (`PYTHONPATH`) | still rejected (by design; guidance added) | not replayable |
| extending-move #375 | fail (whole suite) | not reconstructable (the agent created a file the saved patch lacks) | not reconstructed |

**Reading:** of the 30 accepted recipes, 24 reproduced as run; **2 more reproduce after the validator fix (26/30)**, and **2 more have a sufficient setup and a broader-than-claimed test command (28/30 on a setup-sufficiency reading)**. The remaining non-reproduction are one unreconstructable run and one genuine true-but-non-portable claim (`telegram#4908`), plus 2 rejected recipes. This does not change the main conclusion: **on real, declarable repositories the repository's own declarations already reproduced 97% and the recipe added no reproduction beyond them**; what the follow-up shows is that most of the recipe replay's apparent shortfall was the instrument and the scope of the declared test command, not missing knowledge by the agent.

**Correction after adversarial review (2026-10-10):** the "28/30 on a setup-sufficiency reading" figure rescopes test commands after seeing failures and is withdrawn as a headline; report 24/30 (registered) and 26/30 (validator fix only). The statement that the recipe "added no reproduction" is a ceiling effect of the S1 selection filter and an empty-environment agent run, not evidence that recipes do not help. See `PAPER_FRAME.md` section 8.
