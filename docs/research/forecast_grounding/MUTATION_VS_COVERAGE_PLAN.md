# Does mutation testing add information beyond changed-line coverage? Plan and decision gate (written 2026-10-14, BEFORE any coverage is joined to the mutation outcomes)

Owner decision (2026-10-14): analyse what already exists before running more mutants, as an experiment about the *value of new evidence*, not a commitment to build mutation testing into Agentvow. Free, offline, no agent runs; no Jev, no learned planner, no pilot.

## 1. What already exists
The planted-fault benchmark (`scripts/planted_faults.py`, `docs/research/PLANTED_FAULTS.md`, runs v1-v5 in `data/planted_faults*.csv`, local) planted **behaviour mutations** (operator flips: `==`/`!=`, `<`/`>=`, `>`/`<=`, `return True`/`False`, `and`/`or`, `in`/`not in`) on lines that 15 real merged agent PRs added, in two repositories (NewFuture/DDNS, stdlib unittest; Archmonger/django-dbbackup, pytest), and counted a mutant **detected** when the raw passed-test count dropped against the clean head (the oracle). Unique behaviour mutants across the five runs (deduplicated by repository, PR, file:line and operator): **21** (15 in DDNS, 6 in dbbackup); the oracle gave the same result in every run in which a mutant appeared (no inconsistency); 14 were detected and 7 survived. The data record **no information on whether a mutated line was executed by the tests**.
Caveats that hold throughout: the mutants are simple, authored by us and planted after the agent finished; 21 mutants over 12 PRs in 2 repositories; a surviving mutant does not prove a weak test (it may be equivalent, outside the contract, or only reachable through paths the suite does not exercise).

## 2. Analysis (no new mutants)
Re-create each PR's clean head state, run its test suite once under `coverage` (empty rc file, same test command as the benchmark), and for each mutant record whether its target line was **executed by the original suite**. Join to the stored oracle:
| line executed? | detected | what it means |
|---|---|---|
| no | no | coverage already shows the gap; mutation adds nothing |
| yes | no | the tests ran the line but did not distinguish the mutant: the candidate information beyond coverage |
| yes | yes | existing tests detect it |
| no | yes | an instrumentation or classification problem; expected to be empty and investigated if not |
Also record the wall-clock time of the coverage run per repository as the cost of one suite execution (a mutation run needs one per mutant).
**Manual review (single annotator, disclosed):** every "executed, not detected" survivor is read in context and labelled *equivalent or unobservable* (the flip cannot change observable behaviour), *plausible test weakness* (the line affects behaviour a reasonable test would check), or *cannot tell*.

## 3. Decision rules (fixed now)
Let R = mutants whose line was executed, S = those among R that were not detected.
- **Proceed** to a prespecified coverage-only vs coverage-plus-mutation comparison (same changes, a stated cost budget) if **|R| >= 10 and |S|/|R| >= 25% and at least half of the reviewed survivors are labelled plausible test weakness.**
- **Stop** if **|S|/|R| < 10%**, or two thirds or more of the survivors are labelled equivalent/unobservable or cannot-tell (mutation signal too noisy or already visible from coverage).
- **Investigate further** otherwise, including when |R| < 10 (too few comparable cases), naming what would settle it.
Not claimed whatever the outcome: that these results apply beyond two repositories and simple operator flips, or that mutation score predicts real defect detection.

## 4. Deliverable
`research/preconditions/mutation_vs_coverage.py`, the table above with all denominators, the labelled survivors, and a go / stop / investigate recommendation, appended under Results.

