# Audit study, stage 1 results (2026-10-28, revised after the adversarial review)

Pre-registration: `AUDIT_STUDY_PREREG.md` (frozen at checker commit `6cf7f3b`, amendment A1: labelling agents instead of human readers). Labelling rules: `AUDIT_LABELLING_RULES.md`. Data: `docs/research/audit_data/`. Scripts: `research/audit/` (frozen), `research/audit_label/` (harness, scoring, agreement, breakdown).

**What this is and is not.** Stage 1 scores what needs no execution of repository code: extraction (H6), the files and documentation statements (part of H1), labeller agreement, and what the labels show. **Stage 2 was not run** (test, lint and impact verdicts, H4 reach, H5 reproducibility). All numbers are "against evidence-grounded LLM labels", not human-validated; the labellers are Claude models (first pass Sonnet, second pass Opus), the same family as the author of the checkers, so shared blind spots are possible, and agreement between them is consistency, not independent verification.

## Corrections made after the adversarial review (the first version of this document was wrong in these points)
1. **The scorer was not running the shipped file check.** It used a stand-in repository object, so `statements._exists` always answered "does not exist": a "removed X" claim about a file that still exists could never be flagged. The same stand-in was used in the earlier five precision rounds on real descriptions (`CHECKERS_FILES_DOCS_LINT.md`): those rounds under-counted this one class of contradiction (recall), not the precision of what was flagged. Fixed: the scorer now builds a real directory holding every file of the pull request's head tree. One residual difference remains: `_ignored` is stubbed (a git-ignored path would be UNKNOWN in the product but can be CONTRADICTED here). The pull request with an empty change list (which the old scorer skipped) is now run and is a correct flag.
2. **Unobservable items.** The first version kept 8 pull requests whose repository or pull request returns 404. The pre-registration says such items are replaced by the next draw. I re-checked the 8: **7** are truly unobservable (the eighth was a keyword false positive). Those 7 are now excluded and replaced by the next 7 items in the seeded order (items 150 to 156). Everything below uses the resulting **150 observable pull requests**.
3. **Minimum-size rules are met only under a favourable reading.** The pre-registered floor is "150 pull requests and 250 labelled statements". There are 150 pull requests and **263 statements, but only 215 are claims** (48 are NOT_A_CLAIM spans, which were also labelled). Counting spans, the floor is met; counting claims, **it is not (215 < 250)**, and the clause then says "mechanics only". Treat H1 to H6 below as **non-binding** unless you accept the span reading.
4. **Ordering deviation.** The prereg says labelling order is SHA-256(seed|item id); the packager used SHA-256(seed|pull-request URL). Both give a random order (only 92 of the first 150 coincide); the deviation was not recorded and is now.
5. **Agreement was inflated by easy cases.** NOT_A_CLAIM agreed in 12 of 58 statements. Claims-only agreement is reported below. The A1 rule "disagreement defaults to CANNOT_TELL" was **not applied**: all tables use first-pass labels. The pre-registered 10% intra-labeller re-label after seven days was **not run**.
6. **Wrong sentence removed:** "most labelled claims concern other languages" was false (116 claims are in Python-language repositories, 99 in others); it is true only of test claims (see the Python table).
7. **Wording corrected:** "5 of 7 false file statements surfaced" mixed detection with ambiguity (see the files section); "holds" for tests extraction rested on a point estimate; the CANNOT_TELL reason counts are now produced by a committed script with a stated order of precedence.
8. **Reproducibility of choices:** the second-pass sample is reproduced by `research/audit_label/second_pass.py` (it matches the recorded list); the one repaired label file was `004_fbb7308b52.json` (a missing `}]`, no label touched).
9. **Temporal validity (disclosed, not fixed):** the labellers and the scorer use each pull request's current head and final file list from the GitHub API, while the description may have been written at an earlier commit; a "FALSE" about files can reflect later commits.

