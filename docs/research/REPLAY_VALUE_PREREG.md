# Does the replay earn its place? Pre-registration (2026-11-05; FROZEN at the commit that adds this file; not run)

Status: frozen. The owner confirmed the thresholds in section 5 unchanged (2026-11-05), before any run. Any later change is an amendment, dated and listed at the end, never an edit of the rules above. Nothing here claims novelty. LLM labels are not used for any outcome.

## 1. Why this question
The prior-art reading (`RECEIPT_AUTH_DESIGN.md` sections 16 to 18) found that rule-based claim-to-diff checking exists (groundtruth), as do evidence receipts with an unproven state (FetchSandbox, BobSpot). What remains different in Agentvow is **running the tests in a sandbox against the commit** and the receipt and authentication layer around it. Earlier results bracket the replay's value but do not settle it:
- Where CI exists and has a test job, CI already answers "do the tests pass" (the shadow experiment found no evidence that arm 5 beats CI).
- About two thirds of agent pull requests that claim passing tests have **no CI verdict** (53% no CI at all, 13 to 14% CI without a recognisable test job; `CI_CLAIM_STUDY.md`). There a local run is the only check.
- On unfamiliar repositories with the zero-config ladder, a usable run was reached for 19% (detection v2) to 29% (local coverage) of pull requests, with 0 CONTRADICTED in the 28 local-coverage runs; the bottleneck was environment setup, not the checking logic.
- In the one pool where a faulted line could be planted, the replay added decisions only where the project-native context could not run at all, and 10 of 36 faults still ended "continue" (`SHADOW_FAULTS_RESULTS_V2.md`).
So the open, label-free question is: **where CI gives no verdict, how often does the replay give one, and when it says SUPPORTED, would it have noticed a fault?**

## 2. Questions
- Q1 (yield). Among eligible pull requests with no CI verdict, what share gets SUPPORTED or CONTRADICTED from the replay, and what share stays UNKNOWN (and why)?
- Q2 (sensitivity). On the runs that ended SUPPORTED, how often does the replay stop a planted single-line fault (the existing `scripts/planted_faults.py` generator, control run first)?
- Q3 (precision). Of the pull requests the replay reports CONTRADICTED or as new test failures, how many are real by a deterministic adjudication (below)?

## 3. Population and procedure (frozen at commit)
- Source: the pull requests in `data/ci_study_outcomes.csv` with outcome `NO_CI` or `NO_TEST_JOB` and a `tests_pass` claim found by `agentvow.claims.extract` (so the CI-study sample frame is reused; its seed 2026 stays).
- Eligibility, from the repository's files at the pull request's own head commit (not the default branch; see `INCONCLUSIVE_CLASSIFICATION.md` for why): size under 300 MB; a `requirements*.txt` or a `pyproject.toml`/`setup.py` with no poetry, pipenv, uv-group or conda markers; at most 3 pull requests per repository. Eligibility is decided before any replay and the excluded count is reported.
- Target: 60 pull requests in at least 25 repositories, drawn in seed order from the eligible set. If fewer exist, the study reports the smaller n and does not relax the rules.
- Procedure: the shipped zero-config ladder, `agentvow` run **without** `--ci`, tests at base and head in the sandbox, shipped decision logic. Q2 uses `planted_faults.py` on the SUPPORTED runs only, control first (a fault is scored only if the unfaulted control passes), at most 3 faults per run.
- Free disk of at least 2.5 GiB is checked before each environment build (`envsetup.MIN_FREE`); a run that stops on this is a harness failure and is reported, not counted as UNKNOWN.

## 4. Adjudication for Q3 (no model labels)
A CONTRADICTED or new-failure result is **confirmed** when, on a rerun of the same states in a clean environment, at least one test fails at head, passes at base, three times in three, and the failing test imports or executes a file the pull request changed (coverage of the changed lines by that test, or a stack trace through a changed file). **Not confirmed** when the failure also occurs at base, is not stable, or the failing test touches no changed file. Cannot be decided is its own class. One annotator (the author); the rule above is mechanical so that a second reader would get the same class.

