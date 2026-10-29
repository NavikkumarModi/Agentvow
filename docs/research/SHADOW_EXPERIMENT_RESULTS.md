# Shadow experiment results (2026-10-29/30; DRAFT pending the adversarial review)

Pre-registration: `SHADOW_EXPERIMENT_PREREG.md` (freeze record, amendments A1 and A2). Design: `docs/strategy/SHADOW_EXPERIMENT_DESIGN_2026-10-28.md`. Data and scripts: `docs/research/shadow2_data/`, `research/shadow2/`. **Shadow mode: every decision is hypothetical; nothing acted.** Labels are LLM labels (first pass Sonnet, second pass Opus), not human-validated; agreement between them is consistency, not independent verification. Nothing here claims novelty.

## What ran
- **Pool:** 1,056 pull requests drawn with the frozen seed; 1,003 observable (53 gone). **Arms** 0 to 3 and the static part of 5 on all 1,003; the **full audit (arm 5) on the 178 Python pull requests** that carry a tests, lint or impact claim (median 26 seconds; 38 runs printed "automatic environment setup incomplete").
- **Label sample (after amendment A2):** 278 pull requests (210 flagged by the lenient policy, the exact top 15% of text triage, or failing CI; 68 from the rest at 10%), **603 statements, all labelled by the first pass**. Weights are the inverse inclusion probabilities.
- **Second pass:** 52 of the 56 seeded pull requests (18.7% of 278, just under the pre-registered 20%; the last four were not finished). Arm 4 (LLM judge) and arm 3b (TF-IDF) were **not run**.
- **Classes among the 278:** 52 **positive** (at least one FALSE statement), 129 negative, 97 **unscorable** (35%). Weighted base rate of positives among scorable pull requests: **19.3%**. Of the 70 FALSE statements in positives, 42 are impact claims, 14 files, 7 tests, 4 lint, 3 docs; 8 of the 52 positives are pull requests with an empty change list.

## Primary result: recall of positives at a 20% review budget (weighted; repository cluster bootstrap)
| arm | weighted recall | unweighted (k/n, Wilson) |
|---|---|---|
| 0 random | 0.136 | 6/52 |
| 1 CI only | 0.309 | 27/52 |
| 2 trust the report | 0.294 | 8/52 |
| 3 text triage | 0.172 | 15/52 |
| 5 Agentvow record | **0.320** | 28/52 |
| 6 CI + Agentvow (10% each) | **0.412** | 36/52 |
Differences: arm 5 minus arm 1 **+0.011 [-0.131, +0.156]** (no difference); arm 5 minus arm 3 **+0.149 [+0.023, +0.309]**; arm 6 minus arm 1 **+0.103 [-0.009, +0.244]**.
Sensitivity: if the 97 unscorable pull requests are counted as **positive**, all arms are close (arm 5 0.272, arm 1 0.254, arm 3 0.241, arm 6 0.238; arm 5 minus arm 1 +0.018 [-0.118, +0.152]); counted as negative, the base table is unchanged. **The ordering of the arms is not robust to how unscorable pull requests are treated.**

## Where arm 5's signal comes from
Pool scores: 12 pull requests with a CONTRADICTED finding (score 3), 47 with attention (score 2), 664 with UNKNOWN on a tests, lint or impact claim (score 1), 280 with none (score 0). Weighted precision among labelled scorable pull requests: score 3 **40%**; score 2 **57%**; score 1 **18%**; score 0 **12%**; base rate 19%. So the informative part of arm 5 is the **59 pull requests flagged CONTRADICTED or attention (5.9% of the pool)**, about 3 times the base rate; the 664 UNKNOWN-claim pull requests sit at the base rate. Of the 201 pull requests in arm 5's top 20%, 142 are random ties among score 1. All 14 "unique catches" have score 2 or 3.