## Flow
Drawn 240 pull requests in 183 repositories; labelled the first 157 in the seeded order; 7 unobservable ones excluded; **150 pull requests, 263 statements, 215 claims, 48 NOT_A_CLAIM**. Second blind pass (different model) on the seeded 20% of the first 150 (30 items), of which 29 are observable: 58 statements.

## Extraction (H6: at least 85% of extracted spans are real claims; pre-registered headline interval is the repository cluster bootstrap)
| kind | claims / spans | point | Wilson 95% | cluster bootstrap 95% | reading |
|---|---|---|---|---|---|
| files_scope | 34 / 34 | 100% | 90 to 100% | n/a (all successes) | holds on the point estimate |
| docs_updated | 24 / 25 | 96% | 81 to 99% | 86 to 100% | holds |
| lint_clean | 23 / 23 | 100% | 86 to 100% | n/a (all successes) | holds on the point estimate |
| tests_pass | 36 / 41 | 88% | 74 to 95% | 76 to 98% | point estimate above 85%, bootstrap lower bound below: **not shown** |
| impact (backward_compatible + no_downstream_impact) | 88 / 122 | 72% | about 63 to 79% | about 63 to 80% | **falsified** |
| unchecked | 10 / 18 | 56% | 34 to 75% | 33 to 79% | n/a (not a verdict kind) |
Most NOT_A_CLAIM spans are unticked template checkboxes and bare headings, the classes the labelling rules name.

## Files and documentation statements (part of H1)
Labels (claims): files_scope TRUE 26, FALSE 7, CANNOT_TELL 1; docs_updated TRUE 23, FALSE 1.
| check result (shipped logic, real tree) | files_scope | docs_updated |
|---|---|---|
| raw CONTRADICTED (the product shows this as UNKNOWN + attention, a "mismatch") | 4, all labelled FALSE | 0 |
| UNKNOWN | 3 (2 FALSE, 1 TRUE) | 4 (all TRUE) |
| NOT_CONTRADICTED | 26 (24 TRUE, 1 FALSE, 1 CANNOT_TELL) | 20 (19 TRUE, 1 FALSE) |
| not run | 1 | 0 |
- **Precision of the mismatch flag, files_scope: 4 of 4** (Wilson 95%: 51 to 100%). By the pre-registered rule (lower bound below 80% withdraws a kind from CONTRADICTED) **files_scope is withdrawn from CONTRADICTED**; the product already keeps it attention-only. The rule is applied on the Wilson bound; the other withdrawal clause (fewer than 20 CONTRADICTED with precision below 90%) does not trigger. **docs_updated: no CONTRADICTED verdicts.** H1 is **not supported for any kind**. Caveat on two of the flags: one labeller noted the change "may be in other repositories" (a monorepo reading) for pull request 137; one flag is a pull request with no changed files at all.
- Of the 7 files statements labelled FALSE: 4 flagged; 2 UNKNOWN **for name ambiguity** ("several files have this name"), which is not detection of falsity; 1 missed (NOT_CONTRADICTED). The one docs FALSE was missed: "documentation updated" is satisfied by any changed documentation file, a documented limit.
- **Natural recall is not estimated**: 21 reader-FALSE statements across all kinds (the rule needs 30). Seeded false statements were not generated.

