# Detection study v2 — results (2026-10-09)

Pre-registration: `DETECTION_V2_PREREG.md` (rules fixed before results; two amendments and a deviation log, all dated). Scripts: `scripts/detection_v2_screen.py`, `detection_v2_select.py`, `detection_v2_run.py`, `detection_v2_analyze.py`. Raw data stays local (`data/`, derived from public GitHub PR metadata and not redistributed).

## What was done
- Screened 2,124 fresh AIDev PRs (Python repositories, not in the earlier CI study) with the GitHub check-runs API: 306 had only passing test jobs (CI-passed), 128 had a failing test job (CI-failed), the rest had no conclusive test job.
- Selected under the registered rules (repository < 300 MB, at most 3 PRs per repository): **70 CI-failed PRs and 70 CI-passed controls in 74 repositories** (agents: Copilot 51, Claude Code 31, Cursor 30, Devin 13, Codex 8, Jules 7). 26 of the 140 had a real "tests pass" claim in the PR body; for the other 114 the statement checked was the fixed sentence "All tests pass.".
- Each PR: environment built by the shipped zero-config ladder, tests at base and head in the sandbox, verdict from the shipped decision logic, both detector configurations (default, and `--new-test-failures review`). Agentvow was run **without** `--ci`: CI is the label, not an input.
- **Arm A** (primary, as registered): the shipped ladder. **Arm B** (sensitivity, Amendment 2): for PRs stopped by a missing dependency in arm A, install the named modules in the sandbox and retry. The arms are disjoint sets of PRs and are reported separately and combined.

## Results
**Q3 reachability (the funnel is the main finding).** A usable run (base suite had at least one passing test) was reached for 15 of 140 PRs in arm A (11%) and 12 of the 83 retried in arm B, **27 of 140 (19%, 95% CI 14–27) overall; 13 of the 70 CI-failed PRs (19%, 11–29)**. Why the other 113 did not: missing dependency 83 (before arm B), environment too heavy (limit 700 MB) 26, the base suite had no passing test 6, no tests collected 3, other 5. After arm B the dominant remaining cause is still an import error in the sandboxed environment.

**Q1 recall and Q2 false alerts, conditional on a usable run** (13 CI-failed PRs in 8 repositories; 14 CI-passed controls in 9 repositories):

| config | CI-failed: CONTRADICTED | + REVIEW REQUIRED | UNKNOWN (no alert) | missed (SUPPORTED) | CI-passed controls: alerts |
|---|---|---|---|---|---|
| default | 2/13 = 15% [4, 42] | 2/13 | 11 | 0 | 1/14 = 7% [1, 31] |
| `review` | 2/13 = 15% [4, 42] | **4/13 = 31% [13, 58]** | 9 | 0 | 1/14 = 7% [1, 31] |

- **The two CONTRADICTED are real, reproducible regressions on real agent PRs**, checked by hand: `pab1it0/prometheus-mcp-server#39` (Claude Code; the PR changed a response from a list to a dict while an existing test still asserts the list) and `gerlero/foamlib#457` (Copilot; a refactor of `FoamFile` breaks one existing test). CI also failed on both.
- REVIEW REQUIRED under `review`: `pgmpy/pgmpy#2345` and one more (Devin). Neither was audited line by line.
- **No CI-failed PR with a usable run was declared fine** (0 misses), but 7 of the 11 UNKNOWN ones simply **fail the same tests locally at base and head**: the CI failure is not reproduced in Agentvow's environment (CI-only dependency, service, platform or flaky job), 2 produced no passing head run, 2 had new failing tests with no baseline.
- **One false alert, on a control: `gerlero/foamlib#453`** (CI passed, Agentvow said CONTRADICTED with 67 "regressions"). Cause (reproduced by hand): the PR adds the dependency `multicollections>=0.1.2,<1`, the environment was built from the repository's current main which has `multicollections` 1.2.0, and the PR's code fails against that API ("Can't instantiate abstract class Parsed"). This is an environment-version mismatch, not a bug in the PR. It counts as a false alert in the numbers above.

## Post-hoc follow-up (not part of the registered result)
The false alert exposed a real weakness: **when a change edits dependency declarations, a test environment built for another commit cannot establish a regression.** A safeguard was added after seeing this: if a local test run shows regressions and the change also edits dependency manifests (`pyproject.toml`, `setup.py/cfg`, requirements, lock files, `tox.ini`, …), the finding is UNKNOWN with REVIEW REQUIRED and an explanation, not CONTRADICTED. On `foamlib#453` it now gives REVIEW REQUIRED. The rule was written after seeing these PRs, so it is in-sample and needs a fresh sample before it is trusted; it can also hide a genuine regression in a PR that touches dependencies. It is covered by unit tests only.

## What this does and does not show
- **Shows:** on real agent PRs where the suite could be run locally, Agentvow caught real regressions (2 of 13 CI-failed PRs; 4 of 13 counting the `review` policy) with one environment-caused false alert in 14 controls, and it never declared a CI-failing PR fine.
- **Does not show:** general recall. 81% of PRs never reached a usable run; the 13 usable CI-failed PRs come from 8 repositories (clustered); CI failure is an imperfect label; the PR sample favours small repositories and is dominated by a few projects; the `review` and dependency rules are in-sample; one annotator; the hypothetical-statement design checks the tool, not what agents actually claimed (only 26 PRs had a real claim, and those give no separate estimate).
- **Honest reading:** the checker is precise when it can run and rarely able to run on unfamiliar repositories without per-project setup. For a developer using their own virtualenv (the product's main path) reachability is not the bottleneck, but this study did not measure that case.
- Earlier invalid starts of the run (two bugs in the study script, not the product) are documented in the deviation log and excluded.
