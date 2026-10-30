# Direction draft: independent supervision of AI coding work (2026-10-30)

**Status: DRAFT direction, not a promise.** It replaces nothing yet; `VISION_AUDIT_2026-10-28.md` stays the description of what ships. Every capability below is marked **shipped**, **being tested** or **hypothesis**. The gate in `CLAUDE.md` (no automated consumer until the research gate and a shadow experiment support it) stays closed.

## The problem (from the owner, 2026-10-30)
Agents now produce changes faster than teams can supervise them. The bottleneck is checking, understanding and accepting agent work. Working line: *delegate the coding, review the exceptions.*

## What the evidence supports today
- **Shipped:** an independent record of what an agent claimed, what deterministic checks could establish, what they contradicted and what stayed UNKNOWN (claim extraction, tests and lint replay, files and documentation checks, Python public-API diff, provenance). A person reads it.
- **Being tested:** a narrow attention flag (CONTRADICTED lint or API finding, description-versus-change-list mismatch). In the shadow experiment (`SHADOW_EXPERIMENT_RESULTS.md`) it fires on about 6% of pull requests with precision 0.53, but on only 32 scorable pull requests with labeller-checker overlap, and it misses about 77% of positives. No advantage over CI at a fixed budget is established.
- **Hypothesis, no evidence:** task assurance (comparing the task's acceptance criteria with the change; we have no task text or criteria extraction yet), the repair loop (does feeding findings back help an agent finish correctly), review by exception, and any controlled autonomy.

## Capabilities
1. **Task assurance** (hypothesis). Needs the issue or task text and a way to turn it into checkable criteria.
2. **Independent verification** (shipped, limited). Python-centred; 35% of audited pull requests were unscorable.
3. **Agent supervision** (hypothesis). Structured findings back to the agent, bounded retries, escalation to a person.

## Prior art and differentiation
Not claimed. The closed loop overlaps Proof-or-Stop, orthogon agent-verify (block-once Stop hook), FalseGreen (independent re-execution with attestation), AWS graduated-autonomy patterns (`NOVELTY_BOUNDARY.md`). A differentiation claim needs a supervision-product prior-art scan and evidence from users.

## Roadmap with gates
| Stage | Product | Gate to enter |
|---|---|---|
| 1 | Audit record + attention flag (standalone, no hosted control plane) | shipped; artifacts fixed (empty change list now UNKNOWN, 2026-10-30) |
| 2 | Assisted completion: findings returned to the agent, bounded retry | repair-loop sandbox experiment shows resolution without regressions, compared with CI output alone |
| 3 | Review by exception | stage 2 result plus human-adjudicated labels showing incremental value over CI |
| 4 | Controlled autopilot under policy | shadow experiment on the stage 3 policy; `CLAUDE.md` gate revisited by the owner |

## Success measures
North star: agent tasks accepted without manual intervention, next to independently assessed defect escapes, rework, escalations and cost. Do not optimise claims detected or checkers implemented.

## Open decisions
Whether this reframing replaces the audit framing (owner), and who produces the human labels for the next evaluation.
