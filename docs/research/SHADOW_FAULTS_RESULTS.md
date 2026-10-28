# Shadow study, offline arms B and C: results of run 1 (2026-10-28), with the adversarial review's corrections

**Read the corrections section first. Run 1 is confounded (no unfaulted control) and partly a harness artifact; its reading below is withdrawn and replaced by "inconclusive for this pool". Run 2 (`SHADOW_FAULTS_PREREG_V2.md`) fixes the design.**

## Corrections after the adversarial review (2026-10-28; counts re-verified against the data)
1. **No unfaulted control.** 16 of 21 captured UNKNOWNs and 16 of 28 native UNKNOWNs say the same tests also fail without the change (environment). Those runs were UNKNOWN before any fault; "both UNKNOWN: 20" is not a response to the fault, and "the tool declined to decide rather than clear them" is withdrawn. The fault-specific pool is much smaller than 37.
2. **Harness failures counted as decisions.** 5 captured checks (llm-subtrans Time.py:62 and :80, cartography util.py:292 and :297, and one more) report no test evidence for the faulted state ("evidence belongs to a different commit" or "did not run the tests"). They are not captured UNKNOWN decisions. The llm-subtrans#353 case below is one of them, so there are **8 real differing cases, not 9**, and "B stricter" is withdrawn.
3. **Direction mislabelled.** In llm-subtrans#353 B was continue and C escalate (C stricter by the pre-registration's own definition), and it is a harness artifact. There is no case where B stopped and C did not.
4. **Arm C is not a capsule replay.** Both arms ran through `--recipe`; C is a recipe that installs the agent's pip freeze. Call it the *freeze-recipe context*; conclusions cover that approximation only.
5. **The frozen decision map is a simplified map over the tests_pass finding only**, not `agentvow policy evaluate`; the real policy also escalates on partial_capture, harness_warning, unauthenticated_capture and description_mismatch, so some "continue" cells could be escalations. "SUPPORTED_BY_PRIOR_EVIDENCE" here means: the tests ran in the declared recipe and passed (conditioned support).
6. **Equivalent and non-code mutants were possible** (the generator matched text inside strings and comments, and planted `return None` in generators). The stored data keeps only file:line, so it cannot be audited. Fixed in the generator for run 2.
7. **Not checked: whether the faulted line was executed.** "Not seen by the target tests" below means no failure was observed; an unexecuted line or an equivalent mutant is equally possible.
8. **Possible evidence leakage between arms** (shared `.agentvow` and `AGENTVOW_HOME`, fixed order) was not ruled out. Run 2 isolates every check and alternates order.
9. **Overclaims withdrawn:** "agrees with E5" (same 20 runs, same authors' faults: *consistent with*, not independent confirmation); "evidence that replayability alone is not the product value" (this study does not bear on product value); "further offline faults will not change that" (unsupported prediction); "four times as many" (different generators). The per-type table is not a rate (types were balanced by design). The 7 "C continued where B escalated" faults come from 4 runs (hlda#56, onefilellm#71, vehicle_speed_estimation#7 ×3, things-mcp#8 ×2), not 7 independent cases.
10. **The pre-registered threshold was set after seeing E5 (one captured-only case) and has no power justification; its "otherwise: no evidence" branch reads absence of an effect from an underpowered, confounded pool.** The honest reading of run 1 is **inconclusive for this pool**. Run 2's pre-registration fixes this.

---

# Run 1 as originally reported (kept for the record; see corrections above)

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
Condition for "supports the claim that captured context changes a decision": C stops where B does not in at least 3 faults across at least 3 repositories. Observed: **1 fault, 1 repository.** Original reading (withdrawn, see corrections): ~~no evidence that capture changes decisions beyond reproducibility~~ → **inconclusive for this pool**; consistent with E5 (weak), which used the same runs.

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
