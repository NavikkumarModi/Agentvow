# Planted-fault benchmark v1 (2026-10-05)

**What this is:** a pipeline-sensitivity test. **What it is not:** evidence of real-world detection. We author both the faults and the check, so this cannot show that agents' real mistakes are caught (RISKS C1).

## Setup
15 real merged agent PRs (Copilot) with a "tests pass" claim: 10 in NewFuture/DDNS (stdlib unittest), 5 in Archmonger/django-dbbackup (pytest, venv). Head = merge commit, base = its parent. Per PR (12 had a changed non-test Python file) we plant a fault in the agent's final code, keep the claim "All tests pass", run the suite in the network-denied sandbox at base and at the faulty head, and take the tool's verdict. **Oracle** (independent of test-id matching): raw passed-test count dropped versus the clean head. Fault classes: behaviour mutation on a line the PR added (operator flips), module-level `ImportError`, syntax error, benign comment (false-alarm control), inflated claimed count (control), and the clean unfaulted state. 80 variants. Script: `scripts/planted_faults.py`; data: `data/planted_faults_v3.csv` (local).

## Results (final run, v3)
| | detected (CONTRADICTED) |
|---|---|
| import break | 10 / 11 |
| syntax break | 10 / 11 |
| behaviour mutation | 4 / 9 |
| **all oracle-confirmed breaks** | **24 / 31 (77%)** |

False alarms: 0/7 no-break fault variants, 0/12 benign comments, 0/15 clean states. Inflated-count and clean controls never produced CONTRADICTED (they gave NOT_CONTRADICTED or UNKNOWN). **Caveat on the inflated-count control:** when environmental failures are present the verdict stays NOT_CONTRADICTED and the count mismatch appears only in the explanation text ("the agent's count differs from the totals AgentMirror found"); it changes the verdict to UNKNOWN only when all tests pass. Whether a count mismatch should escalate the status is an open product decision..

## How we got there (each fix was driven by the benchmark)
1. First run: **0 / 31**. Module-level failures (`_FailedTest`, pytest collection errors) matched no individual baseline test ID, and unittest `-v` hid docstring tests from the baseline passed set.
2. After module-level matching and docstring-aware parsing: 21 / 31.
3. After "suite cannot run at all although it ran at base = regression": 24 / 31.

## The 7 misses
- 5 behaviour faults (DDNS #521 ×2, #571, #539; dbbackup #604): the only tests that break are tests **added by the same PR**, which have no baseline → UNKNOWN by design (uncomparable). A real limit: faults caught only by the PR's own new tests are not attributable to the change.
- 2 (dbbackup #597 import/syntax break): the base commit has **no test suite** (the PR creates it) → no baseline → UNKNOWN is correct.

## Limits and honest reading
- Faults are simple, authored by us, planted after the agent finished; 31 breaking variants over 12 PRs in 2 small repos; no confidence interval claimed.
- A 77% / 0-false-alarm result shows the *mechanics* work (id matching, differential rule, suite-level breaks). Real agent errors differ (logic errors in code that tests don't cover would be missed by any test-run approach: the oracle only counts faults that tests detect).
- Behaviour mutations are caught less often (4/9): many mutated lines are untested or only covered by new tests.
- Not yet measured: flaky tests, tests needing network/services, claims about subsets, multi-suite repos, large suites/timeouts.

## Re-run after the 2026-10-06 review fixes, with a different mutation seed (v4)
Code changes since v3 (module-level matching kept; added missing-test detection, zero-pass guard, signed evidence, stricter freshness, etc.). Seed 23 selects different behaviour mutations on the same 15 PRs; import/syntax faults are the same events as before, so this is only a *partly* held-out check (the behaviour class). Results: **26 / 30** oracle-confirmed breaks attributed (behaviour 6/8, import 10/11, syntax 10/11); 0/8 no-break variants flagged. Misses are the same two kinds: faults only the PR's own new tests catch (DDNS #521, #571) and the base commit without a test suite (dbbackup #597). No recall regression from the review fixes. The fixes in 0→21→24 were tuned on the v1 variants; v4 shows they generalise within these two repos, nothing more. The benchmark still calls the verdict function directly, so it cannot see the integrity problems the review found (forged evidence, base choice); those now have dedicated tests in `tests/test_review_fixes.py`.
