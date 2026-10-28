# Vision proposal: evidence admission for autonomous software changes (2026-10-27)

Status: **a proposal for the owner, not a decision and not a research claim.** It follows an external review of `main` at 74de6cb. It does not replace `VISION_2026-10.md`; it narrows its option B. Per `CLAUDE.md`, nothing here is called novel: "Potential gap requiring further verification." The autonomy gate in `docs/research/NOVELTY_BOUNDARY.md` is **not passed**.

## Correction first
"Evidence gates autonomy" is **not** a defensible novelty claim. Proof-or-Stop (July 2026 preprint; only partly read, so treated as `[snippet]` in `AUTONOMY_POLICY_PRIOR_ART.md`) already binds fresh, code-state evidence to lifecycle advance/retry/stop. ProofRun reruns checks on the exact pull-request head. ActPlane enforces agent policy at OS level. An autonomy budget or score alone does not distinguish Agentvow.

## Proposed vision
Let teams delegate software changes to coding agents without reviewing every step, by requiring fresh, independently generated, source-bound evidence before each consequential lifecycle transition, and by stopping or escalating when critical evidence is missing or contradicted.

Category: **evidence admission for autonomous software changes.** Agentvow establishes what the evidence supports for one code state, how it was produced, and what remains unchecked. An external policy decides which actions are allowed. Internal principle: *evidence before autonomy*.

## The wedge (what may be distinct; unproven as a moat)
Compare evidence from the **observed agent execution context** (captured packages) with evidence **reconstructed from the project's declared setup**, keeping provenance, replay completeness and uncertainty explicit, and expose the result to a machine-enforceable policy.

What supports it: E3 (18 replayable runs: capture reproduced 16, repository-derived setup 9; seven only capture reproduced, none the other way) and B6 (91% of valid runs). What does not: E5 (planted faults) is weak evidence that replay changes decisions. Both are small, Python-only, one agent family, one host; reproducibility is not defect detection.

Known limit on the reconstruction half: four experiments, 27 repository runs, zero verdicts gained on non-plain-pip third-party pull requests (`project-reconstruction-limits`). On such repositories the comparison often has one side only. A pilot should use plain-pip repositories or a repository that supplies its own environment.

A captured bundle is **supplied and unauthenticated** (`TRUST_MODEL.md`): the verifier checks its binding to the code and replays it; it cannot establish that the agent used those packages.

## Offline shadow results so far
Run 1 of the offline study (`SHADOW_FAULTS_RESULTS.md`) was confounded and its reading is withdrawn as inconclusive; one thing it did show is a trade-off to measure: a context that can run the tests turns an honest "escalate" into "continue" on faults the tests do not see. Run 2 (controlled, `SHADOW_FAULTS_RESULTS_V2.md`) found identical decisions in the 19 faults where both contexts can run; capture changed decisions only where the project-native context could not run at all.

## Obligations per transition (not one verdict, not a score)
| Transition | Policy approach |
|---|---|
| Continue editing / attempt a repair | Permit bounded work with non-critical gaps; keep unresolved obligations listed |
| Mark a task complete | Fresh evidence for the claims that define completion |
| Open or advance a pull request | The team's agreed checks; unresolved critical evidence visible |
| Merge | Block on contradiction and missing critical evidence; partial or suspicious evidence by explicit policy |
| Deploy | Separate release obligations; a green code test is not enough |

A result for one claim under one context never authorises a more consequential action. No "autonomy percentage", no accumulated evidence-debt number: neither can be calibrated with current evidence.

## What not to do
- Do not add claim kinds indiscriminately: the new checkers gave a new verdict path to about 15 points of 152 labelled statements; the gap is what a change *does*.
- Do not build an orchestrator; supply evidence decisions to existing runtimes.
- Do not sell a safety guarantee; passing checks are evidence within a scope.

## Conflict with current rules (owner decision needed)
Retry/continue/restrict outcomes that act without a person edge toward the autopilot mode. `CLAUDE.md` says Agentvow informs the human and never silently approves or merges. Shadow mode (see `SHADOW_STUDY_DESIGN_2026-10-27.md`) stays inside that rule because it only records hypothetical decisions. Changing the rule is the owner's call.

## Success criterion
More eligible agent changes advance without human intervention than under the team's existing workflow, with an independently audited, acceptably low unsafe-advancement rate and a manageable escalation rate. More claims checked or more replays are intermediate measures only.

## Deployment facts to keep straight
PyPI has 0.4.4 (published 2026-10-26); `main` carries 0.4.5 content (statement checkers, `description_mismatch`) unpublished, release on hold. A pilot must pin 0.4.4 or install from a source checkout and say which.
