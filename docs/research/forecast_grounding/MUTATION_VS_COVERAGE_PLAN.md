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
