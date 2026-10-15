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
