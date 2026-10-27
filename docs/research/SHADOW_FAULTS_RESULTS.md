# Shadow study, offline arms B and C: results (2026-10-28)

Pre-registration: `SHADOW_FAULTS_PREREG.md` (written before the run; decision map and reading unchanged). Script `research/shadow/run_faults.py`, generator `research/shadow/faults.py`, output `data/shadow/faults.jsonl` (local). One pass, no re-runs, no tuning.

## Flow
20 valid B6 runs. 4 not re-runnable (untracked files), 1 no plantable line, **15 runs produced 37 faults in 14 repositories** (≥20 required for a reading). Types that ran: negate 11, return_none 11, flip 8, constant 5, offbyone 2. E5 got 9 faults from 9 runs; the wider scope (any line of a function the change touched) and more fault types give four times as many.

## Decisions (frozen map: CONTRADICTED→stop, UNKNOWN→escalate, passing run→continue)
| | stop | escalate | continue |
|---|---|---|---|
| C: captured context | 5 | 21 | 11 |
| B: project-native context | 4 | 28 | 5 |

The two contexts reached **different decisions on 9 of 37 faults**:
- **C stricter (stop where B escalated): 1** (Bindu#10, a negated condition; project-native could not run, captured did and the tests failed).
- **B stricter or equal-or-more-informative than C: 1** (llm-subtrans#353: captured UNKNOWN, project-native ran and passed).
- **C continued where B escalated: 7** (hlda#56, onefilellm#71, vehicle_speed_estimation#7 ×3, things-mcp#8 ×2). Here the captured context could run the tests, which passed with the fault in place, while the project-native context could not run at all.

Both stop: 4 (korean-romanizer, llm-subtrans, sshpilot, Bindu). Both UNKNOWN: 20.

## Reading, as pre-registered
Condition for "supports the claim that captured context changes a decision": C stops where B does not in at least 3 faults across at least 3 repositories. Observed: **1 fault, 1 repository.** Reading: **no evidence that capture changes decisions beyond reproducibility.** This agrees with E5 (weak).

## What the data does show
1. **Capture's effect is mostly that the tests can run.** Of the 9 differing decisions, 8 are cases where the project-native context could not produce a result. That is the E3 result (reproducibility) showing again, not defect detection.
2. **Running is not the same as catching.** In 7 of 37 faults the captured context ran, the tests passed, and the decision became "continue" where the project-native context honestly said "escalate". Those faults were not seen by the target tests. If a policy lets "continue" advance work, capture **lowers the escalation rate and also converts honest UNKNOWN into a clear on faulted code that the tests do not cover.** Whether those faults are real defects is not established (see limits). This is the trade-off a shadow study with real defects must measure; it is the reason "unsafe advancement" is the primary measure.
3. By type, captured stops came from negate 3 (of 11), offbyone 1 (of 2), return_none 1 (of 11); **flip 0 of 8 and constant 0 of 5** were never stopped. Target tests were blind to a large share of single-line faults, as in earlier work.
4. 20 of 37 faults were UNKNOWN in both contexts: the tool declined to decide rather than clear them.

## Limits
- Faults are single-line edits authored by us. Some may be equivalent mutants (no behaviour change), so "continue" is not proven to be a miss; no oracle other than the same tests was available (circular), so unsafe advancement was **not** measured. Arm A (CI only) was not run either.
- Only the PR's target test files ran. 14 repositories, 15 runs, one agent family, one host, up to three faults per run (faults within a run are not independent). No confidence intervals are claimed.
- Faults were chosen deterministically from a seed, not tuned, but the generator was written after seeing E5's results.
- One annotator; no second reviewer of the results.

## Consequence for the plan
The offline step is done and its answer is "no decision value shown beyond reproducibility, and a visible clear-on-unseen-faults trade-off". Further offline faults will not change that. The question left is the shadow run on a real plain-pip repository with real agent pull requests and independently labelled defects (`SHADOW_STUDY_DESIGN_2026-10-27.md`, step 4), which needs a partner. This is not evidence for or against the vision; it is evidence that replayability alone is not the product value.
