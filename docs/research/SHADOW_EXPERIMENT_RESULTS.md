# Shadow experiment results (2026-10-30, revised after the adversarial review)

Pre-registration: `SHADOW_EXPERIMENT_PREREG.md` (freeze record, amendments A1 and A2). Design: `docs/strategy/SHADOW_EXPERIMENT_DESIGN_2026-10-28.md`. Data and scripts: `docs/research/shadow2_data/`, `research/shadow2/`. **Shadow mode: every decision is hypothetical; nothing acted.** Labels are LLM labels (first pass Sonnet, second pass Opus), not human-validated; agreement between them is consistency, not independent verification. Nothing here claims novelty.

## Corrections after the adversarial review (the first version of this document overclaimed)
1. **The primary comparison is dominated by random tie-breaking.** The 20% budget is 201 slots; arm 5 has only 59 informative flags, so 142 slots are random fills among 664 tied pull requests; arm 2 is binary (608 "review"), so its 201 slots are a random draw; arms 1 and 3 also fill 54 and 80 slots at random. The bootstrap resamples repositories only. Over 300 other tie seeds (exploratory): weighted recall mean (sd) arm 0 0.198 (0.087), arm 1 0.311 (0.054), arm 2 0.279 (0.095), arm 3 0.193 (0.017), **arm 5 0.344 (0.069)**, arm 6 0.403 (0.041); arm 5 minus arm 1 averages **+0.033 (sd 0.087), positive in 64% of seeds**. The registered seed gave arm 0 an unusually low 0.136.
2. **The weights rest on six pull requests.** Six of the 52 positives are unflagged "rest" pull requests with weight 10; they carry **47% of the weighted denominator** and none is caught by arms 1, 3, 5 or 6 (arm 2 and arm 0 catch some by chance). Within the flagged stratum alone (46 positives, no reweighting): arm 5 24, arm 1 23, arm 3 17, arm 6 33, arm 2 10, arm 0 4.
3. **S2 does not discriminate.** A random ranking (arm 0) meets "at least 3 unique catches in at least 3 repositories" in about **70%** of tie seeds. The registered expectation that S2 would be hard to meet was wrong.
4. **An empty-change-list artifact.** 25 pool pull requests have an empty file list (closed, unmerged, zero changed files); the 8 positives among them are produced mechanically (the checker flags the named file as absent; the labeller finds the same). Without them (44 positives, exploratory): weighted recall arm 5 **0.245**, arm 1 **0.299**, arm 2 0.162, arm 3 0.218, arm 0 0.215, arm 6 0.367; unique catches fall to 8 in 7 repositories.
5. **Ascertainment.** Labellers can settle FALSE where deterministic evidence exists, which is where arm 5 looks; unscorable pull requests are not spread evenly across arm 5's score: score 1 has 85 of 179 labelled pull requests unscorable (47%), score 2 has 4 of 32, score 0 has 8 of 57. The bucket precisions below are conditional on being scorable and are not an independent-evidence estimate. Eleven of the 14 files-FALSE positives have arm 5 score at least 2 because the labeller and the static check do the same file-list comparison.
6. **The decision-rule reading was changed by me, not by the registration.** The registered rule is: S1 and S2 hold and the false-clear rate under the policy the owner would run is at most 25%. Under the strict policy the false-clear rate is 20.4% and S1 and S2 hold on the registered seed, so **by the letter the rule is met under strict**. The earlier sentence "no policy is both under 25% and practical" added a "practical" condition that the registration does not contain (it only says strict burden above 70% is "reported as impractical"). Corrected below.
7. **The strict policy is dominated by trivial baselines.** See the binary-decision table.
8. **Wording corrected:** "about three times the base rate" (lenient 52.6% against 19.3% is 2.7 times, on 32 scorable pull requests, no interval; score 3 alone is 2.1 times), "a modest amount to CI" (the interval touches zero), "prioritisation aid" (unsupported against binary baselines), and the S4 reading (see below).
9. **Post-freeze changes list:** `common.py` (A1), `sample.py` (A2), the `analyze.py` loader that maps labels to pull requests through the items, `agree2.py`, `robustness.py` and `seeded.py`. Only A1 and A2 were amended in the registration; the loader change and `agree2.py` were not, and `sample.py` ties use the hash tag "lex" while `analyze.py` uses "arm3_lexical", so the sampled arm-3 flags are not nested in the analysed top set (the weights stay valid; variance is higher). Git alone cannot show that no label existed before A2; file modification times do (labels after 09:15:58 on 29 October; A2 committed 09:16).