## What the labels show about the claims
- Of 215 claims, **82 (38%) are CANNOT_TELL** and 66 (31%) rest on judgment.
- Reasons for CANNOT_TELL by a keyword heuristic (`breakdown.py`; first match wins in a stated order; approximate): not observable (author's machine, opinion, hedge) 32; toolchain not installed (Zig, Go, Cargo, .NET, JDK, sbt) 18; installs or runs denied by the permission system 15; no CI result or expired logs 9; no keyword matched 6; disk full 2. The harness-related reasons (toolchain, permission, disk, CI) account for roughly half; they are limits of this labelling, not properties of the audit, and the categories can overlap in truth.
- Tests: 36 test claims, **26 CANNOT_TELL, 10 TRUE, none FALSE.** These labels cannot evaluate a test check.
- Impact (84 backward_compatible claims plus 4): TRUE 42, FALSE 12, CANNOT_TELL 34; where a labeller decided, 12 of 54 (22%) were judged contradicted from the diff. No product verdict for them in stage 1.
- Lint: TRUE 10, FALSE 1, CANNOT_TELL 12.

## Python and the tests/lint checks
Claims by repository-language stratum (Python / other): files_scope 26/8, docs_updated 17/7, lint_clean 14/9, impact 50/38, **tests_pass 1/35**, unchecked 8/2; all 116/99. Almost every test claim is in a non-Python repository (a limitation of the corpus: the Python-stratum draw rarely contains a test claim). **H4 (reach in plain-pip repositories) has essentially no material (1 test claim in a Python repository)**; lint claims are 14 of 23 in Python repositories.

## Labeller agreement (second pass; consistency only)
29 observable items, 58 statements: 52 identical (90%), Cohen's kappa 0.85; **claims only** (dropping the 12 statements both called NOT_A_CLAIM): 40 of 46 (87%), kappa **0.78**. By kind: files_scope 11 of 11, docs_updated 9 of 9 (kappa undefined, all agree), impact 26 of 30 (kappa 0.82), unchecked 4 of 5, lint 1 of 2, tests 1 of 1. The kappa < 0.6 withdrawal rule cannot trigger for lint, tests or docs (too few or degenerate). Disagreements: 6, of which 5 are CANNOT_TELL against a definite label (the stronger second labeller settled more impact claims by reading code) and 1 is FALSE against CANNOT_TELL. Overlap: 29 of 150 items (19%); by statements 58 of 263 (22%), at the edge of the pre-registered 20% (a further reason to treat the results as non-binding).

## Hypotheses at stage 1
| | status |
|---|---|
| H1 precision of CONTRADICTED | not supported; files_scope withdrawn by the Wilson rule (already attention-only); docs: nothing to evaluate; lint, tests, impact not scored |
| H2 UNKNOWN hides no obtainable answer | not evaluated (7 files/docs UNKNOWN verdicts, all settled by a labeller; whether the tool could have settled them was not assessed) |
| H3 coverage 15 to 40% | not testable as designed: the statements are the extractor's own, so "coverage" is near 100% by construction, and the "with a verdict path" count includes impact and tests, which have no stage 1 verdict |
| H4 reach | no material (1 test claim in a Python repository); stage 2 not run |
| H5 reproducibility | not run |
| H6 extraction | files, docs, lint hold on point estimates; tests not shown; **impact falsified** |

## What blocks stage 2
Running the audit on test, lint and impact statements means installing and running third-party code. The permission system denied many sandboxed installs during labelling (15 labels affected) and the machine had about 3 GB free (two labellers hit ENOSPC). Stage 2 needs the owner's explicit decision to allow sandboxed installs and test runs of these open-source repositories, and free disk space.

## Limits
Evidence-grounded LLM labels, one family; 150 observable pull requests; many CANNOT_TELL; 31% judgment labels; the minimum-statement floor met only by counting spans; ordering and overlap deviations; a stubbed ignore check; temporal validity; the second-pass sample is 20 Python / 10 other by repository language (chance, not designed); seeded-falsehood recall and the intra-labeller re-label were not done. Results describe statements in these pull requests and say nothing about whether the software is correct or safe.

## What this means
The files, docs and lint extractors read pull-request descriptions accurately (96 to 100% on point estimates), and the file-list check flagged 4 false file statements with no false flag, but four flags are too few to claim a precision, and the labels cannot evaluate the claims that matter most (tests, no breaking change) because they could mostly not be run. The older impact extraction mis-reads about a quarter of its spans. The next evidence needs stage 2.
