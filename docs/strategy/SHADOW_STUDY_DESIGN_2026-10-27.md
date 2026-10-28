# Shadow-mode study design: does the evidence layer improve autonomy decisions? (2026-10-27)

Status: **design, not run, not pre-registered yet.** Nothing is merged, approved or blocked by this study; it records hypothetical decisions only (consistent with the human-agency rule).

> **Reframed 2026-10-28.** Agentvow is a claim-verification audit for human overseers, not a safety or autonomy gate (`VISION_AUDIT_2026-10-28.md`). The arms and the "hypothetical continue/escalate/stop decisions" below were an autonomy-gating design; for the audit framing, replace the measures with: precision of CONTRADICTED and recall of real contradictions against an independent second reader; claim coverage; reach (share of changes the audit can run on); honesty of UNKNOWN; and a human reading study (does the record help a reviewer judge the claims correctly and faster than the diff and CI alone). "Unsafe advancement" and "autonomous progression" are not measures for this product. The ground-truth rules, frozen-before-run discipline, second annotator and partner requirements still apply.

## Question
For agent-generated changes, does a policy that uses Agentvow evidence make better advance/escalate/stop decisions than the same team's CI alone, at what cost in escalations?

## Arms (same changes, same code state)
- **A. CI only**: the repository's own CI result at the head commit.
- **B. A + project-native Agentvow evidence** (`--setup auto`; claims checked).
- **C. B + captured-context replay** (capsule from the agent's environment).
- **D. (later)** C + bounded retry, only when the gate returns structured instructions an agent can execute.

Each arm maps its evidence to a hypothetical decision: continue / escalate / stop (≙ allow / needs_acknowledgement / block), computed by `agentvow policy evaluate` with a frozen policy file. Policy frozen before any outcome is looked at.

## Ground truth (the hard part)
1. **Seeded faults**: inject known critical defects into otherwise passing agent changes (extends `docs/research/FAULT_REGRESSION.md` and the E5 design); label is known by construction.
2. **Natural cases**: for disputed cases, an independent assessment by someone other than the annotator of the claims, blind to arm decisions. One annotator behind every earlier number is a known limit; this study needs a second.
3. A *critical requirement* is defined per case before running (a failing hidden test, a seeded fault, a claim-vs-diff contradiction).

## Measures (each reported with counts and intervals, not percentages alone)
- Autonomous progression rate: eligible changes whose hypothetical decision is "continue".
- **Unsafe advancement rate**: "continue" on a change failing a critical requirement. Primary safety measure.
- Escalation and false-block rates: stops caused by missing evidence, and how many were unnecessary.
- Incremental value: cases where C differs from B, and from A, and which side was right.
- Cost: extra runtime, CI minutes, retries, human attention (minutes of reviewer time if a partner takes part).

## Data sources, in order of feasibility
1. **Existing data, no partner**: the B6 captured runs. Of 22 valid runs, 20 had a passing captured replay, but E5 could plant a fault in only **9** (7 had no plantable line, 4 could not be rebuilt from the saved patch; `PRODUCT_EXPLORATION_2026-10.md` section 8). E5 already gives, for those 9: flagged by both contexts 2, captured only 1, silent in both 1, UNKNOWN in both 4, one more silent/UNKNOWN. So this source can only show the mechanics; **nine cases cannot support any claim about decision value**, and E5 has used them once. A new fault generator (more fault types than operator flips, faults in lines the agent did not add) would be needed to reuse the runs, with the policy frozen first.
2. **Plain-pip repository with a design partner** using the gate in shadow mode on real agent pull requests. Needed for any claim about real workflows. Owner supplies the partner (no hosted execution of customer code; the Action runs in their CI).
3. Other agent families and languages: out of scope for the first study; state it as a limit.

## Predictions and falsifiers (written before running)
- Prediction: C resolves some UNKNOWN cases that B cannot, and unsafe advancement in C is no higher than in A.
- Falsified if: C's unsafe-advancement rate exceeds A's, or C differs from B on too few cases to matter (the E5 pattern: one case), or escalation burden exceeds what a reviewer would accept (threshold set with the partner beforehand).
- Do not read more replayability or more checked statements as product value if these fail.

## Risks
- Seeded faults may not resemble natural defects (construct validity).
- Only 9 usable fault cases from existing data (not 22): intervals will be too wide for a decision claim. Treat the offline step as a mechanics check and make the partner shadow run the real test.
- Policy tuning on the evaluation set: freeze the policy first, then run once.
- Reconstruction on non-pip repositories stays UNKNOWN (27-run result); choose repositories accordingly and say so.

## Steps
1. Owner decisions: partner or not; whether arm D is in scope; critical-requirement definitions.
2. Extend the fault generator (beyond operator flips) and rebuild the 4 non-rebuildable runs if possible; freeze the policy; pre-register in this folder. Expect a small N; decide beforehand that an offline result below about 20 faults is reported as mechanics only.
3. Run arms A to C offline; score; adversarial-review the analysis before reporting.
4. Partner shadow run only after step 3 shows C differs from A or B in a useful direction.
