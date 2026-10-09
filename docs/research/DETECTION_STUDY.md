# Detection study on real CI-failing PRs (2026-10-07): detection NOT demonstrated

Script: `scripts/local_coverage.py` (run with `detection_sample.csv`), analysis `scripts/detection_analyze.py`; data local in `data/` (`detection_results.jsonl`).

## Design
46 Python PRs from AIDev that claim "tests pass", in repositories under 100 MB: 23 where a CI test job failed on the PR head commit (`ci_failed`) and 23 CI-passing controls (`ci_passed`), same repos where possible. Zero-config environment (`agentvow.envsetup`: venv, editable install with extras, PEP 735 groups, requirements files, pytest; installs sandboxed with size/disk guards), then tests at the PR's base and head under the network-denied sandbox, verdict from the shipped decision logic. The study was resumed once after a fix (`$HOME` was outside the sandbox's writable paths): the two repos that hit it were re-run; all other rows are from the same code.

## Results (46 PRs, 25 repos)
| group | not run (environment too heavy) | ran | CONTRADICTED | UNKNOWN | other verdicts |
|---|---|---|---|---|---|
| ci_failed | 4 | 19 | **0** | 19 | none |
| ci_passed (controls) | 6 | 17 | 0 (no false alarms) | 11 | 5 SUPPORTED, 1 NOT_CONTRADICTED |

Why the 19 CI-failing PRs that ran gave no verdict: dependency missing in the automatic environment 9; timeout (240 s) 2; dependency-version mismatch 1; a generated module missing 1; a `PermissionError` inside a test run (dbt-databricks, not explained) 1; no tests collected 1; **tests ran 4** (3 with failures, 1 all passed).
The 4 that ran:
- knocker #6 and #9: local run **fails at head** (3 and 14 failing tests) while the base passes (40 and 67 tests), matching CI. All failing tests are new in the PR, so no baseline: UNKNOWN by design.
- air #627: 1 failing test at head (also failing at base): environment-level, UNKNOWN.
- micropython-stubs #840: **local run passes, CI failed** (a disagreement: CI test jobs may be environment-specific, or flaky); UNKNOWN.

## Conclusions
1. **Detection on real bad PRs is not demonstrated.** 0 CONTRADICTED among 19 CI-failing PRs that ran, but 15 of the 19 never produced a usable test run, so the result says nothing about recall. The only detection evidence remains the planted-fault study (26/30 on authored faults, see `PLANTED_FAULTS.md`), which measures matching mechanics, not real-world detection.
2. **No false alarms:** 0 CONTRADICTED among 17 controls that ran (small n; four of the six non-UNKNOWN control verdicts came from one repo).
3. **Zero-config environment setup is the bottleneck** (about 8 of 10 failed runs are environment problems), consistent with the coverage study. A developer's own virtualenv avoids this; a server/CI path needs per-project setup.
4. **The new-test-failure blind spot is confirmed on real PRs** (knocker #6 and #9: real failures that CI also saw, left UNKNOWN because the failing tests are new in the PR).

## Product decision: `--new-test-failures unknown|review` (implemented, default `unknown`)
With `review`, unresolved failures in tests added or changed by the same PR set `attention` and raise REVIEW REQUIRED (verdict stays UNKNOWN, not CONTRADICTED). Measured trade-off, from data on hand:
- Planted-fault study (v4): recall on oracle-confirmed breaks 26/30 → 28/30, but 3 of 15 clean states would alert (their new tests fail only because of the environment).
- Real PRs, this study: it would flag knocker #6 and #9 (genuine) but also 3 other PRs whose "new" failures were collection errors from environment problems (zen-mcp-server #283 and #247, social-app-django #811): 2 genuine of 5 alerts. In the earlier 28-PR coverage study it would alert on 2 of 28 (both without CI).
- **Refinement (2026-10-07, in-sample):** unresolved failures do not count when the suite had no passing tests at base (`no_baseline`: nothing is attributable). Re-evaluated on this study's data, `review` then alerts on exactly knocker #6 and #9 (2 of 2 genuine) and on 0 of the 16 controls that ran. The rule was written after seeing these PRs, so this is in-sample and needs fresh data before it is trusted.
- Conclusion (before the refinement): keep `unknown` as the default; `review` buys sensitivity at about a 1-in-2 to 1-in-3 false-alert rate on these samples. A sharper rule is a clear next step: do not count collection errors that also occur at base as unresolved new-test failures.

## Limits
n small (36 ran), small repos only, one annotator for categories, repository clustering (knocker alone is 8 PRs), zero-config setup only, no project-specific setup, no CI-failing PR reproduced under a good environment.

## Bugs found by this study (fixed, tested)
`$HOME` for test runs was outside the sandbox's writable paths, so tests that write caches/config there failed (now `<worktree>/.agentvow/home`). Earlier in this line of work: killed pip installs left GBs of temp files in `/tmp` (pip temp now inside the throwaway environment).
