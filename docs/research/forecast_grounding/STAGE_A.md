# Stage A — instrument validity (protocol, written 2026-10-09 BEFORE the runs)

Purpose: before scaling to real repositories and more models, show that the measuring instrument (recipe validator, sandboxed replay, audit, ablation) is reliable and that every verdict can be reproduced from saved artifacts. This stage makes **no claim about agents**; it estimates nothing for publication beyond instrument properties.

## Runs
The same 12 verified tasks, **prompt C1P** (recipe requested, `prepare` field mentioned; the instruction that matches the extended instrument), **2 repetitions each = 24 agent runs**, one model (installed default), same isolation as the pilot (fresh agent environment restored per run, project settings only, $1.50 cap per run). Ceiling: 24 runs, one retry for infrastructure failures, all reported.

## Artifacts saved for every run (reproducibility requirement)
Final repository (with `.git`), baseline commit SHA, patch (diff + list of untracked files), the agent's shell commands, final message, the recipe, `pip freeze` of the agent's environment at the end, Python version, per-run cost/turn count, replay verdicts and evidence records, SHA-256 of the saved repository tree.

## Ablation (restores the pre-registered necessity measure)
For every run whose full-recipe replay gives `pass`: replay once with each declared `setup` step removed, each `prepare` step removed, and each `env` variable removed (the test command is never removed). A declared element is **necessary** if its removal turns the replay into a non-pass, **padding** if the replay still passes. Elements are counted per recipe; steps that were already redundant for the project install (for example `pip install -e .` when the project has no dependencies) are reported as padding, not penalised. The ablation uses the same validator, sandbox and base/head procedure as the verdict.

## Instrument acceptance criteria (fixed now)
1. **Replay determinism**: the full-recipe replay is run twice per run; result classes agree in at least 95% of runs (any disagreement is listed and inspected).
2. **Artifact completeness**: 100% of runs have every artifact above; a missing artifact is an instrument failure.
3. **Recipe validator**: no recipe accepted by the validator executes anything outside the allowed vocabulary (unit tests plus a review of every accepted recipe); every rejected recipe is listed with its reason.
4. **Integrity guard**: no replay used as evidence has a `prepare` step that changed existing files (guard unit-tested; counted in the run records).
5. **No change to the validator, replay, audit or analysis code during the stage** except for bugs found; any change is logged here and the affected measure recomputed.
Failing a criterion means the instrument is not ready for Stage B; it is reported as a finding.

## Descriptive outputs (no hypothesis tests)
Accountability profile per run: truth in the agent environment x zero-config replay x recipe replay; necessity/padding counts; replay time; cost per accountable claim.

## Log
No deviation from the protocol. The recipe validator, replay, audit and runner were not changed after the first Stage A run (last code commits precede the run); the analysis and ablation scripts were written before their outputs were seen.

## Results (2026-10-09)
24 runs (12 tasks x 2 repetitions, prompt C1P), cost **$3.60** (mean $0.15 per run), no agent errors. Raw data and saved artifacts stay local (`data/preconditions/`).

| acceptance criterion | result |
|---|---|
| 1. replay determinism (same result class twice) | **24/24** |
| 2. artifact completeness | **192/192** files (8 per run x 24) |
| 3. validator: nothing outside the vocabulary accepted | **0 rejections**; reviewed every accepted recipe: only plain `pip install` names, `-e .`, the fixture script and pytest commands appear |
| 4. replays refused because a `prepare` step changed existing files | 0 (guard unit-tested separately) |
| 5. no validator/replay/audit changes during the stage | **held** |

**Instrument accepted for Stage B, for tasks of this kind.** The criteria are about the instrument on small synthetic pure-Python tasks; replays on real repositories will have flaky tests, services and heavier installs, so determinism must be re-measured there.

Descriptive outputs (no tests; one model, synthetic tasks):
- **Accountability profile** (truth in the agent's environment was `pass` in all 24): zero-config replay reproduced 10/24 (42%), the agent's recipe 23/24 (96%); both 10, recipe only 13. The one recipe that did not replay (`t1a` rep 1) omitted `requests`, which it imported.
- **Necessity / padding** (declared elements removed one at a time): 35 necessary, 9 padding. **All 9 padding items are `pip install -e .`** in projects with no declared dependencies (the project is not needed in the environment because the tests import the code under test from the worktree). Every dependency, environment variable and generated-fixture `prepare` step the agents declared was necessary.
- **Repair versus declare (exploratory):** on the two environment-variable tasks, the repository was made self-contained in 2 of 4 runs and the variable was only declared in the other 2 (alternating across repetitions: `t3a` rep1 declared, rep2 repaired; `t3b` rep1 repaired, rep2 declared). The choice is stochastic for this model, not a fixed response to the instruction.
- **Cost of accountability:** median full-recipe replay 8 s; the recipe costs one extra file per agent run.

Not established: anything about real repositories, other models, or tasks not designed around environment state.
