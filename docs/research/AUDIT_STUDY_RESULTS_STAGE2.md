# Audit study, stage 2 results (2026-10-28)

Pre-registration: `AUDIT_STUDY_PREREG.md` (frozen checker commit `6cf7f3b`; the `agentvow/` and `research/audit/` paths were identical at run time). Runner: `research/audit_label/stage2_run.py`; scoring: `score_stage2.py`; data: `docs/research/audit_data/stage2.jsonl` and `data/audit/score_stage2.json`. Stage 1 results and their caveats: `AUDIT_STUDY_RESULTS_STAGE1.md`. Owner authorisation for sandboxed installs and test runs of these open-source repositories: 2026-10-28. All labels are evidence-grounded LLM labels (Claude), not human-validated.

## What ran
The frozen audit (`agentvow check --setup auto --run-tests --json`, the pull request's base commit as `--base`, a fresh evidence home per run, one pull request at a time, clone deleted afterwards) on the **40 observable pull requests that change Python files and carry a tests, lint or impact claim** (of 150). All 40 ran to a result; none timed out; median 27 seconds. Run status: 23 INSUFFICIENT EVIDENCE, 15 REVIEW REQUIRED, 2 NO CONTRADICTION FOUND. To make room the owner approved deleting stale test-fixture temp folders; the product's own disk floor and sandbox were not changed.

58 claim statements were joined to labels (impact 46, lint 8, tests 4). The per-statement numbers below count each statement; several statements in one pull request often receive the same finding, so a per-pull-request count is given where it matters.

## Impact statements ("backward compatible", "no breaking changes"): the audit's CONTRADICTED is not reliable
| audit verdict | labelled TRUE | labelled FALSE | CANNOT_TELL |
|---|---|---|---|
| CONTRADICTED (16) | 5 | 4 | 8 |
| NOT_CONTRADICTED (27) | 12 | 5 | 10 |
| UNKNOWN (2) | 2 | 0 | 0 |
- **Precision of CONTRADICTED: 4 of 9 decisive flags (44%; Wilson 95%: 19 to 73%).** By pull request: 6 pull requests with a decisive flag, 4 right (67%; Wilson 30 to 90%). Five of the nine decisive flags are statements labelled TRUE; **four of those five are one pull request (061) whose four statements received the same finding**, so the effective number of independent wrong flags is 2 pull requests.
- **Recall of labelled-FALSE impact statements: 4 of 9** (the audit missed 5; they are NOT_CONTRADICTED). Eight further CONTRADICTED flags have no decisive label (CANNOT_TELL), so their correctness is unknown.
- **Reach: 43 of 45 impact statements got a verdict** (the check is static and needs no environment).
- The check reports "the public API changed in N ways" (a syntactic comparison of public names); whether that is breaking is a judgment (4 of the 9 decisive flagged labels are judgment-labelled). The flagged counts run from 1 to 226 changes, so the verdict does not separate additive from breaking changes.

## Lint statements
8 statements: NOT_CONTRADICTED 3 (all labelled TRUE), UNKNOWN 3, CONTRADICTED 2 (1 FALSE, 1 TRUE).
- The wrong flag (pull request 003) is **tool-version drift**: the audit ran ruff 0.15.1 and found 25 findings, while the labeller ran the version the repository pins (0.12.9) with its configuration and found none. The audit states the version and warns that another version may disagree (the foamlib#453 lesson), so this is the documented failure mode, not a surprise.
- Reach 5 of 8: the UNKNOWN cases are a configured ruff that exited with an error, a pre-commit run where 20 other hooks could not run, and two cases where the change edits lint configuration or the tool reports nothing on a one-file change.

## Test statements (H4)
4 statements: **all UNKNOWN (reach 0 of 4)**; the labellers labelled 3 TRUE and 1 CANNOT_TELL. The audit's reasons: the test run was inconclusive with `ModuleNotFoundError` or a missing dependency in the audit's own environment. The labellers settled the three TRUE labels mainly from the repository's own CI check-runs, material the audit does not read, so this is a difference in evidence source, not an answer the audit could have given. **H4 cannot be tested**: only 1 test claim is in a repository whose language is Python, and the 4 test claims here are all UNKNOWN.

## Hypotheses at stage 2
| | status |
|---|---|
| H1 precision of CONTRADICTED | **impact: lower bound 19% (statements) or 30% (pull requests), far below 80%: by the pre-registered rule impact is withdrawn from CONTRADICTED** (kept as attention only). lint: 2 flags, too few. tests: none. files: withdrawn at stage 1 |
| H2 UNKNOWN hides no obtainable answer | tests: 3 of 3 UNKNOWN were settled by a labeller, but from CI logs the tool does not read, so not "material the tool had"; impact: 2 UNKNOWN, both labelled TRUE; lint: 2 of 3 UNKNOWN labelled TRUE. Not a clean test; the honest reading is that the audit is UNKNOWN on a majority of tests and lint cases for environment reasons |
| H3 coverage | not testable as designed (stage 1) |
| H4 reach | not testable (1 test claim in a Python repository); reach for tests 0 of 4, lint 5 of 8, impact 43 of 45 |
| H5 reproducibility | **not run**: no second machine; run-to-run determinism on this machine was not checked either |

## What this means for the product
- The impact check's CONTRADICTED is, on this evidence, a prompt for a person to look, not a finding that a claim is false. The pre-registered rule says to withdraw it from CONTRADICTED. Today `backward_compatible` CONTRADICTED is a full CONTRADICTED verdict under the default policy; making it attention-only is a product change that needs your decision (it would modify the frozen paths after the study, which is allowed once results are in).
- The lint check behaves as designed; its disagreement with a labeller was version drift that the audit itself warns about.
- Tests: on these pull requests the audit could not run the tests in its own environment. That is the reachability limit already measured elsewhere (UNKNOWN is the stable outcome outside plain-pip repositories).

## Limits
40 pull requests, 58 statements; small counts per verdict class (a decisive impact flag is 9 statements from 6 pull requests); evidence-grounded LLM labels from one model family with 31% judgment labels (stage 1) and many CANNOT_TELL (18 of 45 impact statements); the audit ran on the head of the current pull request (temporal validity as in stage 1); one machine, one run each; the audit's environment differs from the labellers' (versions, CI access); the tests/lint checks are Python-only and only 40 of 150 pull requests change Python files. Results describe these pull requests and say nothing about whether software is correct or safe.
