# Shadow study, offline arms B and C: pre-registration (2026-10-28, written before the run)

Design: `docs/strategy/SHADOW_STUDY_DESIGN_2026-10-27.md`. Script: `research/shadow/run_faults.py`; generator `research/shadow/faults.py` (6 unit tests). Output `data/shadow/faults.jsonl` (local).

**Question.** With a richer fault set than E5 (five fault types; any line of a function the agent changed), how often does the captured context (arm C) reach a different decision than the project-native context (arm B), and in which direction?

**Population.** The 20 valid B6 runs with a passing captured replay (same as E5). Up to 3 faults per run, of different types, chosen with seed 20261028. Runs that cannot be rebuilt or have no plantable line are listed, not replaced. Claim: "All tests pass." Only the PR's target test files run (as in E5).

**Frozen decision map** (verdict → hypothetical decision, from `agentvow policy` semantics): CONTRADICTED → stop; UNKNOWN → escalate; NOT_CONTRADICTED / SUPPORTED_BY_PRIOR_EVIDENCE → continue. Not changed after seeing results.

**What is measured, per fault.** Decision under B and under C; whether they differ; direction (C stricter = C turned a continue/escalate into stop, or a continue into escalate).

**Not measured, and why.** Arm A (CI only) and "unsafe advancement" against ground truth: a "continue" on a faulted program is only an unsafe advance if the fault is not equivalent to the original, and the only oracle here is the same tests (circular). A "continue" is therefore reported as **silent: the available tests did not see the fault**, never as a proven miss or a proven safe change.

**Reading, fixed now.**
- Fewer than 20 faults that ran: mechanics only, no reading.
- C stops where B escalates or continues in at least 3 faults across at least 3 repositories: "supports the claim that captured context changes a decision" (descriptive, authored faults).
- B stops where C does not (any case): reported and explained; it would count against the claim that capture dominates.
- Otherwise: "no evidence that capture changes decisions beyond reproducibility".

**Limits.** Faults authored by us (single-line edits); one agent family; one host; target tests only; one annotator. Results are pipeline sensitivity, not defect detection.
