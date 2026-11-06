# Does the replay earn its place? Results (2026-11-05)

Run of the frozen pre-registration (`REPLAY_VALUE_PREREG.md`, Amendments 1 and 2) by `scripts/replay_value_run.py`, data in `data/replay_value_results.jsonl`. 60 pull requests, 51 repositories (at most 3 per repository), zero-config replay without `--ci`, one machine, no harness failures after the disk fix. No model labels. Nothing here claims novelty.

## Result against the frozen rule
| Question | Measured | Threshold | Met |
|---|---|---|---|
| Q1 yield (SUPPORTED + CONTRADICTED, of 60) | 4 of 60 = 6.7% (Wilson 2.6% to 15.9%) | at least 40% | **No** |
| Q2 planted faults stopped on SUPPORTED runs | 0 of 4 faults (Wilson 0% to 49%), on 2 runs | at least 60% | **No** (n tiny) |
| Q3 confirmed share of CONTRADICTED / new-failure results | 2 of 2 confirmed | at least 75% with at least 4 decided | **Undetermined** (2 decided) |

By the rule, **the replay is not kept as a headline capability**. It is documented as an optional extra that reached a verdict for a minority of pull requests (6.7% here), and the headline narrows to the receipt, UNKNOWN-as-an-outcome and authentication layer.

## What the 60 looked like
- 39 UNKNOWN, 4 NOT_CONTRADICTED (not yield by A1.3), 3 SUPPORTED, 1 CONTRADICTED, 12 `env_too_heavy`, 1 `no_commits`.
- Of the 39 UNKNOWN, 28 had no usable base run (base and head both inconclusive), 9 had the same failing tests at base and head, 2 other.
- The CONTRADICTED result (pbs/pycaption #349) was confirmed by the three-run adjudication. A second confirmed result came from a run with new test failures.
- Of the 3 SUPPORTED runs, faults were planted in 2 (4 faults in total); none changed any test outcome (`oracle_break` 0), so none was stopped.

## What this does and does not show
- The yield is a floor: zero-config setup on arbitrary repositories is the bottleneck (13 of 60 stopped at environment build or commit access, 28 more had no usable base), not the checking logic. It says nothing about a developer's own or an agent-captured environment, which this study did not test.
- 0 of 4 faults is too few to say the replay misses faults; it shows only that the 2 SUPPORTED runs had no tests that exercised the mutated lines (or the mutants were equivalent, which A1.1 counts against the replay).
- Q3 has 2 decided results, so precision is undetermined, not good.
- Single machine, one agent dataset, one period; one annotator, with a mechanical rule.

## Consequence
The rule's own branch applies: narrow the headline to the receipt, UNKNOWN and authentication layer; describe the replay as an optional extra that reaches a verdict for a minority of unfamiliar no-CI pull requests. A study of the replay inside a captured environment would be a separate pre-registration.

## Corrections found by the author's own review (Amendment 3 of the pre-registration)
6 pull requests had first been recorded as `env_too_heavy` although the environment build had stopped on the disk floor ("disk low"), which A1.4 treats as a harness failure. The runner now labels these `harness_low_disk`; the 6 were rerun with 3.5 to 4 GiB free: 2 reached a UNKNOWN verdict, 4 were genuinely too heavy. Yield is unchanged at 4 of 60. Best case before the rerun was 10 of 60 (16.7%), still under the threshold. An independent reviewer has not seen this study; the author did this review.

## Relation to the earlier captured-environment measurement (reuse check, 2026-11-06)
The "captured environment" setting, which this study did not test, was already measured on a small pool in `SHADOW_FAULTS_RESULTS_V2.md`: 15 runs with a passing control, 36 planted single-line faults in 14 repositories, replay from the agent's captured packages. There the captured context stopped 6 of the 36 faults (3 in the 7 runs where both contexts could run, 3 more only because the project-native context could not run the tests at all), escalated the rest or let 10 pass as "continue". That is the same direction as 0 of 4 here, from a different pool and a different setting; neither sample is large and the faults in both are single-line mutants authored by us, with equivalent mutants not excluded. Taken together they give no support for a claim that the replay reliably notices a changed line, and they leave open its value on real defects (needs a plain-pip repository with independently labelled defects). A further captured-environment fault study would mostly repeat that measurement, so none is planned.
