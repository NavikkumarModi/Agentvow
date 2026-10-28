# Shadow-mode experiment: does the evidence record change a decision, correctly? (design, 2026-10-28)

Status: **design; not pre-registered, not run.** It is the precondition set by `CLAUDE.md` ("Human agency", amended 2026-10-28) and `EVIDENCE_RECORD_CONSUMER_PRIOR_ART.md` before any acting consumer is built. **Shadow mode means nothing acts**: each arm produces a hypothetical proceed / review / hold decision per pull request, scored afterwards against labels. No human readers exist (amendment A1 of the audit study); ground truth is evidence-grounded LLM labels and every result carries that caveat. No claim about value to a human reader is made.

## Question
For agent-authored pull requests, does a policy that reads the Agentvow evidence record send the pull requests whose descriptions contain a false claim to review more often than cheaper alternatives, at the same review burden, and at what cost?

## Unit and outcome
- **Unit: the pull request.** **Positive:** a pull request with at least one statement labelled FALSE by the labelling procedure (audit study rules, `AUDIT_LABELLING_RULES.md`). **Negative:** all decisive labels TRUE (and at least one). **Unscorable:** only CANNOT_TELL or not-a-claim statements; kept in burden counts, excluded from recall.
- Base rates from the audit study: 18 of 150 pull requests (12%) have a FALSE claim, 96 of 150 carry any decisive label, 54 of 150 are unscorable. At 12% prevalence a few hundred random pull requests yield too few positives, so the design oversamples flagged pull requests (below).

## Arms (each yields a score per pull request and a frozen proceed/review decision)
| arm | what it uses | cost |
|---|---|---|
| **0 Random** | seeded coin at the budget rate | none |
| **1 CI only** | the head commit's check-runs: all success then proceed, otherwise (failure, pending, none) review | one API call |
| **2 Trust the report** (Proof-or-Stop-style self-receipt baseline) | proceed whenever the description reports passing tests, a clean lint or compatibility; review when it reports nothing or a failure | none |
| **3 Text triage** | a lexical "confident closing" score fixed in advance, plus a TF-IDF logistic model trained on the audit-study labels with repository-grouped cross-validation (the cheap detector family reported to reach AUROC 0.83 to 0.95 in the false-success literature, `[snippet]`) | milliseconds |
| **4 LLM judge** (labelled subset only) | a model reads description and diff and rates suspicion (literature: AUROC at or below 0.65 for judges `[snippet]`; here it is a baseline, never in a verdict path) | tokens |
| **5 Agentvow record** | the frozen audit: files/docs from the change list, lint, impact, tests where runnable; score ordered CONTRADICTED > mismatch/attention > UNKNOWN > NOT_CONTRADICTED, ties by count of findings | seconds to minutes; clones only for Python changes |
| **6 CI + Agentvow** | review if arm 1 or arm 5 says review | sum |
Arm 5 uses the code at the commit frozen for the study (the current head after the impact change is the candidate; the freeze record fixes it). Policies for the decision rule are written before any scoring in `shadow_policy_v1.json` using the existing `agentvow-policy/1` keys: **strict** (proceed only when no finding is CONTRADICTED, none needs attention, and tests and impact claims are not UNKNOWN) and **lenient** (proceed unless something is CONTRADICTED or needs attention). The owner may replace these before the freeze; nobody edits them afterwards.

## Sampling (two-phase, to buy positives cheaply)
1. **Pool.** A seeded draw from the AIDev pull requests not used in development, the stage 1 or stage 2 sample, or the labelled audit sample (the exclusion list of `research/audit/draw.py` plus the audit sample), stratified by agent and repository language, size **N_pool** (options below). Run the cheap arms (0 to 3, and the static part of 5: files/docs/impact where API data suffices) on every pool member. No labels yet.
2. **Label sample.** Label **every pull request any arm flags in its top review budget (the set of arms 1, 3, 5 flags)**, plus a **seeded random 15% of the rest**. Estimates use inverse-probability weights from this design (flagged pull requests have probability 1, others 0.15) with a repository cluster bootstrap; the weights, the strata and the unscorable handling are stated before labelling.
3. **Second pass.** A different model labels a seeded 20% blind (consistency only, as before).
4. **Python subset (optional).** The runnable parts of arm 5 (lint, tests, impact with clones) are run on the Python pull requests in the label sample, as in stage 2; arms stay comparable because unrunnable cases are UNKNOWN in the record.

