# Audit study, stage 1 results (2026-10-28)

Pre-registration: `AUDIT_STUDY_PREREG.md` (frozen at checker commit `6cf7f3b`, amendment A1: labelling agents instead of human readers). Labelling rules: `AUDIT_LABELLING_RULES.md`. Data: `docs/research/audit_data/` (items, both labelling passes, scores, agreement). Scripts: `research/audit/` (frozen), `research/audit_label/` (harness, scoring).

**What this is and is not.** Stage 1 scores what needs no execution of repository code: extraction (H6), files and documentation statements (part of H1), agreement between labellers, and what the labels themselves show. **Stage 2 was not run** (test, lint and impact verdicts; H4 reach; H5 reproducibility): see "What blocks stage 2". All numbers are "against evidence-grounded LLM labels", not human-validated; the labellers are Claude models (first pass Sonnet, second pass Opus), the same family as the author of the checkers, so shared blind spots are possible. Agreement between them is consistency, not independent verification.

## Flow
- Draw: 240 pull requests in 183 repositories (record in the pre-registration). Labelled: the first **150** in the seeded random order (a random subsample of the draw; the pre-registered minimum), **266 statements**, of which 218 are claims and 48 NOT_A_CLAIM. 90 drawn items were not labelled (budget, not selection).
- Broken items: 8 items are entirely unobservable (repository or pull request returns 404); their statements are CANNOT_TELL.
- Second pass: 30 items (20%, seeded), 62 statements, labelled blind by a different model. Every first-pass file validates; one file had a missing `}]` that was repaired mechanically without touching a label.

## Extraction (H6: at least 85% of extracted spans are real claims)
| kind | claims / extracted | point | 95% (Wilson) | 95% (cluster bootstrap by repository) | H6 |
|---|---|---|---|---|---|
| files_scope | 35 / 35 | 100% | 90 to 100% | 100% | holds |
| docs_updated | 26 / 27 | 96% | 82 to 99% | 88 to 100% | holds |
| lint_clean | 22 / 22 | 100% | 85 to 100% | 100% | holds |
| tests_pass | 33 / 38 | 87% | 73 to 94% | 74 to 97% | holds on the point estimate, interval wide |
| backward_compatible (impact) | 88 / 121 | 73% | 64 to 80% | 65 to 81% | **falsified** |
| unchecked | 10 / 18 | 56% | 34 to 75% | 33 to 78% | n/a (not a verdict kind) |
Most NOT_A_CLAIM spans are unticked template checkboxes and bare headings ("## Backward Compatibility"), the classes the labelling rules name. The new statement checkers (files, docs, lint) extract accurately; the older impact extraction does not.

## Files and documentation statements (part of H1)
Labels (claims): files_scope TRUE 26, FALSE 7, CANNOT_TELL 2; docs_updated TRUE 23, FALSE 1, CANNOT_TELL 2.
| check result | files_scope | docs_updated |
|---|---|---|
| raw CONTRADICTED (the product shows this as UNKNOWN + attention, "mismatch") | 3, all labelled FALSE | 0 |
| UNKNOWN | 3 (2 FALSE, 1 TRUE) | 4 (all TRUE) |
| NOT_CONTRADICTED | 26 (24 TRUE, 1 FALSE, 1 CANNOT_TELL) | 20 (19 TRUE, 1 FALSE) |
| not run (no usable change list) | 3 | 2 |
- **Precision of the mismatch flag, files_scope: 3 of 3** (Wilson 95%: 44 to 100%). By the pre-registered rule (lower bound below 80% withdraws a kind from CONTRADICTED) **files_scope is withdrawn from CONTRADICTED**; the product already keeps it attention-only, so nothing changes in behaviour. **docs_updated: no CONTRADICTED verdicts to evaluate.** H1 is therefore **not supported for any kind in stage 1**; with 3 flagged cases the data cannot say whether the precision is high or low.
- Of the 7 files statements labelled FALSE, the check surfaced 5 (3 flagged + 2 UNKNOWN) and missed 1 (the other had no usable change list). The one docs FALSE was missed (NOT_CONTRADICTED): "documentation updated" is satisfied by any changed documentation file, a documented limit.
- **Natural recall is not estimated**: only 21 reader-FALSE statements exist across all kinds (the rule needs at least 30).
- Seeded false statements (recall as pipeline sensitivity) were not generated in this stage.