## Pre-registered tests
- **S1** (arm 5 recall above arms 0 and 2 at the budget): numerically met (0.320 against 0.136 and 0.294), but the margin over arm 2 is 0.026 and no interval separates them.
- **S2** (at least 3 unique catches in at least 3 repositories): **met**: 14 positives in 12 repositories are in arm 5's top set and in neither arm 1's nor arm 3's. Caveat: these come from the 59 informative flags; combining with CI raises recall from 0.31 to 0.41 but the gain over CI alone has an interval that touches zero.
- **S3** (lenient: burden at most 30% and false-clear at most 25%): burden **5.9%** met; **false-clear 77% (32 of 52 positives get "proceed") not met**. Strict policy (reported, not bounded): burden **72%**, false-clear 20%, review precision 22.5% against a 19.3% base rate, so it sends nearly three quarters of pull requests to review and enriches almost not at all (pre-registered reading: impractical).
- **S4** (text triage matches or beats arm 5 on non-Python pull requests): **not supported**: on the 37 non-Python positives, arm 5 recall 0.256 against arm 3 0.196.

## Decision rule for an acting consumer (pre-registered)
It may be built only if S1 and S2 hold **and** the false-clear rate under the policy the owner would run is at most 25%. S1 and S2 hold. The lenient policy has a false-clear rate of 77%; the strict policy has 20% but a 72% burden at near-base-rate precision. **No policy tested is both under 25% false-clear and practical; the decision rule is not met.** On this evidence an acting consumer is **not** supported; the record is supported as a prioritisation aid (the lenient flags are right about half the time at 6% of pull requests) next to CI.

## Labeller consistency (second pass, 52 pull requests, 124 statements)
Agreement 99 of 124 (kappa 0.71); claims only 82 of 107 (kappa **0.62**). Pull-request class (positive, negative, unscorable) agrees on 40 of 52 (kappa **0.64**): of the 11 first-pass positives in the sample, 3 are negative in the second pass; of the second pass's 12 positives, 2 were negative and 2 unscorable in the first. By kind: files 13 of 13, impact 60 of 81 (kappa 0.64), tests 12 of 15 (**kappa 0.575, below the pre-registered 0.6**), lint 2 of 2, docs 4 of 4. Disagreements: 8 CANNOT_TELL to TRUE, 6 CANNOT_TELL to FALSE, 6 FALSE to CANNOT_TELL, 2 TRUE to FALSE, 2 TRUE to CANNOT_TELL, 1 not-a-claim to TRUE. **The positive class is noisy**; recall figures carry that noise, and the test-statement labels meet the pre-registered "labels unreliable" condition.

## Limits and deviations
- Labels: LLM, one family per pass; 35% unscorable; 31% of earlier audit-study labels were judgment; **impact claims dominate the positives (42 of 70 FALSE statements)** and they are the most judgment-dependent kind, so this experiment mostly measures agreement with LLM judgments about backward compatibility.
- Second pass 18.7% not 20%; arm 4 and arm 3b not run; the seeded false-statement gate-strength test ran only on development data (32 of 32, pipeline sensitivity).
- Amendments: A1 (transient network errors were cached as unobservable pull requests; fixed before any sample) and A2 (the sampling flag uses the lenient policy and an exact top 15%; chosen after seeing that the as-written rule flagged 80% of the pool, before any label). Pool 1,056 not 1,200.
- Arm 5 for non-Python pull requests is UNKNOWN by construction on tests, lint and impact claims; the labelled-sample selection used the cheap arms and the full arm 5 together.
- Permission-system denials and a nearly full disk made many labellers' test and lint runs impossible (CANNOT_TELL), and one labeller re-ran a denied combined command as separate sandboxed commands.
- Temporal validity as in the audit study; the pool is public agent-authored pull requests in AIDev.
- **Not yet done:** the adversarial review of this analysis (CLAUDE.md requires it before reporting). Treat every statement above as provisional until then.

## What this means
The record's strongest signals (a CONTRADICTED lint or API finding, a description-versus-change-list mismatch, an impact flag) pick out pull requests with a false claim about three times as often as chance, at 6% of pull requests, and they add a modest amount to CI. They miss roughly three quarters of positives, the strict policy is impractical, and the result depends on how the unscorable pull requests are treated. The pre-registered rule does not support building an acting consumer; it supports the record as a human-read aid, as the owner's audit framing says.
