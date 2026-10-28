# Shadow study, offline arms, run 2: results (2026-10-28)

Pre-registration: `SHADOW_FAULTS_PREREG_V2.md` (written before the run; reading rules applied unchanged). Script `research/shadow/run_faults.py` (v2), output `data/shadow/faults_v2.jsonl` (local). One pass. Arm C is the **freeze-recipe context** (a recipe installing the agent's pip freeze), not a capsule replay; decisions use the simplified map over the tests_pass finding only.

## Flow
20 valid B6 runs: 4 not re-runnable, 1 no plantable line, **15 runs with an unfaulted control and 36 faults in 14 repositories**. 0 harness failures (every check produced test evidence). Order: captured first 25, native first 11. Controls: captured passed in all 15; native passed in 7 and was UNKNOWN in 8 (the project-native context could not run the tests at all).

## Pre-registered reading
Pool P (faults in runs where at least one control passed, no harness failure): **36 faults, 15 runs, 14 repositories (≥20)**. C stops and B does not: **3 faults (Bindu#10 negate; things-mcp#8 negate and flip) from 2 repositories.** The rule needs at least 3 faults from at least 3 repositories, so the pre-registered reading is **"no change seen in this pool"** (not "supports"). B stops and C does not: **0**. This is a statement about this pool of authored single-line faults, not about real defects.

## What the structure shows
- **Clean comparison (both controls pass): 7 runs, 19 faults. The two contexts decided identically on all 19** (each: 3 stop, 12 escalate, 4 continue).
- **Native control UNKNOWN: 8 runs, 17 faults.** The native context escalated all 17 by construction (it cannot run the tests). The captured context stopped 3, continued 6, escalated 8. The 3 captured-only stops (and the 6 continues) are therefore entirely a consequence of being able to run the tests at all. The effect of capture here is reproducibility, as in E3, not a different view of the same evidence.
- **Clear-on-unseen-fault trade-off:** 10 faults in 6 runs produced "continue" in the captured context (tests ran and passed with the fault). In 6 of those (3 runs: hlda#56, vehicle_speed_estimation#7, things-mcp#8) the native context honestly escalated. Whether those faults change behaviour, or whether the faulted line is executed by any test, was not checked (equivalent mutants are reduced but not excluded).
- **Failing tests that stay UNKNOWN:** of the 19 clean-comparison faults, 12 ended UNKNOWN in both contexts although tests failed on the exact state. Consistent with E5: tests the change itself adds fail at the base by construction, so a fault that breaks them has no passing baseline and the failure is not attributable. This is a design limit of the differential rule, now seen on 12 faults in 7 runs.

## Comparison with run 1
Run 1 (37 faults, no control, partly harness failures) pointed the same way but was confounded; its reading was withdrawn. Run 2 does not reproduce independently: same 20 runs, same generator family, different seed and the fixed generator.

## Limits
Faults authored by us, single-line; one agent family; one host; target tests only; faults within a run not independent (36 faults, 15 runs); executed-line coverage and equivalent mutants unchecked; arm A (CI only) and unsafe advancement against ground truth not measured; one annotator. No confidence intervals.

## What this means for the plan
In the one pool available, the freeze-recipe context adds decisions only where the project-native context cannot run, and in those runs it also converts some escalations into "continue". It does not add a different view where both can run. The question of decision value on real defects remains open and needs a plain-pip repository with real agent pull requests and independently labelled defects (`SHADOW_STUDY_DESIGN_2026-10-27.md`, step 4). Nothing here changes the vision's wedge claim from "potential gap requiring further verification".
