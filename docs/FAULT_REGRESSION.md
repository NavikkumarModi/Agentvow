# Fault regression suite (`tests/test_faults.py`)

Eight scenarios on tiny repositories: a change, the claim "All tests pass.", the real `agentvow check --run-tests` in the real sandbox, verdict and exit code pinned. Offline (unittest only); skipped where no sandbox works. It records what the tool says today, including where it is deliberately silent or unknown, so a behaviour change is decided and not discovered.

| | Scenario | Pinned result |
|---|---|---|
| A | clean change with its own new test (false-alarm control) | SUPPORTED_BY_PRIOR_EVIDENCE, exit 0, "matches the agent's count" |
| B | an operator flip in code an existing test covers | CONTRADICTED, REVIEW REQUIRED, exit 1 ("passed before the change now fail") |
| C | a syntax error that stops the whole suite | CONTRADICTED, exit 1 |
| D | a fault only a test the change itself added catches | UNKNOWN, exit 2 by default; REVIEW REQUIRED, exit 1 with `--new-test-failures review` (the verdict stays UNKNOWN) |
| E | a fault in code no test runs | **not flagged** (SUPPORTED_BY_PRIOR_EVIDENCE, exit 0): passing tests say nothing about code they do not run; the evidence pack's changed-line coverage is what names it |
| F | a claimed test count that is far too high | UNKNOWN, exit 2 (not contradicted) |
| G | a test that fails at base and at head | UNKNOWN: "also fail without the change", not blamed on the change |
| H | everything skipped | UNKNOWN: nothing is confirmed |

**Why D matters.** The fault-injection study on real agent runs (`docs/strategy/PRODUCT_EXPLORATION_2026-10.md` sections 7 and 8) found the same shape on real repositories: a fault that breaks only tests the change itself added cannot be told from an environmental failure when only the final state is seen, so the default answer is UNKNOWN. Whether the hook should use `--new-test-failures review` by default is an open design question (it raises REVIEW REQUIRED for any failing new test, including network-dependent ones); this suite pins the current default.
**Not covered here** (needs network or a captured environment, and was measured in the study instead): the same claim replayed from the captured packages versus the project-native setup.