## What the labels show about the claims themselves
- Of 218 claims, **88 (40%) are CANNOT_TELL** and 66 (30%) rest on the labeller's judgment. Reasons for CANNOT_TELL (keyword-classified from the labellers' notes, so approximate): not observable (author's own machine, opinion): 28; toolchain not installed (Zig, Go, Cargo, .NET, JDK, sbt): 17; repository or pull request gone (404): 14; installs or runs denied by the permission system: 13; no CI result or expired logs: 10; other: 6.
- Test claims: 24 of 33 are CANNOT_TELL, 9 TRUE, none FALSE. **These labels cannot evaluate the test check**, because labellers could rarely run the tests; that is a limit of this labelling, not a property of the audit.
- Impact claims ("backward compatible", "no breaking changes", 88 claims): TRUE 38, FALSE 12, CANNOT_TELL 38. Where a labeller could decide, 12 of 50 (24%) were judged contradicted from the diff, mostly by reading code. The product has no verdict for these in stage 1; a deterministic impact check exists for Python and was not run.
- Lint: TRUE 8, FALSE 1, CANNOT_TELL 13 (most are non-Python repositories).

## Labeller agreement (second pass, consistency only)
62 statements: 56 identical (90%), Cohen's kappa **0.86** overall. By kind: files_scope 11 of 11, docs_updated 9 of 9, impact 28 of 32 (kappa 0.83), unchecked 6 of 7, lint 1 of 2, tests 1 of 1. No kind with enough statements falls under the pre-registered kappa 0.6 line (lint has 2). Of the 6 disagreements, 5 are CANNOT_TELL against a definite label (the second labeller, a stronger model, settled more impact claims by reading code), and 1 is FALSE against CANNOT_TELL. The pre-registered requirement of at least 20% overlap is met (30 of 150 items; 23% of statements).

## Hypotheses at stage 1
| | status |
|---|---|
| H1 precision of CONTRADICTED | not supported; files_scope withdrawn from CONTRADICTED by rule (already attention-only); docs: nothing to evaluate; lint, tests, impact not scored |
| H2 UNKNOWN hides no obtainable answer | **not evaluated**; for files and docs there are 7 UNKNOWN verdicts, all of which a labeller settled (TRUE 5, FALSE 2); whether the tool could have settled them with its own mechanism was not assessed |
| H3 coverage between 15 and 40% | **not testable as designed**: the statements are exactly those the extractor found, so coverage is ~95% by construction; measuring it needs checkable statements identified independently of the extractor, which this design did not do. This is a design flaw, recorded |
| H4 reach | not run (stage 2) |
| H5 reproducibility | not run (stage 2) |
| H6 extraction precision | holds for files, docs, lint (and tests on the point estimate); **falsified for impact** (73%) |

## What blocks stage 2
Running the audit on test, lint and impact statements means installing and running third-party code. In this session the permission system denied many sandboxed installs (13 labels were affected) and the labellers' machine was nearly out of disk (about 3 GB free; two labellers hit ENOSPC). Stage 2 needs (1) an explicit decision from the owner to allow sandboxed installs and test runs of these open-source repositories, which the permission layer treats separately from the instruction already given, and (2) free disk space. Until then the study cannot say anything about test-claim correctness, lint, impact, reach or reproducibility.

## Limits
Evidence-grounded LLM labels, one family; 150 of 240 drawn items labelled; many CANNOT_TELL; judgment-flagged labels are 30%; Python-only checks are mostly outside the sample (half of the draw is Python by repository language, but most labelled claims concern other languages); the checker commit recorded by the draw script is `a328836` (identical frozen paths to `6cf7f3b`); no second human; seeded-falsehood recall not done. Results describe statements in these pull requests and say nothing about whether the software is correct or safe.

## What this means
The files, docs and lint extractors read pull-request descriptions accurately (96 to 100%), and their file-list checks surfaced 5 of 7 false file statements without a blocking false alarm in this sample, but 3 flagged cases are too few to claim a precision. The older impact extraction mis-reads a quarter of its spans. For the claims people most want checked (tests pass, no breaking change) the labels were mostly unobtainable without running code, which is exactly where the audit's runs are needed and where stage 2 has to be done.
