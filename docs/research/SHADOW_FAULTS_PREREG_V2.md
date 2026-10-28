# Shadow study, offline arms, run 2: pre-registration (2026-10-28, written before run 2)

Replaces the reading rules of `SHADOW_FAULTS_PREREG.md` after the adversarial review of run 1 (`SHADOW_FAULTS_RESULTS.md`, corrections). Script `research/shadow/run_faults.py` (v2), generator `research/shadow/faults.py` (10 tests). Output `data/shadow/faults_v2.jsonl` (local). Seed 20261029.

**Changes from run 1.** (1) An unfaulted control per run and arm. (2) A fresh `AGENTVOW_HOME` and no `.agentvow` before every check; arm order alternates by fault. (3) The generator never edits strings, f-strings or comments, never plants `return None` in a generator, never flips `while True`. (4) The mutated line, all findings and a harness-failure flag are stored. (5) Arm C is called the **freeze-recipe context** (pip-freeze recipe), not a capsule replay.

**Same as run 1.** The 20 valid B6 runs; up to 3 faults of different types per run; claim "All tests pass."; target tests only; the simplified decision map (CONTRADICTED→stop, UNKNOWN→escalate, passing run→continue) over the tests_pass finding only, not `agentvow policy evaluate`.

**Definitions.** *Harness failure*: the check produced no test evidence for the state ("different commit or working-tree state", "did not run the tests", no result); excluded from decisions and listed. *Informative fault pool P*: faults in runs where, for at least one arm, the unfaulted control was a passing run (not UNKNOWN, not a harness failure). Faults in runs where both controls were UNKNOWN say nothing about the fault and are excluded from P.

**Primary outcome.** Among faults in P with no harness failure in either arm: the number where C decides *stop* and B does not, and the repositories they come from. Also reported: faults where B stops and C does not; C continue where B escalates (clear-on-unseen-fault trade-off); counts by run, not only by fault.

**Reading, fixed now.**
- |P| < 20 faults: **inconclusive for this pool** (mechanics only). This is not evidence of no effect.
- |P| ≥ 20 and C stops where B does not in ≥ 3 faults from ≥ 3 repositories: supports "the freeze-recipe context changes a decision" for this pool (authored faults, one agent family).
- |P| ≥ 20 and fewer: "no change seen in this pool", with the counts; not a statement about real defects.
- Any fault where B stops and C does not is reported and explained, whatever |P|.

**Not measured.** Unsafe advancement against ground truth, arm A (CI only), whether the faulted line is executed, equivalent mutants (reduced, not excluded). Faults within a run are not independent. One annotator.
