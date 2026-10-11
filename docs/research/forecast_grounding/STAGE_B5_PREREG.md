# Stage B5 (larger registered test of the fuller attempt-time capture) — pre-registration, 2026-10-11 (written BEFORE any B5 run)

Origin: `STAGE_B4_RESULTS.md`: B4 had 8 valid runs (< the registered minimum of 10), so no reading was drawn (descriptively capture 5/8, reconstruction 2/8). The limit was task yield: about 46% of attempts end as valid runs (B3 11/19, B4 8/22), the rest being unsolved or trivial. A static pre-agent screen for triviality was tried on the 33 agent-passing B3/B4 runs and **did not work** (valid rate 57% base; 60-73% when selecting on the screen, losing 5-8 of 19 valid runs), so it is not used. B5 simply attempts more tasks.

**Question, capture, contexts, validity, replay:** identical to `STAGE_B4_PREREG.md` (the fuller capture frozen there; replay and harness as of commit `0252fdc`; same agent, S0 sandbox, empty virtualenv, prompt C1P, one run per task, same scoped target command in every context). Changes allowed during the stage: bug fixes only, logged below.
**Tasks.** Stage B0 candidates without a reconstructable environment that B3 and B4 did not use (`stageb5_select.py`, seed 2031, 151-candidate pool, at most 2 per repository, 44 tasks in 36 repositories).
**Primary outcome.** Among valid runs (agent's target tests pass in its own environment and fail on the baseline without its changes): E_capture and E_repo reproduction rates with Wilson 95% intervals and paired counts. **Rule (unchanged from B4):** *supported* if E_capture >= 70% AND exceeds E_repo by >= 30 points; *not supported* if E_capture <= E_repo + 10 points or E_capture < 50%; otherwise inconclusive. **Minimum: 15 valid runs**; fewer is reported as underpowered with no reading.
**Secondary / descriptive:** E_recipe (scoped); B4+B5 pooled (same capture, fresh tasks each; descriptive only, the registered test is B5 alone); classification of each capture failure; cost.
**Budget.** Hard cap $32; a run is not started if spent + $1.5 would exceed it; authentication failures stop the run without recording (nothing is spent or recorded).
**Expected size** (stated so the stop is not a surprise): about 44 attempts at about $0.77 each is about $34, so the budget rule will probably stop the run at 40-42 attempts; about 18-20 valid runs are expected.
**Known limits stated in advance.** Capture is pip-freeze only; tasks were selected as ones reconstruction failed on, so E_repo is expected to be low (B4 saw 25% because environment resolution varies by day); one model; one run per task; reconstruction tasks; third-party code stays local.

## Deviation log
(none yet)