## What ran
- **Pool:** 1,056 pull requests drawn with the frozen seed; 1,003 observable (53 gone). **Arms** 0 to 3 and the static part of 5 on all 1,003; the **full audit (arm 5) on the 178 Python pull requests** that carry a tests, lint or impact claim (median 26 seconds; 38 runs printed "automatic environment setup incomplete").
- **Label sample (after amendment A2):** 278 pull requests (210 flagged by the lenient policy, the exact top 15% of text triage, or failing CI; 68 from the rest at 10%), **603 statements, all labelled by the first pass**. Weights are inverse inclusion probabilities.
- **Second pass:** 52 of the 56 seeded pull requests (18.7% of 278, just under the pre-registered 20%). Arm 4 (LLM judge) and arm 3b (TF-IDF) were **not run**.
- **Classes among the 278:** 52 **positive** (at least one FALSE statement), 129 negative, 97 **unscorable** (35%). Weighted base rate of positives among scorable pull requests: **19.3%** (the share among all pool pull requests is lower, since unscorable ones are excluded). Of the 70 FALSE statements in positives, 42 are impact claims, 14 files, 7 tests, 4 lint, 3 docs.

## Primary result as registered: recall of positives at a 20% review budget (registered tie seed; weighted)
| arm | weighted recall | unweighted (k/n) |
|---|---|---|
| 0 random | 0.136 | 6/52 |
| 1 CI only | 0.309 | 27/52 |
| 2 trust the report | 0.294 | 8/52 |
| 3 text triage | 0.172 | 15/52 |
| 5 Agentvow record | 0.320 | 28/52 |
| 6 CI + Agentvow (10% each; 193 slots) | 0.412 | 36/52 |
Registered differences: arm 5 minus arm 1 **+0.011 [-0.131, +0.156]**; arm 5 minus arm 3 **+0.149 [+0.023, +0.309]**; arm 6 minus arm 1 **+0.103 [-0.009, +0.244]**. Read with corrections 1, 2, 4 and 5 above: **there is no evidence that arm 5 beats CI at this budget**; its advantage over the lexical arm is the only difference whose interval excludes zero, and it rests on the registered tie seed. If the 97 unscorable pull requests are counted as positive, all arms are close (arm 5 0.272, arm 1 0.254, arm 3 0.241, arm 6 0.238).

## Binary decisions (burden / weighted recall / weighted precision; exploratory, the fair comparison for yes/no arms)
| decision | burden | recall | precision |
|---|---|---|---|
| CI not success (arm 1) | 78.7% | 0.83 | 0.21 |
| CI failing or pending only | 14.7% | 0.26 | 0.38 |
| trust the report: review (arm 2) | 60.6% | 0.84 | 0.23 |
| **Agentvow strict** | 72.1% | 0.80 | 0.225 |
| **Agentvow lenient** | **5.9%** | 0.23 | **0.53** |
The strict policy (any UNKNOWN claim or flag) is just "the description has a tests, lint or impact claim" and is **dominated by arm 2** (less burden, more recall, similar precision). The lenient policy has the smallest burden and the highest precision of the five, on 32 scorable flagged pull requests with no interval; it recovers a quarter of the positives; its precision is also inflated by correction 5.

## Where arm 5's signal comes from
Pool scores: 12 pull requests with a CONTRADICTED finding (score 3), 47 with attention (score 2), 664 with UNKNOWN on a tests, lint or impact claim (score 1), 280 with none (score 0). Weighted precision among labelled scorable pull requests: score 3 **40%**, score 2 **57%**, score 1 **18%**, score 0 **12%**; base rate 19%. The informative part is the **59 pull requests flagged CONTRADICTED or attention (5.9% of the pool)**; the 664 UNKNOWN-claim pull requests sit at the base rate.

