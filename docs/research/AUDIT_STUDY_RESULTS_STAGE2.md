# Audit study, stage 2 results (2026-10-28, revised after the adversarial review)

Pre-registration: `AUDIT_STUDY_PREREG.md` (frozen checker commit `6cf7f3b`; `agentvow/` and `research/audit/` were identical at run time). Runner: `research/audit_label/stage2_run.py`; scoring: `score_stage2.py`; data: `docs/research/audit_data/` (`stage2.jsonl` = the recorded run; `stage2_diag.jsonl` and `stage2_postfix.jsonl` = diagnostic re-runs, never mixed into the results). Stage 1 and its caveats: `AUDIT_STUDY_RESULTS_STAGE1.md`. Owner authorisation for sandboxed installs and test runs of these open-source repositories: 2026-10-28. Labels are evidence-grounded LLM labels (Claude), not human-validated.

## Corrections after the adversarial review (the first version of this document was wrong in these points)
1. **Pull request 003 was not tool-version drift.** I attributed the one wrong-looking lint flag to ruff 0.15.1 versus the pinned 0.12.9. The labeller's own note says the opposite: under 0.12.9 the same 25 findings exist in the `app/` files; the labeller scoped "ruff passes" to the repository's root pre-commit configuration (which excludes `app/`), the audit linted all 29 changed files. The audit's 25 findings in 29 files match. **It is a scope ambiguity, and under the literal reading the audit's CONTRADICTED is arguably correct.** That label is also marked `judgment=false` although its note admits a scope judgment. The foamlib#453 reference does not apply here.
2. **Join bug.** The first scorer kept only the last finding per statement. A statement can receive several (116 statement 1: `backward_compatible` NOT_CONTRADICTED, then `no_downstream_impact` CONTRADICTED; 131: four lint findings). The scorer now produces one row per statement under a stated aggregation (worst verdict) and, as a sensitivity, an "own kind" variant; both are reported. The aggregation rule was chosen after the first look; that is a disclosed deviation.
3. **Inconsistent counts fixed.** Impact is 46 statements (`backward_compatible` 45 plus `no_downstream_impact` 1) in 32 pull requests: CONTRADICTED 17, not 16; CANNOT_TELL 18 of 46; verdict produced 44 of 46.
4. **Pre-registered reporting rules.** Natural recall needs at least 30 labelled-false statements; there are 9, so recall is **not estimated** (I had reported "4 of 9" as recall). The pre-registered **miss rate of NOT_CONTRADICTED** is reported instead. The headline interval is the repository cluster bootstrap; both it and Wilson are given. The split by the labeller's `judgment` flag (A1.5) was omitted; it is added.
5. **The impact check was described wrongly.** It is not "a syntactic comparison of public names that cannot separate additive from breaking". It reports removed names, removed or renamed parameters, new required parameters, changed positional order and changed kind; additions are never counted. The count of changes is not a severity measure (moves and renames inflate it).
6. **A checker defect was found by this study** (see the next section).
7. **Lint UNKNOWN reasons were miscounted.** Three UNKNOWN lint verdicts, not four causes (below). **Test UNKNOWN causes were asserted without evidence** (below). **Environment-setup counts** the document omitted are added.

## A defect in the impact check, found by the study and fixed afterwards
For pull request 061 the four flagged statements all rest on one finding, "removed: ExecutorTypes". At the head commit `ExecutorTypes` is defined inside an `if sys.version_info >= (3, 14): ... else: ...` block; `api_diff.public_api` read only top-level statements, so a name moved into a version branch looked removed. Fixed after the study (`agentvow/api_diff.py` now also reads module-level `if`/`try`/`with` bodies, 4 new tests); re-running the check on 061 gives NOT_CONTRADICTED for all four statements, matching the TRUE labels. **This is a post-study change to the audited tool, reported separately; the pre-registered numbers below are from the frozen version.** The same re-run on 011 still flags `search_cases` (parameters removed or renamed: `tags`; `start_time`, `end_time`, `updated_after`, `updated_before`) while both labellers read the diff as compatible; whether the labels or the check are wrong there is **unresolved**.

