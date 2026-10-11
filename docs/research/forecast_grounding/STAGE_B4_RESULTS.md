# Stage B4 (registered test of a fuller attempt-time capture) — results, 2026-10-11

Pre-registration: `STAGE_B4_PREREG.md` (committed before the run; no deviation occurred other than an authentication stop before any row was recorded). 22 of the planned 24 tasks were attempted (the run stopped by the budget rule at $16.88, under the $18 cap, with no run allowed to start if it could exceed it); fresh tasks that B3 did not use, from the candidates without a reconstructable environment, 20 repositories, Claude Code under the S0 sandbox, empty virtualenv, one run each. 3 runs ended with an agent error. Raw data stay local.

## Which runs count
22 attempted: 5 not solved in the agent's environment; 17 passed there, of which **9 were trivial** (the target tests also passed without the changes, so excluded under the pre-registered validity rule) and **8 valid**. (B3 had 11 valid of 19.)

## Result (8 valid runs; same scoped command in every context)
| context | reproduces | 95% CI |
|---|---|---|
| E_repo: reconstruction from the repository (zero-config ladder) | 2/8 = 25% | 7-59 |
| **E_capture: the fuller capture** | **5/8 = 62%** | 31-86 |
| E_recipe, scoped | 4/8 = 50% | 22-78 |
Paired (repo, capture): both reproduce 2, only capture reproduces 3, neither 3.

**Pre-registered reading: none can be drawn.** The registration required at least 10 valid runs ("fewer than 10 valid runs is reported as underpowered and no reading is drawn"); there are 8. For information only, the numbers would not have met the "supported" bar either (62% < 70%), and capture is 37 points above reconstruction.
Reconstruction reproduced 2 of 8 here although all tasks had failed Stage B0's reconstruction earlier: the ladder's environment resolution differs from day to day, as B1 had already shown.

## The three capture failures (not examined beyond the saved summaries)
deepmd-kit#4893 (collection error), scoringengine#1008 (collection error), agent-lightning#198 (`agentops` missing: the dependency is absent from the pinned list, consistent with an editable or direct-URL install that the capture drops). Unexplained collection errors may involve generated files or system libraries that a pip-freeze capture cannot carry.

## Reading
- B3 (simple capture, registered): 5/11, inconclusive. B3 post-hoc (repaired capture, not registered): 8/11. B4 (repaired capture, registered, fresh tasks): **underpowered, 5/8 descriptive**. Across the three, capture of the agent's installed packages reproduced a majority of valid results that reconstruction mostly could not, but **no registered test has reached a conclusion**.
- The binding limit on this line of work is task yield, not the replay: more than half of the runs in which the agent passed were trivial (9 of 17 in B4, 5 of 16 in B3), because the target tests also pass without the agent's changes once an environment exists. A usable design needs a non-triviality screen before the agent runs, which needs a working environment for the base commit, which is the thing that was missing.
- Not shown: that attempt-time capture raises replayability to a level that supports routing at volume. Weak proxy (pip freeze only), N = 8-11 per stage, one model, reconstruction tasks, third-party code.