## 5. Decision rule (thresholds chosen by the author before data; the owner may change them before the freeze)
- **Keep the replay as a headline capability of the audit** only if all hold: Q1 yield (SUPPORTED plus CONTRADICTED, among eligible no-CI pull requests that did not stop on a harness failure) is **at least 40%**; Q2 detection on SUPPORTED runs is **at least 60%** of scored faults; Q3 confirmed share of CONTRADICTED and new-failure results is **at least 75%** with at least 4 such results, otherwise Q3 is reported as undetermined.
- If Q1 or Q2 fails: the replay is documented as an optional extra that reaches a verdict for a minority of pull requests (stated with the measured share), and the headline claim is narrowed to the receipt, UNKNOWN-as-an-outcome and authentication layer. If Q1 passes and Q2 fails, the SUPPORTED wording is weakened to "tests passed; planted faults were stopped in X%".
- No confidence interval is treated as significant: Wilson 95% intervals are reported and the rule is applied to point estimates, with the interval beside it. Repository clustering is reported (pull requests per repository), and the results are also given per repository.

## 6. Limits stated in advance
Public Python repositories from one agent dataset (AIDev) and one period; zero-config setup, so the yield is a floor for the intended use (a developer's own or an agent-captured environment, where setup is largely solved; the shadow-fault runs showed 91% usable B6 runs); planted faults are single-line, authored by us and not real defects; adjudication is mechanical but by one annotator; no human-reader study; a pass is evidence to weigh, not a safety verdict. The result says nothing about arbitrary repositories, other languages or the control plane.

## 7. What is not done here
No run has started as of the freeze. The first step after the freeze is a script `scripts/replay_value_run.py` reusing `detection_v2_run.py` and `planted_faults.py`, with the harness-failure rule above.

## Amendments
**Amendment 1 (2026-11-05, before any run; operational choices the frozen text left open, made while writing `scripts/replay_value_run.py`; thresholds and population rules unchanged):**
- A1.1 *Detection (Q2)*: a planted fault counts as **stopped** when the faulted head's tests_pass verdict is CONTRADICTED, or the runner reports at least one regression (a test that passed at base now fails). Faults are single-line behaviour mutants of changed non-test Python lines (at most 3 per run); every fault whose unfaulted control passed (the run itself ended SUPPORTED) is scored, including equivalent mutants, so the rate is a lower bound. Also reported, not part of the rule: the share of faults after which any test outcome changed (`oracle_break`).
- A1.2 *Adjudication (Q3)*: the rerun is three runs of the same head state in the same environment (not a rebuilt one); a regression is the set of failed test ids that passed at base; stable means the intersection of the three sets is not empty. "Touches a changed file" is a **static proxy**: the failing test's own file was changed, or it imports a module whose file the pull request changed (absolute, relative and `src/` layouts). No coverage run. A result with no regression in any run (for example a count mismatch) is `cannot_decide`.
- A1.3 *Yield (Q1)* counts SUPPORTED and CONTRADICTED only, as frozen; NOT_CONTRADICTED and UNKNOWN are reported separately and are not yield.
- A1.4 *Harness failures*: stages `harness_low_disk` and `error` are excluded from the yield denominator and listed; `env_failed`, `env_too_heavy`, `no_commits` and `clone_failed` are ordinary outcomes of the replay and stay in the denominator as no verdict.
- A1.5 *Selection*: candidates are the CI study's NO_CI / NO_TEST_JOB pull requests whose body has a tests_pass claim; ordered by `random.Random(2026).shuffle` of the (repo, number)-sorted list; eligibility from the root file listing and `pyproject.toml` at the pull request's head commit; repository size from the GitHub API at selection time (current, not at the commit).