## Pre-registered tests (as the registration states them, with what the review showed)
- **S1** (arm 5 above arms 0 and 2): met on the registered seed (0.320 against 0.136 and 0.294); met in **66%** of tie seeds; the margin over arm 2 is 0.026.
- **S2** (at least 3 unique catches in at least 3 repositories): met by the letter (14 positives in 12 repositories; 8 in 7 without the empty-change-list artifact), but a **random ranking meets it in about 70% of seeds**, so it carries little information.
- **S3** (lenient: burden at most 30% and false-clear at most 25%): burden 5.9% met; **false-clear 77% (32 of 52) not met**. Strict (reported): burden 72%, false-clear 20%, precision 22.5% against 19.3%.
- **S4** (text triage matches or beats arm 5 on non-Python pull requests): arm 5 0.256 against arm 3 0.196 (interval for the difference includes zero); on these pull requests arm 5 is the static files/docs check plus random ties, and CI scores about 0.32. The prediction is not supported, but no difference is established either.

## Decision rule
Registered: an acting consumer may be built only if S1 and S2 hold and the false-clear rate under the policy the owner would run is at most 25%. **By the letter it is met under the strict policy** (S1, S2 on the registered seed; false-clear 20%). **I recommend not acting on that**: S1 and S2 hold only weakly (66% of tie seeds; random meets S2 70% of the time); the strict policy sends 72% of pull requests to review and is beaten by a rule that needs no Agentvow; its false-clear rate rests on 6 of 52 positives; and the lenient policy, the only one with a useful burden, clears 77% of positives. The owner has not chosen a policy to run. So the evidence does not support building an acting consumer, and it supports the record only as an additional, high-precision, low-recall flag next to CI (the lenient flag), which is itself conditional on correction 5.

## Labeller consistency (second pass, 52 pull requests, 124 statements)
Agreement 99 of 124 (kappa 0.71); claims only 82 of 107 (kappa **0.62**). Pull-request class agrees on 40 of 52 (kappa **0.64**): of the 11 first-pass positives in the sample, 3 are negative in the second pass; of the second pass's 12 positives, 2 were negative and 2 unscorable in the first. By kind: files 13 of 13, impact 60 of 81 (kappa 0.64; plus no_downstream_impact 3 of 3), tests 12 of 15 (**kappa 0.575, below the pre-registered 0.6**), lint 2 of 2, docs 4 of 4. **The positive class is noisy**, and the test-statement labels meet the pre-registered "labels unreliable" condition.

## Limits and deviations
- Labels: LLM, one family per pass; 35% unscorable; **impact claims dominate the positives (42 of 70 FALSE statements)** and are the most judgment-dependent kind: this experiment mostly measures agreement with LLM judgments about backward compatibility.
- Second pass 18.7% not 20%; arm 4 and arm 3b not run; the seeded false-statement test ran only on development data (32 of 32, pipeline sensitivity); the pool is 1,056 not 1,200; amendments A1 and A2 (and the unlisted loader change, see correction 9).
- Arm 5 on non-Python pull requests is UNKNOWN by construction on tests, lint and impact claims.
- CI classification treats cancelled, action-required and stale check-runs as failing; the lexical phrase list has overlapping phrases (a harmless double count).
- Permission denials and a nearly full disk made many labellers' test and lint runs impossible (CANNOT_TELL); one labeller re-ran a denied combined command as separate sandboxed commands.
- Temporal validity as in the audit study; the pool is public agent-authored pull requests in AIDev.

## What this means
The record's strongest flags (a CONTRADICTED lint or API finding, a description-versus-change-list mismatch, an impact flag) pick out pull requests with a false claim somewhat more than twice as often as chance, at about 6% of pull requests; they do not measurably improve on CI at a fixed budget, they miss roughly three quarters of positives, and the strict policy is no better than a trivial baseline. The pre-registered rule does not justify an acting consumer. The honest product statement stays the one the owner chose: an independent claim-audit record for people to read, with a high-precision attention flag, not a gate.
