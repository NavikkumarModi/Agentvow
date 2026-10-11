# Stage B5 (larger registered test of the fuller attempt-time capture) — results, 2026-10-11

Pre-registration: `STAGE_B5_PREREG.md` (committed before the run; no deviation). 38 of the 44 planned tasks were attempted (the budget rule stopped the run at $31.55 of the $32 cap), 36 repositories, Claude Code under the S0 sandbox, empty virtualenv, one run each; 6 agent errors. Raw data stay local.

## Which runs count
38 attempted: 15 not solved in the agent's environment; 23 passed there, of which 5 were trivial (target tests also pass without the changes) and **18 valid** (>= the registered minimum of 15).

## Result (18 valid runs; same scoped command in every context)
| context | reproduces | 95% CI | outcomes |
|---|---|---|---|
| E_repo: reconstruction from the repository | 3/18 = 17% | 6-39 | 11 inconclusive, 4 fail, 3 pass |
| **E_capture: the fuller capture** | **9/18 = 50%** | 29-71 | 9 pass, 6 inconclusive, 3 fail |
| E_recipe, scoped | 9/18 = 50% | 29-71 | 9 pass, 4 inconclusive, 4 no replay (recipe rejected), 1 fail |
| E_recipe, own command | 8/18 = 44% | 25-66 | |
Paired (repo, capture): both 3, only capture 6, neither 9. Descriptive pool of B4 and B5 (same capture, fresh tasks each): reconstruction 5/26 = 19%, capture 14/26 = 54% [35, 71].

**Pre-registered reading: inconclusive.** "Supported" needed capture >= 70% (it is 50%); "not supported" needed capture <= reconstruction + 10 points (it is +33) or below 50% (it is exactly 50%, not below). The capture is clearly better than reconstruction on these tasks but did not reach the registered bar.

## Why the 9 capture failures (from saved summaries; one verified by re-running the install)
- **5 report a "missing dependency"** (agentops x2, boto3 x2, equinox) although each package is pinned in the captured list. Checked on one (cartography#1622): the same pinned list installs correctly by itself, but inside Agentvow's replay it is killed by **Agentvow's own environment-size guard (700 MB, "environment too heavy")** and the run is then reported as a missing dependency. So these look like an instrument limit (a guard that protects disk), not a failure of the capture; the other four share the signature but were not individually verified.
- 3 fail outright (dspy#8478, onefilellm#65 and #66: tests failing or erroring in the replayed environment), 1 inconclusive (sqlmesh#5078: `No module named pytest`). Not examined further.
- Recipe: 4 of the 18 valid runs had a recipe rejected by the validator (`prepare` or test-command vocabulary, a declared `HOME`, an env name), the same friction as before.

## Reading
- Registered, with enough valid runs for a reading: **capture 50% vs reconstruction 17%, inconclusive against the bar**. Across B3, B4 and B5 the capture has reproduced about half of valid results that reconstruction largely could not, and no registered stage has cleared the 70% bar.
- A material part of the shortfall appears to be a replay guard and not the capture. That is a hypothesis; it is tested post-hoc below, not by this registered stage.
- Limits unchanged: pip-freeze capture only, one model, reconstruction tasks, tasks selected as ones reconstruction failed on, third-party code.

## Post-hoc: the size guard (2026-10-11; NOT registered; no agent; saved patches; `stageb3_recapture.py stageb5 3 ...`)
Hypothesis from the failure analysis: the 5 "missing dependency" capture failures were the replay's own 700 MB environment guard. The limit is now a documented setting (`AGENTVOW_MAX_ENV_MB`, default 700, test added). First attempt: I set the limit inside the re-run script only, which does not reach the replay subprocess, so nothing changed (a mistake of mine, not a result). Corrected re-run of the six runs that had failed on a missing dependency or an unexplained import, limit 3 GB:
| run | registered capture | with the size limit raised |
|---|---|---|
| agent-lightning#148, #160, cartography#1622, levanter#1064 | inconclusive (missing dependency) | **pass** |
| cartography#1820 | inconclusive (missing dependency) | **fail** (the tests now run and fail) |
| sqlmesh#5078 | inconclusive (`No module named pytest`) | inconclusive (`SQLMESH_VERSION` import, the same pattern as B3) |
**So the guard caused 4 of the 5 "missing dependency" failures.** Capture reproduces **13/18 (72%, 95% CI 49-88)** against reconstruction 3/18 (17%) once the guard is raised; this clears the numbers of the registered bar (>= 70%, >= +30 points) but **is post-hoc and does not replace the registered, inconclusive result (9/18)**. The guard exists to protect disk; the lesson for the instrument is that a fixed 700 MB limit turns heavy-but-legitimate environments into false "missing dependency" verdicts, so the verdict text should say "environment too heavy" instead (a product defect, not yet fixed).
Remaining capture failures (5): dspy#8478 (no result), onefilellm#65 and #66 (tests fail), cartography#1820 (tests fail), sqlmesh#5078 (symbol missing, likely a generated version file).