## Measures (counts first; Wilson and weighted cluster-bootstrap intervals)
- **Primary:** **recall of positives at a fixed review budget** (default 20% of pull requests sent to review): the share of positive pull requests each arm sends to review, compared pairwise with arm 6 against arm 1 and arm 5 against arm 3.
- **Decision-change analysis:** among positives, **unique catches** (sent to review by arm 5 but not by arms 1 or 3) and **unique alarms** (sent to review by arm 5 only and negative or unscorable); for the frozen strict and lenient policies, the **false-clear rate** (positives that get "proceed") and the **review burden** (share sent to review) and **review precision**.
- **Gate strength:** the share of seeded false statements each arm catches. Seeds are minimal false variants of true statements (named file not in the change list, doc update that did not happen, lint on a change with a known finding, inflated test count), produced by a script after the freeze, labelled by construction; reported separately and never mixed into the primary result.
- **Cost:** seconds and tokens per pull request per arm; the pool-wide cost of arm 5's static part versus the Python-subset cost of its runs.
- **Sensitivity:** treating CANNOT_TELL as FALSE and as TRUE (bounds); judgment-labelled versus non-judgment positives; with and without the labelled audit sample added.

## Predictions and falsifiers (fixed before the pool is run)
- **S1.** At a 20% budget, arm 5 sends a higher share of positives to review than arm 0 and arm 2 (a floor; failing it would mean the record is not informative). Falsified if not.
- **S2.** Arm 5 has **at least 3 unique catches** across at least 3 repositories over arms 1 and 3 together. The expectation is that this is **hard to meet**: the audit study found 4 flagged false file statements and few others; if not met, the honest reading is "the record adds nothing measurable over CI plus cheap text triage in this sample".
- **S3.** Under the lenient policy, review burden is at most 30% and the false-clear rate at most 25% of positives. Under the strict policy, burden may reach 70%; its value is reported, not bounded.
- **S4.** Arm 3's text triage matches or beats arm 5 at the same budget on positives in non-Python pull requests (where arm 5 mostly returns UNKNOWN). If so, report that the record's value there is explanation and provenance, not detection.
- **Decision rule for the acting consumer:** it may be built (as engineering) only if S1 and S2 hold and the false-clear rate under the policy the owner would run is at most 25%; otherwise it is not built and the record stays a human-read output. Either outcome is reported with its denominators.

## Threats and controls
Evidence-grounded LLM labels (one model family; 31% judgment labels), unscorable pull requests (54 of 150 earlier), low prevalence (the weighting corrects the sampling but not the variance), arm 5's dependence on the Python subset and on installs, the corpus (AIDev, agent-authored public repositories), temporal validity of heads and file lists, label leakage (labellers see only the description, diff and repository, never any arm output), policy tuning (policies frozen before scoring; no threshold changes after), harness mistakes (controls and isolation as in the earlier studies, an adversarial review before reporting), shared-model blind spots between the LLM judge arm, the labellers and the checkers.

## Cost options (owner's choice; the budget is tokens for labelling at about 65k per pull request)
| option | N_pool | labelled | tokens (approx.) | positives expected |
|---|---|---|---|---|
| minimal | 600 | about 160 | 10M | about 20 to 30 |
| standard | 1,200 | about 320 | 21M | about 45 to 60 |
| full | 2,000 | about 550 | 36M | about 80 to 100 |
Minimal cannot establish S2 reliably; it can show whether the effect is large. Standard is the smallest option that can fail S2 with some confidence.

## Steps
1. Owner: choose the option, confirm or replace the two policies, authorise third-party installs for the Python subset (given 2026-10-28 for the audit study; confirm for this study).
2. Write `shadow_policy_v1.json`, the pre-registration (arms, weights, measures, falsifiers above) and the sampling script; freeze the arm-5 commit and a seed; commit.
3. Draw the pool; run arms 0 to 3 and the static part of 5; compute the flagged sets; draw the label sample.
4. Label (first pass; second pass 20%); run the Python subset; run arm 4 on the labelled subset; seed false statements.
5. Analyse as pre-registered; adversarial review; report including everything that failed.
6. Only then decide whether an acting consumer is built, and under which policy.

## What this experiment cannot show
That the record helps a person; that the software is correct or safe; that results hold for other corpora, languages or agents; anything about a hosted or enterprise deployment.
