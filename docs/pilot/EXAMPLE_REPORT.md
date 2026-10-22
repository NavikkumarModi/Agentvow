# Agent pull request evidence report: example-org/example-service

> **Illustrative example built from synthetic receipts. Not data from any team.**

Repository: example-org/example-service. Period: 2026-11-01 to 2026-11-28. Receipts counted (latest per commit): **40**, covering 40 pull request(s).

## What the gate decided

| Decision | Changes |
|---|---|
| allow | 10 |
| needs_acknowledgement | 24 |
| block | 6 |

Needs-acknowledgement changes that a named person then acknowledged: 0.

## What the replay said about each claim

| Verdict | Claims |
|---|---|
| CONTRADICTED | 6 |
| NOT_CONTRADICTED | 6 |
| SUPPORTED_BY_PRIOR_EVIDENCE | 14 |
| UNKNOWN | 14 |

## How reproducible the results were

| Contexts that ran and agreed | Changes |
|---|---|
| both | 13 |
| captured_only | 6 |
| native_only | 7 |
| single | 14 |

`both`: the agent's captured packages and the repository's own files both reproduced the result. `captured_only` / `native_only`: only one did. `single`: only one context ran. `neither`: no context reproduced a pass.

## How much of the changed code the tests ran

Median fraction of changed executable lines run by the tests: **40%** over 33 receipts with coverage data; 20 had fewer than half of the changed lines run.

## What the replay could not recreate (named, not judged)

| Category | Receipts |
|---|---|
| environment variables | 40 |
| network use | 14 |
| external programs the tests invoke | 8 |

5 claim(s) used a capture supplied as a file (checked against the exact files and replayed, but not authenticated).

## By week

| Week | allow | needs_acknowledgement | block |
|---|---|---|---|
| 2026-W44 | 0 | 2 | 0 |
| 2026-W45 | 3 | 5 | 2 |
| 2026-W46 | 2 | 7 | 1 |
| 2026-W47 | 4 | 4 | 2 |
| 2026-W48 | 1 | 6 | 1 |

## Changes that were not simply allowed

| Commit | PR | Decision | Rules |
|---|---|---|---|
| `0000000000` | 100 | needs_acknowledgement | unauthenticated_capture |
| `0000000000` | 101 | needs_acknowledgement | min_changed_line_coverage |
| `0000000000` | 102 | needs_acknowledgement | unknown |
| `0000000000` | 103 | needs_acknowledgement | unknown |
| `0000000000` | 104 | block | contradicted |
| `0000000000` | 107 | needs_acknowledgement | min_changed_line_coverage |
| `0000000000` | 108 | needs_acknowledgement | unknown |
| `0000000000` | 109 | needs_acknowledgement | unknown |
| `0000000000` | 110 | block | contradicted |
| `0000000000` | 113 | needs_acknowledgement | min_changed_line_coverage |
| `0000000000` | 114 | needs_acknowledgement | unknown |
| `0000000000` | 115 | needs_acknowledgement | unknown |
| `0000000000` | 116 | block | contradicted |
| `0000000000` | 118 | needs_acknowledgement | unauthenticated_capture |
| `0000000000` | 119 | needs_acknowledgement | min_changed_line_coverage |
| `0000000000` | 120 | needs_acknowledgement | unknown |
| `0000000000` | 121 | needs_acknowledgement | unknown |
| `0000000000` | 122 | block | contradicted |
| `0000000000` | 125 | needs_acknowledgement | min_changed_line_coverage |
| `0000000000` | 126 | needs_acknowledgement | unknown |
| `0000000000` | 127 | needs_acknowledgement | unknown |
| `0000000000` | 128 | block | contradicted |
| `0000000000` | 131 | needs_acknowledgement | min_changed_line_coverage |
| `0000000000` | 132 | needs_acknowledgement | unknown |
| `0000000000` | 133 | needs_acknowledgement | unknown |

## What we recommend

- 14 of 40 claims were UNKNOWN. Each pull request comment names the cause and a next step. In the study behind Agentvow, the most common cause (7 of 10 misses by a repository-only replay) was a dependency that none of the repository's own files installed; others were credentials, network or services the replay does not recreate.
- In 20 of 33 receipts with coverage data, the tests ran fewer than half of the changed lines. A low share means the tests did not execute much of the new code; ask whether tests exist for it.
- 6 change(s) were blocked by the policy. Review each: a contradiction means the check found the agent's claim false in the replay.

## Limits of this report

What this report shows: how many agent pull requests went through the gate, what the replay said about each, how often the result could be reproduced in more than one way, how much of the changed code the tests ran, and what the replay could not recreate. What it does not show: that any change is correct, that any defect was prevented, or that review time was saved. The output of a test run is written by the code under test; a pass is evidence to weigh, not verification. The counts come from receipts the team's own runners produced.
