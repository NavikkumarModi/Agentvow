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
- 37 UNKNOWN, 4 NOT_CONTRADICTED (not yield by A1.3), 3 SUPPORTED, 1 CONTRADICTED, 14 `env_too_heavy`, 1 `no_commits`.
- Of the 37 UNKNOWN, 26 had no usable base run (base and head both inconclusive), 9 had the same failing tests at base and head, 2 other.
- The CONTRADICTED result (pbs/pycaption #349) was confirmed by the three-run adjudication. A second confirmed result came from a run with new test failures.
- Of the 3 SUPPORTED runs, faults were planted in 2 (4 faults in total); none changed any test outcome (`oracle_break` 0), so none was stopped.

## What this does and does not show
- The yield is a floor: zero-config setup on arbitrary repositories is the bottleneck (18 of 60 stopped at environment build or commit access, 26 more had no usable base), not the checking logic. It says nothing about a developer's own or an agent-captured environment, which this study did not test.
- 0 of 4 faults is too few to say the replay misses faults; it shows only that the 2 SUPPORTED runs had no tests that exercised the mutated lines (or the mutants were equivalent, which A1.1 counts against the replay).
- Q3 has 2 decided results, so precision is undetermined, not good.
- Single machine, one agent dataset, one period; one annotator, with a mechanical rule.

## Consequence
The rule's own branch applies: narrow the headline to the receipt, UNKNOWN and authentication layer; describe the replay as an optional extra that reaches a verdict for a minority of unfamiliar no-CI pull requests. A study of the replay inside a captured environment would be a separate pre-registration.
