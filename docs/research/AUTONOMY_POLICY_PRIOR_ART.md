# Evidence-gated autonomy: prior art (2026-10-27)

Question: is "an independent evidence layer whose states map by policy to agent actions (continue / retry / restrict / escalate / stop)" already done? Gate: this must be settled before any autopilot mechanism is built (CLAUDE.md, research before implementation).

Source status: `[read]` = full text fetched and the cited sections read; `[partial]` = full text fetched, only the cited passages read; `[snippet]` = search-result summary only (not citable as settled fact).

## Read

| Work | What it does | Relation to Agentvow |
|---|---|---|
| **Proof-or-Stop** (Huang et al., arXiv 2607.14890) `[partial]`: abstract, problem statement, the admissibility definition (Eq. 2), receipt table, related-work table, threats | Lifecycle states (reviewed, tested, DONE, ready-to-merge) are claims. A transition is allowed only if evidence is *Fresh* (bound to the tracked source state), *Complete*, *IntegrityVerified* (signed local receipts), *ProducerAuthorized*, *ExecutionAttested* (command, args, cwd, exit code, output digest), supports the claim, and the outcome is accepted. Missing or stale evidence makes the loop repair, retry boundedly, or safe-stop. Evaluation: unattended loop 10/10 scenarios with no false DONE; 18 tamper classes rejected; 9,240-cell ablation, wrong-artifact amplification 31/1800 (naive loop) vs 2/1800 (gated). | **Closest work.** It already has evidence states mapped to automatic lifecycle actions (advance / retry / stop), bound to source state, deterministic. It states that its receipts "do not independently prove execution truth against a compromised runner". The receipts are produced by the actors' own host with a local key. No independent replay of the agent's environment. |
| **Bhati, Agentic SDLC** (arXiv 2609.04681) `[partial]`: §11–12 | "Agentic Autonomy Budget": autonomy is a budgeted privilege limited jointly by money/compute, reliability/risk (blast radius, reversibility) and human attention; a control-plane architecture with a risk classifier and escalation. Conceptual objective function; "proposed constructs to be validated". | Prior art for the *autonomy budget* and *control plane* framing. Budget inputs are cost and risk, not independently checked evidence. No evaluation. |
| **ActPlane** (Zheng et al., arXiv 2606.25189) `[partial]`: abstract, introduction | Agents declare policies; an eBPF engine enforces them at the OS (e.g. "run tests before commit"), with semantic feedback. | Prior art for external, enforced policy over agent actions. Enforces *what the agent may do*; it does not check whether a claim the agent made is true. |
| **Engineering Reliable Coding Agents** (Jarmak, arXiv 2608.13867) `[partial]`: ch. 7 lifecycle passages, search hits | Separates attempt lifecycle from logical-work lifecycle. A worker's self-report moves an attempt only to "outcome ready"; "only independently observed evidence completes logical work". Retry policy, unknown external state as a side state, escalation chapter. | Prior art for "self-report is not completion", for UNKNOWN as a state and for retry-vs-terminal policy. |

## Snippet only (not citable as fact)
[Agentic autonomy levels](https://addyosmani.com/blog/agentic-autonomy-levels/), [Augment autonomous loop](https://www.augmentcode.com/guides/autonomous-engineering-loop), [autonomy-budget pattern](https://aiuxplayground.com/pattern/autonomy-budgets), [escalation-threshold pattern](https://aiuxplayground.com/pattern/escalation-thresholds), [Arkforge](https://arkforge.tech/en/blog/agent-autonomy-budgets-runtime-enforcement), [ATXP](https://atxp.ai/blog/how-to-ramp-agent-autonomy), [policy-as-code guardrails](https://hoop.dev/blog/guardrails-for-agent-runtimes/). Several practitioner pieces say merge and deploy stay human-controlled; vendor material; not verified.

## Boundary decision

**Already done (reject as a novelty claim):**
- External policy mapping evidence states to continue / retry / stop / escalate for coding agents (Proof-or-Stop, Jarmak, Bhati).
- Autonomy as a budget limited by risk and blast radius (Bhati, practitioner patterns).
- "Self-report is not evidence" (Proof-or-Stop, Jarmak).
- Source-state-bound freshness of evidence (Proof-or-Stop; ours is `reality.git_tree_hash`).

**Potential gap requiring further verification** (narrow):
- The *evidence source* for such a policy being an **independent replay** of the agent's claimed result, in a clean environment rebuilt from a captured package set, with the replay's own provenance (`capture_authenticated`, `partial_replay`, `harness_warning`) as policy inputs. In Proof-or-Stop the evidence comes from the same host and actors under a local-key trust model; our B6 result (20/22 valid runs independently reproduced from capture) is the relevant empirical fact. Not yet shown: that the independence changes any action outcome compared with their style of attested self-run evidence. That comparison is the only experiment that would support a novelty claim here.

**Not read yet** (blockers for any claim): the rest of Proof-or-Stop (§7 onward, cross-vendor review), Jarmak ch. 8 and 16, the ActPlane evaluation, patent search (unchanged blocker from `NOVELTY_BOUNDARY.md`).

## Consequences for the design
1. No autopilot mechanism is a research contribution. If built, it is engineering on top of the policy engine and is labelled so.
2. Any evaluation must include a Proof-or-Stop-style baseline: the same actions driven by attested self-run receipts instead of independent replay.
3. The honest hypothesis is narrow: "independent replay evidence changes at least some continue/stop decisions compared with agent-produced receipts, in the cases where the agent's environment or harness differs from a clean one."
