# Mutation survivors versus coverage: the bounded result

Written 2026-10-15. Closes the mutation line of work. Sources: `MUTATION_STUDY_PREREG.md` (sections 8 to 10) and `REAL_BUG_PLAN.md` (sections 5 to 7). All rules were fixed before the data they govern; deviations and instrument bugs are in the logs of those documents.

## Demonstrated

- On changes written by coding agents (37 runs, 22 repositories, 348 valid mutants on lines the tests executed), **29.6% of executed-line mutants survive the claimed target tests** (repository-level cluster interval 18.7 to 41.3%; leave-one-repository-out 27.3 to 33.9%). Coverage alone does not show these gaps, because the lines were executed.
- Of the 75 survivors whose full project suite could be run, **74 survived the whole suite** (99%). So the gaps are in the tests a project actually has, not only in the claimed tests. This check is weaker in 21 of the 75, which sit in suites that already fail many tests at baseline; 28 survivors could not be checked (full suite over 180 seconds).
- In a seeded sample of 60 survivors, the primary reviewer labelled **80% plausible test weaknesses** (82% among those that survived the full suite). A second labeller, another model and not independent verification, labelled 87% plausible; agreement was 87%, and only the first 30 packets were labelled independently of it (30 of 30 agreement there). The plausible share on that independent half was 28 of 30.
- Cost was small: median 6 seconds of mutation time per run.

## Not demonstrated

- That survivors predict real defects, or that mutation testing would have prevented regressions that coverage missed. The survivors are mostly constant replacements and comparison flips on defaults, boundaries and configuration; "plausible weakness" there means a reasonable test could pin the value, which is weaker than a missed logic error. One fifth of the reviewed survivors were equivalent or undecidable.
- Real-defect value from later history: only 16 fix-like later changes in 4 of 21 repositories, too few for any comparison.
- Generality: one PR-author family, small mostly-Python repositories with simple tests, one reviewer plus one model, sshpilot holding a fifth of the survivors.

## Infeasible under the tested setup (not unanswerable)

The historical real-bug benchmark (BugsInPy) did not reach its pre-committed feasibility threshold (at least 30 usable bugs across at least 5 projects, none above 40%) on this Mac, in two screens of the same 65 bugs:

- Python 3.11: 7 feasible, 2 projects.
- Python 3.8.20, the era interpreter where available: 0 feasible among bugs whose declared interpreter matched; 16 in 3 projects when 3.6/3.7-declared bugs were run on 3.8 as a stated substitution.

Interpreter age was not the main obstacle. Old dependency pins fail on this platform (a `cryptography` build, a Windows-only `pywin32` pin, an uninstallable `pkg-resources==0.0.0`, metadata errors), some suites fail at collection, and the network-off sandbox blocks tests that bind local sockets (not relaxed). These are limits of the environment tested, not evidence about whether real-bug validation can be done.

A design point learned on the way: a historical fix is a bug that escaped, so "the pre-existing suite did not detect the original defect" is true by construction for nearly all instances. The informative outcome is how often the lines a fix changed were executed by the suite, which a future study should use.

## Decisions

- The line-by-line install stage (skip unusable pins) was not run. It would change the environment recipe after the failures were seen, and pre-registering it would make that transparent without making the environments faithful to the historical ones. Avoiding an open-ended series of more permissive recipes chasing a sample size is deliberate.
- If real-bug validation is revisited, it should be a separately planned feasibility study using historically compatible Linux environments, where old pins and platform assumptions can be tested faithfully, with its own stop rule written beforehand.
- For Agentvow: the result supports, at most, an opt-in mutation action explained as "tests execute these lines but would not notice this change", never as a defect finding. No mutation feature is added on this evidence.
