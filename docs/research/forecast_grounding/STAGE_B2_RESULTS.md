# Stage B2 (ambient-environment falsification run) — results, 2026-10-10

Pre-registration: `STAGE_B2_PREREG.md` (written and committed before the run; no deviation occurred). Same 32 tasks as B1, same model and sandbox, agent's virtualenv **preloaded with 17 common packages** (requests, numpy, pandas, pytest, pytest-asyncio ...), all replay contexts on the **same scoped target command**. 32 runs, **$14.90**, no agent errors. Truth in the agent's own environment: **pass in 32/32**. One run per task; N = 32, descriptive only. Raw data stay local (`data/preconditions/stageb2_*`).

## Result against the pre-registered rule
| context (same frozen patch, scoped target tests) | reproduces | 95% CI |
|---|---|---|
| repository-only replay (zero-config) | **31/32 = 96%** | 84-99 |
| agent's recipe, scoped command | 15/32 = 46% | 31-64 |
| agent's recipe, agent's own command | 12/32 = 37% | 23-55 |
| agent's exact `pip freeze` (control) | 28/32 = 87% | 72-95 |

Pre-registered reading: repository-only replay at least 90% means **B1's "small gap" reading survives this condition**. It does: ambient packages in the agent's environment did not make claims irreproducible from the repository's own declarations (31/32; the one failure is the same telegram#4908 case as in B1, failing in the repository-only and freeze contexts).

## What the ambient environment did change: the agent's recipe
Recipe sufficiency fell from 24/30 (B1) to 15/32. Why (scoped command, 17 non-passing recipe replays):
- **11 inconclusive: `No module named pytest`.** The agents, seeing pytest already installed, did not declare `pip install pytest`; the clean replay had no pytest. This is real hidden state in the sense the study set out to find, but it is **a property of the experiment's ambient set (pytest is preinstalled) and of the test runner, not of project dependencies**; the zero-config ladder installs the runner itself, which is why it was unaffected.
- 1 inconclusive: a missing project dependency (`httpx`, telegram#4908; the non-portable case).
- 5 never replayed: 4 recipes rejected by the validator (2 haliax `PYTHONPATH`, 2 `HOME` in env: jaseci#1897 and ComfyUI-Lora-Manager#586) and 1 run with no recipe written.
- The three own-command failures (Lora-Manager, extending-move, b2500) pass when scoped, as in B1.
The freeze control was inconclusive in 3 runs (the two haliax tasks again reported missing `jax`/`aqt`, probably a freeze-file construction limit for packages the agent installed from non-index sources; not investigated further), so the control itself is imperfect here.

## Reading it honestly
- The adversarial review's cheapest falsifier did **not** falsify the claim that, for repositories whose setup is declarable, a replay from the repository alone reproduces most passing claims (96% with ambient state; still conditioned on the S1 filter, which this run did not remove).
- It **did** show that an agent-declared recipe is fragile when the agent's environment contains tools it takes for granted: the dominant failure is an omitted test runner, which a recipe validator could close deterministically (for example by always installing the declared test runner), a product decision, not yet made. It would be wrong to read the 46% as a rate for recipes in general: 11 of the 17 failures are one omission caused by our own ambient set.
- Still untested: tasks that are not S1-filtered, project dependencies hidden in the ambient state (the ambient set rarely overlaps what these repositories need beyond pytest), other models, natural bug reports.
- Hidden-state markers: the session audit found undeclared installs or environment in 10/32 runs.

## Consequences
0. **Product change made after this result (owner decision: install the runner and say so):** when a recipe's test command uses pytest and the recipe does not install it, the replay installs pytest (only the runner) and the verdict states it (`meta.runner_supplied`, text "Agentvow installed pytest itself ..."). B2's numbers above are as run, before this change and are not recomputed; the 11 omitted-runner runs are expected to replay under it (not re-run).
1. `PAPER_FRAME.md` updated: the repository-only result now holds under an ambient condition; the recipe result is reported as a fragility finding with its cause.
2. Product follow-up (not made): when a recipe's test command names pytest/unittest and the setup does not install it, install the runner in the replay environment and say so (the claim then carries the basis "runner supplied by Agentvow"), or report the omission explicitly as the cause instead of a bare UNKNOWN. The second is already partly true (the summary says "No module named pytest").

## Post-hoc re-replay with the runner-supplied change (2026-10-10; no agent; saved patch + recipe; `stageb_rereplay.py --b2`)
The 11 runs whose scoped recipe replay failed on `No module named pytest`; 10 could be reconstructed (pocket-pick#4 created a file the saved patch lacks).
| outcome of the scoped recipe replay | runs |
|---|---|
| **pass** (SUPPORTED, with the "Agentvow installed pytest itself" note) | **5**: translate#5770, issue-metrics#610, gidgethub#225, scoringengine#1045, skillz#2 |
| inconclusive on a *second* undeclared package that was only in the ambient set | **3**: sunbeam#567 (`yaml`), staticjinja#202 (`typing_extensions`), KToolBox#274 (`httpx`) |
| fail (not investigated) | **2**: open-webui-developer-toolkit#401 (pytest exit 4: probably the hidden `.tests/` path), openai-agents-python#1554 (2 failed; probably an undeclared pytest plugin from the ambient set such as pytest-asyncio) |
**Reading:** the runner change recovers about half (5/10). The other half were never only "pytest omitted": the same ambient environment also hid project dependencies and plugins, which Agentvow deliberately does not supply (they stay UNKNOWN or fail, and the message names the missing module). Updated B2 scoped recipe reproduction on this reading: 15 + 5 = 20/32 (62%) against 31/32 for repository-only replay: the recipe is still the weaker context under ambient state, and the remaining gap is genuine undeclared ambient state (3 + probably 2 runs) plus 4 rejected recipes (2 `PYTHONPATH`, 2 `HOME`) and 1 unreconstructable. Post-hoc analysis, labelled as such; the registered B2 table above is unchanged.
