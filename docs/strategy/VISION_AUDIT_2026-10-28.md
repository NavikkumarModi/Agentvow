# Vision: an independent claim-verification audit for human oversight of coding systems (2026-10-28)

Status: owner's framing, written down. It **replaces** the earlier proposal `VISION_PROPOSAL_2026-10-27.md` (autonomy-admission framing), which is withdrawn: Agentvow is not here to decide whether coding is safe, to gate autonomy or to make agents safer. Per `CLAUDE.md`, nothing here is called novel: "Potential gap requiring further verification."

## What Agentvow is
An **audit system**. When a semi-autonomous or autonomous coding system says what it did ("tests pass", "only these files changed", "docs updated", "lint is clean"), Agentvow independently checks those claims against what can be observed and gives the human overseer a plain-language record: what was claimed, what was observed, what the evidence supports, what could not be checked and why.

The human decides. Agentvow does not approve, reject, merge, deploy or alter anything, and it does not claim the software is correct or safe. A passing check is evidence within a stated scope, not a certificate.

## What it is not
- Not a safety layer, autonomy controller, approval bot, or orchestrator.
- Not another AI code reviewer: no LLM decides a verdict.
- Not a replacement for CI. It audits the *statements* made about the work and the evidence behind them.

## What the audit gives a human
1. **Claim ledger.** Each statement the system made, as a CLAIM, with its verdict: CONTRADICTED, SUPPORTED, NOT_CONTRADICTED or UNKNOWN. Separate CLAIM / OBSERVATION / EVIDENCE / INFERENCE / ASSUMPTION / UNKNOWN.
2. **Provenance and independence.** Where each piece of evidence came from (a replay the tool ran, a supplied capture, a prior receipt) and how independent it is of the claimant: independence is a vector (framing / evidence / mechanism / authority), never one score. A supplied capture bundle is unauthenticated.
3. **What is still not true or not shown** from the communication: contradictions, claims with no verdict path, and "no claim about tests or impact found".
4. **UNKNOWN as a result.** Missing evidence is reported as missing, with the reason, never converted into confidence.
5. **A durable record** (receipts, check run, job summary) a reviewer can read later. Policy files let a team say how the record is shown (e.g. whom a person must acknowledge it with); they are a way for humans to consume the audit, not an autonomy mechanism.

## The wedge under test (potential gap requiring further verification)
Auditing a claim often needs the environment the claimant actually used. Comparing evidence from the observed agent environment with evidence reconstructed from the project's declared setup, while keeping provenance, completeness and uncertainty explicit, is how Agentvow tries to get a verdict where the repository alone cannot run.
- Supports it: E3 (captured packages reproduced 16 of 18 replayable runs vs 9 for repository-derived setup); B6 (20 of 22 valid runs).
- Does not show: that the comparison changes what a human concludes. Offline fault runs (`SHADOW_FAULTS_RESULTS_V2.md`) found identical results where both contexts run, and capture adding a result only where the project-native context could not run.

## How to judge it (audit measures, not safety measures)
- **Precision of CONTRADICTED**: how often a flagged contradiction is real when a human checks (statement checkers: 56% → 91% over five rounds on ~1,300 real descriptions; each round found new misreadings).
- **Coverage**: the share of a system's statements that have any verdict path (about 15 points of 152 labelled statements gained one from the new checkers); the largest gap is claims about what a change *does*.
- **Reach**: how often an audit can be run at all on a third-party change (UNKNOWN dominates outside plain-pip repositories; 27 reconstruction runs gained no verdicts).
- **Honesty of UNKNOWN**: UNKNOWN must not hide an answer that was obtainable, and must never turn into confidence.
- **Reproducibility of evidence** across machines and runs.
- **Value to the human reader**: whether the record lets a reviewer see, faster and more accurately, what is true and what is not about what was claimed. This needs a human study; it has not been done.
Unsafe-advancement and autonomy-progression rates are **not** measures for this product.

## Principles
1. Never treat a system's output as evidence because it is confident.
2. Bind every result to the exact code state and conditions checked.
3. Prefer independent deterministic evidence; another LLM's agreement is not independent.
4. UNKNOWN is a valid result and is explained in plain words, with scope, consequence and evidence.
5. The human keeps agency. Agentvow informs.
6. No universal guarantee; state what was and was not checked.

## Deployment facts
PyPI has 0.4.4 (published 2026-10-26). `main` carries 0.4.5 content (statement checkers, `description_mismatch`), unreleased and on hold. A pilot must pin 0.4.4 or install from a source checkout and say which.
