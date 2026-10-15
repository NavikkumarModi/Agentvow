# Real-bug replay: plan and feasibility stage

Status: feasibility stage only. Written 2026-10-15 before any run. The confirmatory protocol is NOT frozen here; it is frozen only after the feasibility results, and only if the stop rule below is not triggered.

## 1. Question and a design problem that changes the primary outcome

Proposed question: does coverage look reassuring about the code changed by a real fix even though the pre-existing suite did not detect the original defect?

Problem: a historical bug fix is a bug that escaped. The suite at the buggy commit normally passed on the buggy code (otherwise the bug would not have been committed or released). So "the pre-existing suite does not detect the original bug" is true by construction for almost every instance, and the proposed primary outcome (the proportion of covered fixes whose defect stays undetected) would be close to 100% whatever coverage means. A near-100% figure would say nothing about coverage.

Outcome that is not degenerate: among real escaped defects, in what share were the lines the fix changed (measured on the buggy version) executed by the pre-existing suite at all? That is the share of real escapes a changed-line-coverage signal would have called "covered" while the defect escaped, i.e. how often coverage reassurance was available and wrong. Detection is reported alongside as a check: how many instances the pre-existing suite already fails on the buggy source (expected near zero).

What this can and cannot show: it measures how often coverage reassurance is wrong on real defects. It does not show that mutation testing would have caught them. A mutation arm (does a generated mutant on the fixed lines reproduce the escaped behaviour) is a separate, larger step and is not part of this stage.

## 2. Source and eligibility

BugsInPy (17 Python projects, buggy and fixed commits, bug patch, test command). Excluded before screening for cost or environment reasons, listed so the choice is visible: pandas, matplotlib, keras, spacy, ansible (compiled or very heavy environments). Remaining 12 projects: PySnooper, black, cookiecutter, fastapi, httpie, luigi, sanic, scrapy, thefuck, tornado, tqdm, youtube-dl.

Sample for the screen: up to 6 bugs per project, seeded random (seed 20261015), over the remaining projects.

## 3. Feasibility record (no coverage and no coverage-vs-detection association is computed in this stage)

For each bug: commits fetchable; changed non-test source files and changed-line count from the bug patch; whether the revealing test existed before the fix; environment built (interpreter, requirement install result); the pre-existing suite (tests at the buggy commit) run on the buggy source and on the fixed source (bug patch applied to the buggy tree, so tests are identical); pass/fail counts, failures that differ between the two; time.

Runs: network off, same sandbox as the earlier studies, suite cap 300 s, environment build cap 600 s. Interpreter available locally: 3.11 and 3.13 only. Instances needing 3.7 or 3.8 are tried on 3.11 and failures are classified, not hidden.

## 4. Stop rule (set now)

Feasible instance = environment built, suite runs on both trees with a finished baseline, and fixed-source baseline has at least 1 passing test. Proceed to a frozen confirmatory protocol only if there are at least 30 feasible instances in at least 5 projects, with no project above 40% of them. Otherwise stop and report the bounded mutation result. If the shortfall is only the missing 3.7/3.8 interpreters, ask the user before downloading one rather than stopping.

## 5. Feasibility results (2026-10-15)

Sample: 65 bugs (seeded; PySnooper has only 3). Harness: `research/preconditions/realbug_feasibility.py`; records in `data/preconditions/realbug_feasibility.jsonl`. Interpreter: Python 3.11 only. One harness bug was found and fixed during the run: BugsInPy's youtube-dl metadata writes `fixed_commit_id ="..."` with a space, which my parser rejected, so its 6 bugs were re-run after the fix (the first 6 records were discarded). Nothing else was changed after seeing results.

| Project | Bugs screened | Feasible by the section 4 definition | Pinned requirements failed to install on 3.11 |
|---|---|---|---|
| PySnooper | 3 | 0 | 0 (code fails to import on 3.11: `collections.Mapping`) |
| black | 6 | 0 | 6 |
| cookiecutter | 4 | 0 | 4 |
| fastapi | 6 | 0 | 6 |
| httpie | 5 | 0 | 5 |
| luigi | 6 | 0 | 6 |
| sanic | 5 | 0 | 5 |
| scrapy | 6 | 0 | 6 |
| thefuck | 6 | 0 | 3 |
| tornado | 6 | 1 | 0 |
| tqdm | 6 | 0 | 6 |
| youtube-dl | 6 | 6 | 0 |
| Total | 65 | 7 | 47 |

Stop rule (at least 30 feasible instances in at least 5 projects, none above 40%): NOT met. 7 feasible instances in 2 projects; youtube-dl is 6 of the 7 (86%).

Quality of the 7: all are weak. Their fixed-source baselines still contain many failing tests (youtube-dl 43-54 failures of about 1,300-2,200, mostly network-dependent; youtube-dl bug 41 fails 330 of 406; tornado bug 15 has 86 failures and 465 errors). Under the plan's own rule for already-failing suites these would be reported separately, so the usable count is lower still.

Causes of the other 58: pinned requirements that do not install on 3.11 (47), code that does not import on 3.11 (PySnooper, thefuck, 3 tornado bugs), two tornado suites that exceed the 300 s cap, and luigi tests that need to bind a local socket, which the network-off sandbox forbids (a harness limitation, separate from the interpreter).

Detection check (allowed in this stage): among the 7 feasible instances no test fails on the buggy source and passes on the fixed source (0 of 7), consistent with the by-construction argument in section 1.

Reading: the shortfall is mostly the missing 3.7/3.8 interpreters, but that is an inference. The 47 failed installs were not diagnosed individually, and the luigi socket problem would remain on an old interpreter. Whether the study is feasible on era-appropriate interpreters is untested.

Decision needed from the user: download Python 3.7 and 3.8 (for example via `uv python install`, standalone builds from GitHub, a few hundred MB), re-run this same screen, and apply the same stop rule; or stop here and publish the bounded mutation result. No coverage-vs-detection analysis has been run.

## 6. Second feasibility screen: era interpreters (frozen 2026-10-15, before it is run)

Authorised by the user in chat after section 5. Scope frozen here:

- Same 65 bug instances (same seed and sample), same eligibility, same section 4 stop rule, unchanged. Feasibility only: no coverage, no coverage-vs-detection association.
- Interpreter chosen by the Python version declared in the bug's BugsInPy metadata, not by outcome. Each bug is run once, on one interpreter.
- Availability finding (made before the run): `uv` (0.13.1) provides Python 3.8.20 for this machine (Apple silicon) but has no download for 3.6 or 3.7 (no arm64 macOS build; no x86_64 build offered either). So bugs declaring 3.8.x run on 3.8.20 (matching). Bugs declaring 3.6.x or 3.7.x (cookiecutter, httpie, thefuck, tornado, youtube-dl) cannot run on their declared interpreter. They are run on 3.8.20 as a substitution decided now, and are reported separately as "substituted".
- The stop rule is evaluated twice and both are reported: (a) matching-interpreter instances only; (b) matching plus substituted. The decision to continue requires (a) or (b) to meet the rule; if only (b) does, that is stated as weaker evidence.
- Sandbox unchanged: network off, no relaxation for luigi's local sockets. Luigi instances that need a bound socket are counted as a sandbox limitation, not made feasible.
- Python 3.11 results (section 5) stay as reported; the new results are reported separately.
