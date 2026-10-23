# Sample evidence report (from the live test repository, not from a customer)

> Built on 2026-10-23 by `agentvow pilot-report` from the receipts the control plane stored during its first live run (`docs/LIVE_TESTING.md`): a throwaway public repository whose pull requests the maintainer wrote to exercise the gate. They are **not agent traffic and not a customer**; the numbers show the shape of the report, not what a team would see. Receipts are unmodified; one acknowledgement was made by the maintainer through the real comment flow. The same report with synthetic data and more volume: `docs/pilot/EXAMPLE_REPORT.md`.


Repository: NavikkumarModi/agentvow-live-test. Period: 2026-10-23 to 2026-10-23. Receipts counted (latest per commit): **5**, covering 5 pull request(s).

## What the gate decided

| Decision | Changes |
|---|---|
| allow | 2 |
| needs_acknowledgement | 2 |
| block | 1 |

Needs-acknowledgement changes that a named person then acknowledged: 1.

## What the replay said about each claim

| Verdict | Claims |
|---|---|
| CONTRADICTED | 1 |
| SUPPORTED_BY_PRIOR_EVIDENCE | 1 |
| UNKNOWN | 3 |

## How reproducible the results were

| Contexts that ran and agreed | Changes |
|---|---|
| single | 5 |

`both`: the agent's captured packages and the repository's own files both reproduced the result. `captured_only` / `native_only`: only one did. `single`: only one context ran. `neither`: no context reproduced a pass.

## How much of the changed code the tests ran

Median fraction of changed executable lines run by the tests: **50%** over 5 receipts with coverage data; 0 had fewer than half of the changed lines run.

## Changes that were not simply allowed

| Commit | PR | Decision | Rules |
|---|---|---|---|
| `dea516869f` | 3 | block | contradicted |
| `1c8343c016` | 4 | needs_acknowledgement | unknown |
| `78725a8dd0` | 7 | needs_acknowledgement | unknown |

## What we recommend

- 5 of 5 receipts had only one replay context. Capture the agent's environment at the end of each agent turn (`agentvow init` for Claude Code) so the replay can compare the agent's packages with what the repository declares.
- 3 of 5 claims were UNKNOWN. Each pull request comment names the cause and a next step. In the study behind Agentvow, the most common cause (7 of 10 misses by a repository-only replay) was a dependency that none of the repository's own files installed; others were credentials, network or services the replay does not recreate.
- 1 change(s) were blocked by the policy. Review each: a contradiction means the check found the agent's claim false in the replay.

## Limits of this report

What this report shows: how many agent pull requests went through the gate, what the replay said about each, how often the result could be reproduced in more than one way, how much of the changed code the tests ran, and what the replay could not recreate. What it does not show: that any change is correct, that any defect was prevented, or that review time was saved. The output of a test run is written by the code under test; a pass is evidence to weigh, not verification. The counts come from receipts the team's own runners produced.
