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

## Candidate extension: decision application audit
**Status: hypothesis, not an adopted product direction. The mission in `CLAUDE.md` is unchanged.**

In multi-agent software development a human decision can change the requirements or constraints of work that agents have already started or finished. That raises a verification question: what did the human decide, which existing outputs does it affect, did the later changes implement it, and are earlier artefacts now inconsistent with it?

**Possible Agentvow application.** Express one bounded human decision as explicit, checkable claims. After the agent receives the guidance and changes its work, compare the resulting repository state against those claims with the existing deterministic checks and evidence mechanisms. Initial scope: one decision, one affected work item, one before-and-after code comparison. Example: the decision "the existing API contract must stay backward compatible", checked by the public-API diff. What is verified is whether the work satisfies explicit consequences of the decision, not whether the agent understood it. Many architectural or strategic decisions will not reduce to deterministic checks, and they should not be forced into the model.

**Not proposed:** a universal decision graph; a generic human-agent coordination platform; an authority or approval engine; automatic propagation across repositories; any change to the research mission.

**Evidence required before further investment:** (1) real engineering teams show that decision fragmentation is a recurring problem; (2) the consequences of selected decisions can be written as independently checkable claims; (3) existing mechanisms can detect whether they were applied; (4) the audit adds value beyond tests, CI and existing workflow tools.

**Prior art.** BoardroomAI (arXiv, August 2026, evolving decision graphs; prototype on synthetic graphs and a 12-case pilot per its own abstract), Orako, Wakalix, Camunda and agent-workspace products have been named as possibly related. **Their primary sources have not been read (`[snippet]` at best); no novelty or differentiation claim is made.**

**Priority order (owner, 2026-10-30, corrected 2026-10-31):** no team outreach or recruitment; capability comes first and demand evidence comes from benchmarks, public data and dogfooding. (1) Continue the existing research programme and extend the deterministic checkers (API diff beyond Python, differential replay); (2) use our own multi-agent workflow as the dogfooding case for whether decision fragmentation or claim reliability bites; (3) test one bounded decision-application case if a real example appears in that work; (4) read the prior art from primary sources; (5) revisit direction only on new evidence. Passive public signals (package downloads, issues filed against the repository) may inform this but nothing is collected from users without a separate decision.

## Principle: value over novelty (owner, 2026-10-31)
A capability does not need to be new. Where an existing tool already solves the right problem (for example a mature API-diff tool for a language, a mutation tester, a differential-test runner), Agentvow should wrap or adopt it and cite it, and put its own effort into what is missing: independent evidence capture, binding to the exact code state, honest UNKNOWN, and the plain-language record. `NOVELTY_BOUNDARY.md` already puts system novelty at low; that is acceptable. Novelty claims stay subject to the research-honesty rule.
