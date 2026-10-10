# Paper frame, re-scoped to the measurements (2026-10-10)

Status: a framing document, not a draft. It states what the evidence supports, what it does not, and what a paper could honestly claim. Novelty is **a potential gap requiring further verification** (full-text comparison with 2610.00425, SetupBench, ResearchEnvBench, ProofRun and reproducible-trajectories is still open; the patent search is not done; see `../NOVELTY_BOUNDARY.md`).

## 1. The question, restated
When a coding agent says "the tests pass", **can an independent party obtain a determinate verdict on that claim, and what does it take?** Three execution contexts are compared on the same frozen patch: the agent's environment, a replay from the repository's own declarations, and a replay from a recipe the agent itself declares. No LLM sits in any verdict.

The earlier headline, "agent-declared recipes close a large accountability gap", is **withdrawn as a general claim**. It holds only where hidden state exists by design.

## 2. What was measured (all numbers from this repository's own studies)
| Study | Design | Result | What it supports |
|---|---|---|---|
| Detection v2 (140 PRs) | real agent PRs, 70 CI-failed + 70 controls | a usable independent run for 27/140 (19%, CI 14-27) | **Reachability is the bottleneck**: most real claims get no determinate verdict because the environment cannot be rebuilt |
| Pilot (12 designed tasks, 36 runs) | traps with environment state hidden from the repository | zero-config replay 42-50%; agent's recipe 75-83%; 19/20 expressible recipes sufficient | A recipe recovers claims whose truth depends on state outside the repository. **Designed to favour the recipe; not a rate** |
| Stage A (instrument validity) | 24 runs, ablation, determinism | determinism held, 0 validator escapes; recipe 23/24 vs zero-config 10/24 | The instrument is reliable on designed tasks |
| Red team (pre-fixed expectations) | adversarial recipes and agents | several bypasses found and fixed (env fallback, shadow install, symlinked prepare, option injection) | The replay path fails closed |
| **Stage B1 (real repositories, N = 32)** | real merged agent PRs, S0-sandboxed Claude Code | repository-only replay 31/32 (97%); recipe replay 24/30 (80%) as run, 28/30 on a setup-sufficiency reading after instrument fixes; exact `pip freeze` 31/32; **recipe adds 0 reproductions beyond the repository-only replay** | On repositories whose setup is declarable, the gap is small. 1/32 claims was true but non-portable |
| S2 screening | 246 + 56 attempts, extended CI-derived recipes | S2 = 2 tasks; extending the extractor to tox/make/uv/poetry yielded 0 more | Real CI setups are mostly not expressible as a pip-only recipe; **the stratum where recipes should matter cannot be filled by parsing CI** |

## 3. Claims the evidence supports (candidate contributions)
1. **A measurement design**: claim-level accountability across execution contexts on one frozen patch, with the support basis stated (`agent_recipe` versus repository-native). Potentially novel in combination; each part has neighbours.
2. **A reachability funnel on real agent PRs**: 19% of PRs reach a usable run; most losses are environment, not logic. (Detection v2.)
3. **A negative-and-bounded finding**: on declarable real repositories (selected because zero-config already reproduces), repository-only replay reproduced 97% of agents' passing claims and agent-declared recipes added none. The pilot's gap does not generalise past designed hidden state. Negative results of this kind are rarely reported.
4. **Where a recipe is needed is where verification is hardest to study**: S2 scarcity is itself a result.
5. **Instrument lessons, reported as findings**: an honest declaration can be rejected by the verifier's vocabulary (4/4 generated-fixture recipes in the pilot; `PYTHONPATH` in 2/32 real runs); a declared test command broader than the claim produces false non-reproduction (3/32); a flattened `-e dir` silently installed an unrelated PyPI package in monorepo replays. Each is a way a replay-based verifier can mislead and was found only by running on real repositories.
6. **A fail-closed, deterministic replay instrument** with an adversarial test suite (open source, MIT). An artifact, not a research claim.

## 4. Claims the paper must NOT make
- That recipes "close the accountability gap" in general, or that the pilot's 42% to 83% is a rate.
- That agents omit dependencies, that declared and actual dependencies differ, or that necessity/padding can be measured: all taken by prior work (`DIRECTION.md`, update of 2026-10-09).
- Anything about dishonest agents: in every study the agents' claims were true in their own environment and no agent edited protected tests.
- Anything about other model families (Claude only), larger tasks (median change 45 lines), or natural bug reports (reconstruction tasks).
- That the S1 numbers are a population rate: S1 is conditioned on zero-config already working.
- Novelty of any single component without the SOTA gate.

## 5. Structure that fits the evidence
1. Problem: a completion claim is true under conditions the reader cannot see; measured consequence is the 19% reachability.
2. Instrument: recipes with preconditions, fail-closed replay, support basis. (Short; the artifact is the contribution.)
3. Study 1, designed hidden state (pilot, Stage A): shows what a recipe can capture and the validity of the instrument. Labelled as an instrument test.
4. Study 2, real repositories (B1): the main empirical result, negative and bounded; post-hoc instrument analysis kept separate from the registered table.
5. Where recipes would matter and why it could not be tested (S2 scarcity; CI not expressible).
6. Threats, including the selection effect, one model family, one run per task, N = 32 (feasibility, no confirmatory inference).
7. Related work, after the full-text comparison; novelty stated only as "potential gap" until the gate passes.

## 6. Venue fit and what it would take to strengthen it
- As it stands: a **measurement / negative-result paper plus an artifact**, suited to a workshop or an MSR-style data/tool track; not to a venue wanting a positive method result.
- To reach a stronger claim, one of: (a) a stratum with real hidden state at N >= 40 (needs a source other than CI parsing, for example agent-authored recipes validated against truth on repositories chosen without the zero-config filter); (b) a second model family; (c) natural bug reports instead of reconstruction tasks. Each costs real money or time and is a decision for the project owner.

## 7. Open items before any draft
Full-text read of 2610.00425, SetupBench and ResearchEnvBench; the patent search; the cause of the one non-portable case (`telegram#4908`); an adversarial review of this frame (the project rule requires one before a major milestone).
