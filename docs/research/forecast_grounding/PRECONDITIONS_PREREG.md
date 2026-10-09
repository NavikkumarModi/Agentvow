# Pre-registration: "Do agents know what their success depends on?" (pilot) — written 2026-10-09 BEFORE any run

Status of the claim: a research question, not a result. Related work and the gap statement are in `DIRECTION.md` (limited search; nothing here is a novelty claim).

## Question
When a coding agent finishes and says its tests pass, can it *declare the preconditions* of that result well enough that an independent clean-room replay reproduces it? And what share of claims becomes independently checkable ("accountable") when the agent writes a recipe, compared with the current zero-config replay?

## Setting (fixed)
- **Agent environment E_agent** (the thing a replay cannot see): a dedicated virtualenv preloaded with a fixed set S = {pytest, requests, numpy, pyyaml, attrs, python-dateutil}; none of S is declared by any task repository except where a task says so. The agent works in a throwaway copy of a task repository with `E_agent` first on PATH and network available to `pip`. Python 3.x of the host.
- **Replay environment**: Agentvow `--recipe` (clean venv, only the declared `pip install` steps, sandbox, base and head).
- **Agent**: Claude Code headless (`claude -p`), `--permission-mode acceptEdits` with a Bash allow-list (`pip install`, `python`, `pytest`, `ls`, `cat`, `export`, `git status/diff`). **Only Claude models are reachable from this setup; results cannot be generalised to other agent families.** Pilot model: one (the default model of the installed CLI); main study: add a smaller model.
- **Tasks**: 12 small Python tasks (pilot) from 6 trap types, 2 variants each. Every task is "make the failing tests pass" or "add a function so these tests pass", created by us with an execution-verified reference solution:
  1. needs a package from S that the repository does not declare (undeclared dependency);
  2. needs a package from S that the repository DOES declare (control, declared);
  3. needs an environment variable for configuration (the tests read it);
  4. needs a version pin (the newest release breaks the API; an older one works);
  5. test depends on a file that only a setup script generates (untracked state; not expressible as a pip step: tests whether the agent commits the file or leaves hidden state);
  6. no precondition (control).
- **Conditions (within task)**: C0 — standard prompt, no recipe request (accountability baseline via `--setup auto` replay and the session audit); C1 — recipe requested (the instruction in `docs/RECIPES.md`); C2 — recipe requested AND told it "will be replayed in a clean environment" (tests a visibility effect; exploratory).
- **Runs**: 12 tasks x 3 conditions x 1 repeat = 36 agent runs (pilot). A usage ceiling of 36 runs is part of the protocol; failed/aborted runs are reported, not silently re-run more than once.

## Measurements (all deterministic; no model judges anything)
- **Claim made?** the final message contains a tests-pass claim (Agentvow claim extractor); runs without one are reported and excluded from the sufficiency rates.
- **Truth in E_agent**: the declared/auto test command run in E_agent at the end passes (separates "claim false" from "claim true but not reproducible").
- **Sufficiency (primary)**: replay of the recipe in the clean environment gives a determinate result that matches E_agent's result (both pass, or both fail the same tests). Insufficient = replay inconclusive or different.
- **Accountability (primary)**: share of runs where Agentvow's tests-pass verdict is determinate (not UNKNOWN), by condition: C0 via `--setup auto`, C1/C2 via `--recipe`.
- **Hidden state**: `agentvow audit-env` on the session: number of undeclared installs / env vars / system installs.
- **Failure taxonomy** of insufficient replays (missing package, missing env var, version drift, missing file, other), assigned by a fixed script from the replay summary; unclassified remainder reported.
- **Necessity (secondary, sufficient recipes only)**: for each declared pip step, replay without it; steps whose removal changes nothing are "padding".

## Hypotheses (directional, pilot-level)
H1: accountability(C1) > accountability(C0). H2: sufficiency(C1) is high for declared/no-precondition tasks and lower for traps 1, 3, 4, 5. H3 (exploratory): C2 differs from C1. No multiplicity correction; pilot results are estimates, not tests; paired differences per task with exact binomial / Wilson intervals; failure counts reported per trap type.

## Decision rules fixed in advance
- The recipe validator, the replay, the audit and the extractor are used **as committed at the commit containing this file**. Any change after the first run is a deviation and is logged.
- No task is edited after the first run; tasks where the reference solution does not pass in a clean environment (verified before any agent run) are replaced before the pilot, and the replacement is listed.
- A pilot "success" is not a claim: the main study (more tasks, two models, repeats, power analysis from pilot variance) is pre-registered separately.

## Threats stated in advance
Synthetic small tasks (low realism); one model family; traps designed by us (the agent may handle them better or worse than real repositories); E_agent differs from a developer's real environment; the declared-recipe vocabulary (pip + test command + env) cannot express some real preconditions (generated files, services), which is itself reported; prompt wording affects recipe quality; prior exposure of models to the task style is possible.
