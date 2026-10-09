# Local-run coverage: can Agentvow verify agent test claims on unfamiliar repos? (2026-10-07)

Script: `scripts/local_coverage.py`; data (local): `data/local_coverage.jsonl` (+ run1/run2 snapshots). Sample: 33 merged PRs in 27 small public Python repos (<40 MB), from the CI study: 18 with no CI at all, 15 where CI could judge (all 15 happened to be CI-SUPPORTED, so no CI-failing PR is in the sample). Automatic environment ladder per repo: venv, `pip install -e .[test|tests|testing|dev]`, requirements files, pytest; installs and tests run under `sandbox-exec` (installs: network allowed, writes limited; tests: network denied). Environment built once per repo at the first PR's head and reused; tests run at the PR's base and head states.

## Results (final run; 33 PRs, 27 repos)
- 5 PRs (4 repos) skipped by the environment-size guard (>700 MB of dependencies, e.g. torch-class): not attempted.
- 28 PRs ran tests: **all passed 3, some failed 9, inconclusive 16** (of which 14 = a dependency missing in the automatically built environment, 2 other).
- **Verdicts: 8 / 28 (29%)**: 2 SUPPORTED (count matched), 6 NOT_CONTRADICTED (failures identical at base and head: environmental), **0 CONTRADICTED**, 20 UNKNOWN.
- Group no-CI (15 ran): 4 NOT_CONTRADICTED, 0 SUPPORTED, 11 UNKNOWN. Group CI-judged (13 ran; CI said SUPPORTED for all): local 2 SUPPORTED, 2 NOT_CONTRADICTED, 9 UNKNOWN, **no disagreement with CI**.
- Interpretation: on unfamiliar repos with a generic automatic setup, a local run reaches a weak or strong verdict for under a third of PRs; **the bottleneck is environment setup (50% of runs stopped on a missing dependency)**, not the checking logic. Where a developer runs it in their own environment (the intended use; see the attrition check) this bottleneck largely disappears, so these numbers are a lower bound for that use and a realistic bound for a zero-config server/CI use.

## What this does not show
- Detection: no CI-failing PR was in the sample, so recall on real bad PRs is untested here. 0 CONTRADICTED and 0 disagreements is not evidence of correctness.
- n=33 (28 ran), small repos only (<40 MB), one annotator, one setup ladder; project-specific setup (e.g. Django settings variables, services, system libraries) is not handled.

## Defects in Agentvow found by this run (all fixed, with tests)
1. A PR that adds a new third-party dependency looked like a broken import (CONTRADICTED with 138 "regressions" on a PR that CI had passed). Now a module that is not part of the repo is an environment limit: inconclusive, never a regression.
2. A project whose pytest config makes output extra quiet has no final "N passed" line; counts parsed as zero and the suite was reported as unable to run (same false CONTRADICTED). Now counts fall back to the per-test lines, and "suite cannot run" requires that no test result exists at all.
3. Runs record the first error line (`hint`) so an inconclusive result says why.

## Incident (my error, disclosed)
The first run filled the machine's disk: the throwaway virtualenvs (4.8 GB, torch-class dependencies) and pip cache exhausted free space (119 MB left of 228 GB), which also corrupted several runs. I deleted those folders, then added: no pip cache, a live size watchdog that kills an install above 700 MB, a free-space floor (2.5 GB), and environment deletion after each repo. The watchdog's first version crashed the whole run on a PermissionError when killing the sandboxed process; fixed with a fallback kill and per-repo error isolation.
