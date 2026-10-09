# Pilot P0 — cost-lean plan (replaces "build v0.1 first")

## Reframe (decision taken)
The contribution is **an evaluation**, not a novel mechanism. Hypothesis under test: *decision-gated UNKNOWN (counter-state enumeration filtered by an explicit approval rule) catches more harmful agent changes than existing impact/verification tooling at a matched review rate.* Novelty language is dropped until P0 supports it (see RISKS.md A1/A2).

## Principles
- Cheapest falsifier first; every stage has a stop rule. No stage starts until the previous passes.
- No product code, no UI, no human subjects until P0 passes.
- Reuse existing tools as arms (Assay, regression test selection, mutation testing); don't rebuild them.
- Deterministic collectors; LLM calls capped and logged (cost is a reported outcome).
- The decision-rule table is written and frozen **before** looking at outcomes, and a rule-aware version of every baseline gets it too (RISKS C1).

## Stages and stop rules

| Stage | Work | Rough cost | Stop if |
|---|---|---|---|
| S0 Feasibility (≈1–2 days) | Identify a public source of agent-authored PRs/patches with objective outcome labels (reverted, follow-up fix, failing CI after merge, hidden-test failure). Candidates to verify, not assumed: SWE-bench-family trajectories, agent-authored PRs on open GitHub repos. Check licences and that repos build. | Low; no LLM | Fewer than ~30 labelled items with ≥8 true failures that tests/CI alone didn't catch |
| S1 Pilot-lite (≈1 week) | 30 items (+10 hand-made traps). Arms: (a) Assay-style cone check, (b) RTS/impact + mutation score, (c) always-UNKNOWN trivial baseline, (d) **hand-simulated** enumerator as upper bound (a human applies the frozen rule; no code). | Low; zero or minimal LLM | Hand-simulated upper bound isn't ≥10 pts recall above best baseline at matched REVIEW rate → **stop, publish negative result/notes** |
| S2 Add LLM arm (days) | One rule-aware LLM-with-tools arm, same collectors and same rule, token budget capped per item. | Moderate; fixed cap | LLM arm matches the hand-simulated upper bound → mechanism not needed; reframe around cost/UX only |
| S3 Scale to 60–100 items | Only if S1–S2 pass. Out-of-model audit: ≤40% of real failures outside the counter-state vocabulary. REVIEW rate on clean items ≤30%. | Moderate | Out-of-model >50%, or clean-PR REVIEW rate >30% → stop |
| S4 Minimal enumerator | Code only the counter-state classes S1–S3 showed matter (expected 2–3), fail-closed, with property tests that collector failure never renders OK. | Engineering | Any collector-failure path renders OK |
| S5 Human pilot | Small within-subject study with tool-wrong trials, non-inferiority margin on time. | Highest; deferred | Complacency or slower without accuracy gain |

## Measurements (S1 onward)
Recall of harmful changes, REVIEW rate on clean items, precision, share of failures outside the model, UNKNOWN-silently-SAFE incidents (must be 0), cost per item (tool time, tokens). Report confidence intervals; with ~30 items state plainly that results are directional only.

## Cost controls
- Stop rules above; negative result is an acceptable deliverable.
- Hand-simulation before code.
- Cache collector outputs per snapshot (also tests the reuse idea cheaply).
- Pin model/tool versions; log every LLM call.

## Open inputs needed from you
1. Willingness to spend a small LLM budget at S2 (suggest a hard cap you choose).
2. Whether any real agent session transcripts/PRs of your own may be used as pilot items (the highest-quality, cheapest data source).
