# CI-claim study: do agents' "tests pass" claims hold? (pre-registration, written 2026-10-07 before the full run)

## Questions
- RQ1. Among agent-authored PRs that claim tests pass, how often do the project's own CI test jobs on the PR head commit contradict the claim, support it, or give no usable evidence?
- RQ2. Does this differ by agent, and by merged vs unmerged?
- RQ3. How often would Agentvow's CI evidence path (`ci.py`) give a verdict at all (coverage)?
- RQ4 (validation of our classifier). How precise is the name-based test-job classification?

## Population and sampling
AIDev-pop (`hao-li/AIDev` v4) pull requests in repositories whose language is Python, with a non-empty body, where the current claim extractor finds a `tests_pass` claim (`agentvow.claims.extract`). Stratified random sample (seed 2026): up to 300 PRs per agent (Claude_Code, Copilot, Devin, Cursor, Google_Jules, OpenAI_Codex), whatever exists if fewer. Previously examined 150-PR pilot sample (seed 7) is not reused for estimates.

## Data collection (frozen)
Read-only GitHub API through `gh`: PR (head SHA, commit count, merged, state) and check-runs for the final head SHA (per_page=100; PRs with more runs than one page are excluded and counted as `truncated`). Legacy commit statuses are not read (limitation).

## Outcome definitions (applied at analysis time to stored job names, so the classifier can be audited without refetching)
A job is a *test job* if its name matches `\b(tests?|pytest|unit|unittests?|integration|tox|nox|specs?)\b` (case-insensitive). Completed jobs with conclusion neutral/skipped are ignored.
- CONTRADICTED: at least one test job failed, timed out, was cancelled or required action.
- SUPPORTED: no test job failed and at least one test job succeeded.
- NO_TEST_JOB: check-runs exist but none is a test job.
- NO_CI: no check-runs.
- (excluded) ERROR/TRUNCATED.
*Judgeable* = CONTRADICTED or SUPPORTED.

## Analysis plan
Report counts and Wilson 95% CIs: share of each outcome overall and by agent and merged status; CONTRADICTED rate among judgeable PRs. Sensitivity analyses (declared now): (a) single-commit PRs only (the claim most likely describes the head), (b) excluding cancelled/timed-out. No other subgroup cuts will be presented as findings.

## Known threats (declared now)
The PR body may predate later commits; CI failures can be flaky or environmental (not the agent's fault); job-name heuristic misclassifies; CI that does not run tests; PRs where CI needed human approval (Copilot cloud agent: no runs = NO_CI, not evidence of anything); public repos only, popularity-biased; AIDev time window (Dec 2024-Jul 2025 for the PRs analysed in related work) and tool versions then. One annotator for RQ4.

## RQ4 procedure
Draw 60 random distinct (job name, classified-as-test or not) pairs, judge each from the name alone as test/not-test before seeing the classifier output; report agreement. Single annotator: indicative only.

---
# Results (run 2026-10-07; `scripts/ci_study.py`, `scripts/ci_study_analyze.py`; data local in `data/`)

Population: 923 Python AIDev-pop PRs with a tests-pass claim (Copilot 514, Devin 200, Claude Code 101, Cursor 66, Codex 40, Jules 2). Sample = 709 (300-per-agent cap; the small strata exhausted). 21 excluded (18 PR lookup errors, 3 truncated) → n = 688 PRs in 221 repositories.

## RQ1 (pre-registered classifier v1; Wilson 95% CI, PRs treated as independent, see clustering caveat)
| outcome | share of 688 |
|---|---|
| CONTRADICTED (a test job failed on the head commit) | 62 = 9.0% [7.1, 11.4] |
| SUPPORTED | 164 = 23.8% [20.8, 27.2] |
| NO_TEST_JOB (CI exists, no test-named job) | 96 = 14.0% [11.6, 16.7] |
| NO_CI | 366 = 53.2% [49.5, 56.9] |
Judgeable 226 = 32.8%; **CONTRADICTED among judgeable: 62/226 = 27.4% [22.0, 33.6]**.
Sensitivity (a) single-commit PRs (n=117): 27/45 = 60.0% contradicted among judgeable [45.5, 73.0] (small, wide). (b) treating cancelled/timed-out as non-failures: 56/224 = 25.0% [19.8, 31.1].
Post-hoc, classifier v2 (see RQ4): contradicted 66/234 = 28.2% [22.8, 34.3] among judgeable; judgeable 34.0%.

## RQ2 (by agent and merge status): descriptive only, NOT interpretable as an agent comparison
Contradicted among judgeable (v1): Claude Code 7/37 (19%), Copilot 17/118 (14%), Cursor 21/35 (60%), Devin 15/32 (47%), Codex 2/4. **But PRs cluster in a few repositories:** 55% of all contradicted PRs come from 3 repos (litellm 20, crewAI 11, foamlib 3); 77% of Cursor's judgeable PRs are litellm, 78% of Devin's are crewAI. Differences by agent are therefore mostly repository effects. Repo-level: 80 repos have judgeable PRs; 29 (36%) have at least one contradicted PR. Merged vs unmerged: contradicted 44/94 (47%) unmerged vs 18/132 (14%) merged; the gap persists within the 14 repos having both (20/37 vs 11/56) but is confounded by reverse causation (PRs with failing CI tend to be abandoned) and does not show that claims were false when written.

## RQ3 (coverage of the CI evidence path)
About one third (33-34%) of claiming PRs get a verdict from test-named CI jobs; **53% have no CI at all** and 13-14% have CI without a recognisable test job. For these a local test run is the only way to check the claim.

## RQ4 (classifier audit; one annotator, blind to classifier output; names judged from the name alone)
v1 on 60 random distinct job names: agreement 44/60, precision 20/22, recall 20/34 (misses: matrix names such as "Python 3.8", underscores/digits hiding the word, project-specific names). v2 was written *after* seeing those results (post-hoc, token-aware + python-version matrix names + test.pypi exclusion). v2 on a **fresh** 60 names (not used for tuning): precision 22/23, recall 22/26 (v1 on the same names: 18/19, 18/26). Remaining misses are project-specific (`pl-cpu ...`).

## What this does and does not show
- Shows: in public agent PRs where the author says tests pass, a failing test job on the final head commit is common (about 1 in 4 of those that CI can judge) and most claims cannot be checked by CI at all.
- Does not show: that agents misreport more or less than humans (no human baseline here), a ranking of agents, or that any individual claim was false when made (the body may predate later commits; flaky and environmental failures; single-commit sensitivity is small).
- Wilson intervals assume independent PRs and are too narrow given repository clustering; a cluster-robust analysis (by repository) is future work.
- v1 results are the pre-registered primary; v2 results are post-hoc.
