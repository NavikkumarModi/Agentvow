# Preconditions pilot — results (2026-10-09)

Pre-registration: `PRECONDITIONS_PREREG.md` (including its deviation log). Harness: `research/preconditions/{make_tasks,verify_tasks,run_pilot,analyze_pilot}.py`. Raw runs stay in `data/` (local). 12 tasks verified before any agent ran (fail at start, pass with the reference solution, reference recipe replays as designed), 36 runs (12 tasks x 3 conditions), one model (the installed Claude Code default, Claude Sonnet 5 per its usage report), total reported cost $5.26 (list basis), no errors, no aborted runs.

## What was measured
Agents worked in a virtualenv preloaded with packages the repositories do not declare (the *ambient* state). After each run: truth in the agent's own environment; the **zero-config replay** (Agentvow's `--setup auto` ladder, clean environment built from the repository's own declarations); and, on C1/C2, the **replay of the agent's own declared recipe** (clean environment built only from what it declared). C0 = no recipe requested, C1 = recipe requested, C2 = recipe requested and told it will be replayed.

## Results
- Agents behaved well: in all 36 runs they made a tests-pass claim, the claim was true in their environment, and no agent edited an existing test. (So this pilot says nothing about dishonest claims.)
- **Accountability** (share of runs where Agentvow reached a SUPPORTED verdict independently; no run produced CONTRADICTED):

| | zero-config replay | agent's recipe replay |
|---|---|---|
| C0 | 6/12 = 50% [25, 75] | n/a |
| C1 | 5/12 = 42% [19, 68] | 10/12 = 83% [55, 95] |
| C2 | 5/12 = 42% [19, 68] | 9/12 = 75% [47, 91] |

- **By trap (all agent runs passed in their own environment):**

| trap | zero-config replay reproduces | agent's recipe reproduces (C1+C2) |
|---|---|---|
| declared dependency (control) | 6/6 | 4/4 |
| no precondition (control) | 6/6 | 4/4 |
| environment variable | 4/6 | 4/4 |
| **undeclared dependency** (requests, numpy present only in the agent's environment) | **0/6** | **4/4** |
| version-sensitive API (numpy 2, PyYAML 6) | **0/6** | 3/4 |
| **generated untracked file** | 0/6 | **0/4 (recipe rejected, see below)** |

- **Where the agent's own declaration worked:** on the 20 C1/C2 runs whose preconditions the recipe vocabulary can express, the replay reproduced the result in **19/20 (95%)**. The one failure (`t4a`, C2) is a real insufficiency: the agent declared `pip install -e .` and `pytest` but not `numpy`, which it imported (the ambient-import audit flagged exactly that module).
- **Where it could not:** in the 4 generated-file runs the agents *knew* the precondition and said so in their final message ("generated the gitignored fixture via the existing script"), and tried to declare it (`"test": "python3 scripts/make_fixture.py && pytest ..."` or a `python scripts/...` setup step). Agentvow's recipe validator rejected all four, so nothing was replayed. This is a **vocabulary gap in the instrument, not ignorance by the agent**: the recipe schema cannot express "run this repository script first".
- **Hidden state (ambient imports declared nowhere):** 4 of 12 C0 runs (all in the undeclared-dependency and version-sensitive tasks) versus 0 of 12 C1 and 1 of 12 C2. The session audit of installs/exports/system changes found almost nothing (agents rarely installed anything; the hidden state was what was already there).
- **Fixing the repository versus declaring the workaround (exploratory, one task):** on `t3a` the C0 agent made the repository self-contained (code now falls back to `.env.example`) and its work replays with zero config; both recipe-condition agents changed nothing and declared `PKG_MODE=test` in the recipe, so the result is reproducible only through the declaration. On `t3b` all three agents edited the code. No agent pinned a dependency version in any task; all patched the code.
- **Visibility (C2 vs C1):** 9/12 versus 10/12 sufficient; the difference is the single numpy omission. No evidence of an effect of telling the agent it will be replayed.

## Reading against the pre-registered hypotheses
- **H1 (recipes raise accountability): supported** in this pilot (zero-config 42-50% versus recipe 75-83% on identical tasks, and paired on identical agent output 5/12 versus 10/12).
- **H2 (sufficiency lower for traps 1, 3, 4, 5): not supported for traps 1 and 3** (agents declared undeclared dependencies and environment variables correctly), **weak for 4** (3/4), **supported for 5 only because of the vocabulary gap**.
- **H3 (visibility): no difference observed.**

## What this does and does not show
- It shows a measurable gap: the agent's own environment held dependencies nobody else could see, and a replay from the repository alone could not reproduce 50-58% of otherwise correct work; a self-declared recipe closed most of that gap at a cost of one extra file per run, with an accurate declaration in 19 of 20 expressible cases.
- It does **not** show that agents are bad at knowing their preconditions (the opposite, on these tasks), nor anything about dishonest agents, other model families, real repositories or larger tasks. 12 small synthetic tasks, one model, one repetition each, tasks designed by us. The trap set favours the recipe (all traps were designed around environment state).
- The secondary pre-registered measure (necessity/padding by ablation) was **not run**; the saved final repositories were not kept for ablation. Reported as dropped.
- Deviations were logged in the pre-registration as they occurred (ambient-import measure added after a dry run; paired zero-config replay added; audit parser bug fixed with recomputation from saved sessions).

## Consequences for the product (post-hoc, to be treated as such)
1. Recipe vocabulary needs a `prepare` step: run a repository script (inside the sandbox, before the tests) for generated/untracked fixtures. Without it a correct, honest declaration is rejected.
2. The claim extractor missed "The test passes." in a dry run; it should accept singular forms.
3. The ambient-import audit is the right detector for hidden dependencies (a session audit of installs alone is not enough).
