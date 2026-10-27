# Shadow-mode study design: does the evidence layer improve autonomy decisions? (2026-10-27)

Status: **design, not run, not pre-registered yet.** Nothing is merged, approved or blocked by this study; it records hypothetical decisions only (consistent with the human-agency rule).

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
1. **Existing data, no partner**: B6 runs (22 valid, captured) and the AIDev sample, with seeded faults added to the replayable ones. Fast; limited by 22 captured runs and one agent family.
2. **Plain-pip repository with a design partner** using the gate in shadow mode on real agent pull requests. Needed for any claim about real workflows. Owner supplies the partner (no hosted execution of customer code; the Action runs in their CI).
3. Other agent families and languages: out of scope for the first study; state it as a limit.

## Predictions and falsifiers (written before running)
- Prediction: C resolves some UNKNOWN cases that B cannot, and unsafe advancement in C is no higher than in A.
- Falsified if: C's unsafe-advancement rate exceeds A's, or C differs from B on too few cases to matter (the E5 pattern: one case), or escalation burden exceeds what a reviewer would accept (threshold set with the partner beforehand).
- Do not read more replayability or more checked statements as product value if these fail.

## Risks
- Seeded faults may not resemble natural defects (construct validity).
- Only 22 captured runs: intervals will be wide; report them and do not generalise.
- Policy tuning on the evaluation set: freeze the policy first, then run once.
- Reconstruction on non-pip repositories stays UNKNOWN (27-run result); choose repositories accordingly and say so.

## Steps
1. Owner decisions: partner or not; whether arm D is in scope; critical-requirement definitions.
2. Build seeded-fault variants of the replayable B6 runs; freeze policy; pre-register in this folder.
3. Run arms A to C offline; score; adversarial-review the analysis before reporting.
4. Partner shadow run only after step 3 shows C differs from A or B in a useful direction.