## What ran
The frozen audit (`agentvow check --setup auto --run-tests --json`, the pull request's base sha from the cached pull-request record as `--base`, a fresh evidence home per run, one pull request at a time, clone deleted afterwards) on the **40 observable pull requests that change Python files and carry a tests, lint or impact claim**. All 40 ran to a result; median 27 seconds; status 23 INSUFFICIENT EVIDENCE, 15 REVIEW REQUIRED, 2 NO CONTRADICTION FOUND. **Whether an environment was built and tests were run cannot be derived from the record for most runs**: 6 runs print "automatic environment setup incomplete" (005, 013, 026, 039, 120, 142) and the others give no indication. The owner approved deleting stale test-fixture temp folders to make disk room (the disk floor never mattered during the run; minimum free 7.5 GB). 58 statements were joined (impact 46, lint 8, tests 4); none were dropped; no statement text repeats within a pull request.

## Impact statements (worst-verdict aggregation, one row per statement)
| audit verdict | labelled TRUE | labelled FALSE | CANNOT_TELL |
|---|---|---|---|
| CONTRADICTED (17) | 5 | 4 | 8 |
| NOT_CONTRADICTED (27) | 12 | 5 | 10 |
| UNKNOWN (2) | 2 | 0 | 0 |
- **Precision of CONTRADICTED: 4 of 9 decisive flags (44%; Wilson 95% 19 to 73%; repository cluster bootstrap 13 to 100%).** Own-kind variant: 3 of 8 (14 to 69%). By pull request: 4 of 6 (30 to 90%); own kind 3 of 5. Four of the five wrong flags are one pull request (061, the defect above).
- **Miss rate of NOT_CONTRADICTED: 5 of 17 decisive (29%; Wilson 13 to 53%)**; own kind 6 of 18. NOT_CONTRADICTED is not support: nearly a third of the decisive "no contradiction" statements were labelled false.
- **Judgment split (A1.5).** Of the 9 decisive flags, 5 have non-judgment labels and 4 of those are right (80%; Wilson 38 to 96%); the 4 judgment-labelled flags are all labelled TRUE (0 right). The conclusion "CONTRADICTED is unreliable" therefore leans on judgment labels; the pre-registered withdrawal rule (lower bound below 80%) still holds on the non-judgment subset alone.
- The one correct flag in 116 comes from a **different check** (the import-graph "102 modules depend on what changed"), not from the labeller's reason (a settings-caching regression); under the own-kind variant it is a miss.
- 85's 226 "changes" are plausibly moved or renamed files counted as removals (not verified).
- Statements with a verdict: 44 of 46. This is near-trivial for a static check that answers NOT_CONTRADICTED whenever no removal is found; read it as "produces some verdict", not "can verify".

## Lint statements
8 statements: NOT_CONTRADICTED 3 (all TRUE), UNKNOWN 3 (2 TRUE, 1 CANNOT_TELL), CONTRADICTED 2 (1 FALSE, 1 TRUE: pull request 003, see correction 1). Too few to evaluate (7 decisive labels).
UNKNOWN causes: **005** ruff exited with status 2 and 20 other pre-commit hooks could not run (and the setup printed "project too large to copy"); **131** no runner for isort and 4 other hooks not run (black and flake8 were clean); **155** the change edits lint configuration, so a clean result is distrusted by design. Two of the three are design and policy limits, not environment failures.

## Test statements (H4)
4 statements in 3 repositories, **all UNKNOWN**; labels 3 TRUE, 1 CANNOT_TELL. The recorded reasons: two statements (062 and 151, the same repository, meta-agent) report `ModuleNotFoundError ... 'pytest_asyncio' is not a package`, which suggests a name shadowing in the repository rather than a missing install; two (129, 144) report a missing dependency "in Agentvow's environment" although `--setup auto` was passed and no setup-incomplete line was printed. **The cause cannot be separated into audit-side and repository-side from the stored fields** (scope and stderr were truncated), so I do not attribute it to the audit's environment. The labellers settled their TRUE labels mainly from the repository's CI check-runs, which the audit does not read. H4 is untestable: 1 test claim is in a Python-language repository.

## Hypotheses at stage 2
| | status |
|---|---|
| H1 precision of CONTRADICTED | impact: **withdrawn from CONTRADICTED by the pre-registered rule** (28 decisive labels; Wilson lower bound 19%, or 38% on the non-judgment subset, both below 80%; also under the own-kind variant); lint: too few; tests: no CONTRADICTED verdicts; files: withdrawn at stage 1 |
| H2 UNKNOWN hides no obtainable answer | not run as pre-registered (no "answerable from the material the tool had" flag was built); labeller-settled UNKNOWN: tests 3 of 3 (from CI the tool does not read), impact 2, lint 2 of 3 |
| H3 coverage | not testable as designed (stage 1) |
| H4 reach | untestable (see above); tests 0 of 4, lint 5 of 8, impact 44 of 46 |
| H5 reproducibility | not run (no second machine; run-to-run determinism on this machine was not checked either) |

## What this means for the product
- The impact check's CONTRADICTED should be a prompt for a person to look, not a finding that a claim is false: precision 4 of 9 (3 of 8) on 6 pull requests, a recall-side miss rate of 29%, one defect found and fixed (conditional definitions), and one unresolved disagreement (011). The pre-registered rule says to withdraw it from CONTRADICTED. The owner decided (2026-10-28) to make it attention-only; this is done on `main` (`decision._compat` returns UNKNOWN with attention and a mismatch flag; tests updated) and is a post-study change to the audited tool. `no_downstream_impact` still issues CONTRADICTED from an import graph and has only one evaluated case.
- The lint check behaves as designed; its one disagreement with a labeller is a scope question the audit answered literally.
- Tests: the audit could not produce a verdict on any of the four test claims, and the cause is not established.

## Limits
40 pull requests, 58 statements (9 decisive impact flags from 6 pull requests); evidence-grounded LLM labels from one model family (31% judgment labels in stage 1; 18 of 46 impact statements CANNOT_TELL); the aggregation rule was chosen after the first look; the base sha is the pull-request record's base-branch tip at snapshot time, not a merge-base, and the labellers' base and head were not compared with the audit's; `git fetch pull/N/head` return codes were not checked; one machine, one run each; the tests and lint checks are Python-only and 40 of 150 pull requests change Python files. Results describe these pull requests and say nothing about whether software is correct or safe.