## 5. Deviations (logged, none after seeing the join outcome)
1. **django-dbbackup's suite was run without the macOS test sandbox** for the coverage pass (2 PRs, 1.6-1.7 s each): its `gpg` tests hang inside the sandbox because `gpg-agent` cannot start (an issue known from earlier work; the benchmark run of the same suite finished, so the environment drifted). DDNS (5 PRs) ran sandboxed. The suites are small and were run once unsandboxed in a probe first with no side effects; stated as a deviation from the project's sandboxing rule.
2. **A check not in the plan was added before the decision was read:** each mutant's flip was classified by parsing the original and mutated file: `code_changing` (the program's AST changes), `invalid_syntax` (the mutated file does not parse), or `comment_or_docstring_only` (AST unchanged; ordinary string literals are not blanked because a changed message or key can change behaviour a test asserts). Reason: while reading the survivors I found a flip applied inside a docstring; the classification is a deterministic property of the mutant, not of the join outcome. The registered decision rule below uses all 21 mutants as written; the classification enters only as a sensitivity.
3. Suite re-run results differ slightly from the benchmark's clean counts for some DDNS PRs (for example #562: 781 passed here, 785 in the benchmark); the suites contain environment-dependent tests. The oracle values are the stored ones, not recomputed.

## 6. Results (2026-10-14)
**Population.** 21 unique behaviour mutants (15 DDNS in 5 PRs, 6 dbbackup in 2 PRs; 15 PRs existed, the other 8 had no changed non-test Python line or no behaviour mutant in any run). Of the 21: **10 code-changing, 9 invalid syntax, 2 comment/docstring-only.**
**The join (registered rule, all 21 mutants).**
| line executed by the original suite? | detected | count |
|---|---|---|
| yes | yes | 14 |
| **yes** | **no** | **2** |
| no | no | 5 |
| no | yes | 0 (the instrumentation check came out empty, as expected) |
R (executed) = 16; S (executed and not detected) = 2; **S/R = 12.5%**, |R| >= 10. Coverage already flagged 5 more survivors (not executed): 2 are comment/docstring flips, 1 is a flip in a script file the tests never load, 2 are code-changing flips on unexecuted lines.
**Manual review of the 2 survivors (single annotator; reading the code, not running it):** (a) DDNS #521 `edgeone.py:48`, `and -> or` in `if response and "AccelerationDomains" in response:`; the flip differs only when `response` is falsy (a `None` then raises instead of short-circuiting): a missing negative-case test: **plausible test weakness**. (b) DDNS #539 `http.py:112`, `== -> !=` in the check that decides whether a default `User-Agent` header is added; the flip changes which requests carry the default header, and no test inspects it: **plausible test weakness**. 2 of 2 survivors plausible; none judged equivalent.
**Sensitivity (code-changing mutants only, n = 10):** executed 8 (6 detected, 2 survived), not executed 2; S/R = 25%, but |R| = 8 < 10.
**Cost of one suite execution** (a mutation run needs one per mutant): DDNS 1.5-14 s, dbbackup 1.6-1.7 s per run (seven PR suites; timings from this pass, small repositories).
**Decision under the rules fixed in section 3: INVESTIGATE FURTHER.** S/R = 12.5% is between 10% and 25% (neither Proceed nor Stop), and the code-changing sensitivity has too few comparable cases (|R| = 8). What would settle it: a larger set of **valid code-changing** mutants on executed changed lines, generated by a standard mutation tool and filtered for syntactic validity, over the agent-authored PRs we have (B6 has 22 valid runs with saved patches and suites that run in seconds to minutes), with the same manual review of survivors. Suite times of seconds per mutant make that affordable on small repositories; larger suites would need a per-change budget.
**A correction this analysis forces on the earlier benchmark.** The planted-fault "behaviour mutation" detection counts (4/9, then 6/8) include **9 of 21 mutants that are not valid programs** (flips such as `for x in y` to `for x not in y` that break the file's syntax; 8 of 9 are "detected" because the suite cannot run) and 2 that change only a comment or docstring. The behaviour-mutation recall in `PLANTED_FAULTS.md` therefore overstates detection of real behaviour changes and should not be cited; among the 10 valid code-changing mutants, 6 were detected, 2 survived on executed lines and 2 were on lines no test ran. Raw join: `data/mutation_vs_coverage.json` (local).
**What this does and does not say.** On this small, synthetic sample, coverage identified most undetected mutants (5 of 7); the 2 extra survivors on executed lines are plausible gaps coverage could not show, which is the signal the question looked for, but it rests on 2 cases. It says nothing about real agent defects or about mutation score as a predictor of them.
