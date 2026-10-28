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

## Owner decision 2026-10-28 (later the same day): the record may also feed an automated policy
After the study results the owner chose that the evidence record's consumer may be, besides a person, **a policy that acts without a person** ("also an autonomous gate"). This is recorded as a direction, not a feature, and it **does not take effect until conditions 2 and 3 are met**:
1. **(Done 2026-10-28, owner's go-ahead: `CLAUDE.md` "Human agency" now carries the amended wording, including the research-gate and shadow-experiment preconditions.) `CLAUDE.md` said until then** Agentvow informs the human and never silently approves, rejects, deploys, merges or alters the user's system. The owner must amend that rule in `CLAUDE.md` (proposed wording: "Agentvow produces the evidence record. A separately configured policy chosen by the owner or team may act on it; Agentvow itself never grants autonomy or approves anything, and every automated action is logged with the record that caused it.") before any automated action is built. Until then the default and the only implemented behaviour remain: a person, or a policy a person wrote, reads the record.
2. **Prior art first** (`CLAUDE.md`: research before implementation). Evidence-gated autonomous lifecycles (Proof-or-Stop and similar, only partly read), independent re-execution (ProofRun), OS-level policy (ActPlane) and autonomy budgets exist. The autonomy gate in `NOVELTY_BOUNDARY.md` is not passed; no novelty is claimed.
3. **Evidence that a record changes a decision** is the next experiment, run in shadow mode (hypothetical decisions only, nothing acts): does an evidence record change what a person or a written policy would decide, correctly, compared with the diff and CI alone? The stage 2 results are the reason for caution: tests UNKNOWN on every case, impact flags right in 4 of 9.
4. **Design constraints:** the tool emits the record and, optionally, a machine-readable outcome (the existing `allow` / `needs_acknowledgement` / `block` policy result); the component that acts on it is separate, configured by the owner, and logs each action with the record. UNKNOWN is never converted to support. A supplied capture bundle stays unauthenticated, so "the agent does not define its own evidence" holds for repository replay and not yet for captured environments.
5. **Wording for the product:** "accountability layer for autonomous coding agents: it turns an agent's report into an evidence record (supported, contradicted, unknown, attention) for people and policies." No safety guarantee, no verdict beyond what the evidence supports, no test-verification or human-benefit claim until measured.
