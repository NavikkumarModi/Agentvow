# Repair-loop experiment: pre-registration (DRAFT v0, 2026-10-30; NOT FROZEN)

**Question.** When a coding agent is shown Agentvow's findings about a flawed change, does one bounded repair attempt resolve the finding without breaking anything, more often than when it is shown only CI output, or only a generic "check your work" nudge? This tests the "agent supervision" stage of `docs/strategy/VISION_SUPERVISOR_2026-10-30.md`, which is a hypothesis with no evidence behind it. **Sandbox only: nothing is merged, pushed, commented or deployed anywhere.** Prior art for the loop itself (Proof-or-Stop, orthogon agent-verify, FalseGreen) is in `NOVELTY_BOUNDARY.md`; no novelty is claimed, only a measured effect.

## 0. Freeze record (to be filled at freeze; any later change to `agentvow/` or `research/repair/` voids it)
Code commit: TBD. Arm-order seed and run seed: TBD (secure random source, unused until freeze). Coding agent: Claude Code, headless, model `claude-sonnet-5-5`, default settings, same for all arms. Environment: TBD (macOS, Python, tool versions as in `SHADOW_EXPERIMENT_PREREG.md` section 0). **Adversarial review of this document must precede the freeze.** Authorisation to clone and run these open-source repositories and an agent on them inside the sandbox: given for earlier studies; **owner to confirm for this one.**

## 1. Units
Pull requests from the shadow pool (`data/shadow2/pool.json`) that are **eligible**: Python, the full Agentvow audit ran (`data/shadow2/full_arm5.jsonl`), arm-5 score at least 2 (a CONTRADICTED or attention finding), non-empty change list, a runnable base environment, and the head commit still fetchable. Expected about 35 of the 43 Python pull requests with score at least 2. **All eligible pull requests are used; none is chosen.** Every ineligible one is listed with the reason. The unit of analysis is the pull request; repositories are clustered.

## 2. Arms (within-unit: every pull request gets all three, in a seeded random order, each from a fresh checkout of the head commit)
- **A generic nudge.** The agent gets the pull-request description and the instruction to review its own change for mistakes and fix them. No findings.
- **B CI output.** Same, plus the head commit's CI result: the names and logs of failing checks, or the sentence "CI reported no failures" when there are none.
- **C Agentvow findings.** Same, plus the Agentvow record's findings for this pull request in plain language (claim, what the check found, evidence, UNKNOWN items), as the product would show a person. No instruction to trust or obey the findings.
One session per cell: bounded to a fixed number of turns and wall-clock time (TBD at freeze, equal across arms), no network except the package index, writes confined to the checkout. One run per cell, so run-to-run variance is **not** estimated; this is stated in the results.

## 3. Outcomes (all decided by deterministic checks on the final state; no LLM in the verdict path)
Baseline for each pull request is the head commit's own audit record.
- **Primary: clean resolution.** The finding that put the pull request in the eligible set is no longer CONTRADICTED or attention when Agentvow is re-run on the final state, **and** no new CONTRADICTED finding appears, **and** no test that passed at the head commit fails at the final state, **and** the final diff against head stays within a scope guard (at most K files, no deleted test files; K TBD at freeze).
- **Secondary:** description-only resolution (the finding went away only because the agent edited its stated description, not the code), reported separately because it can be legitimate (a wrong file claim) or an escape (deleting the claim); regression rate; agent turns and tokens; wall-clock time; the share of runs with no change at all.
- **Excluded from primary:** a resolution that only works because Agentvow now returns UNKNOWN (for example the agent made the environment unreconstructable). Counted as "turned into UNKNOWN" and reported.

## 4. Analysis (descriptive; the sample is too small for strong tests)
Paired by pull request. Report for each arm the clean-resolution count and proportion with Wilson intervals, the paired differences C minus A and C minus B with a repository-cluster bootstrap interval, the regression rate per arm, and the table of discordant pairs. Stratify by finding kind (files, lint, API, tests) and by whether the first-pass audit labels called the pull request positive. Seed from section 0. No multiple-testing claim is made; there is one primary comparison, C minus B.

## 5. Decision rule (what the result may and may not be used for)
Entering stage 2 of the roadmap ("assisted completion") as a product claim requires **all** of: C minus B at least +20 percentage points with a cluster-bootstrap interval excluding zero; C's regression rate no higher than B's; the effect present in at least two finding kinds. With about 35 pull requests only a large effect can show; a null or inconclusive result means **no claim that findings improve agent repair**, and the loop stays an unsupported hypothesis. Nothing here supports an acting consumer or an autopilot: even a positive result concerns bounded repair in a sandbox on historical pull requests.

## 6. Known threats (stated before the run)
- The pull requests were written by other agents and are historical: the repair agent edits someone else's change, without the original task context or conversation. External validity to a team's live workflow is unestablished.
- Eligible pull requests are exactly those Agentvow flagged, so the study cannot say anything about the unflagged majority or false alarms; arm C is shown only true-positive-ish findings (about half the flags were false, `SHADOW_EXPERIMENT_RESULTS.md`). A flagged-but-correct subset is reported separately by first-pass label.
- Findings come from the same checks that re-score the outcome, so "finding gone" is partly circular; the test-regression and scope guards and the secondary outcomes are the independence we have, and a human spot check of 10 clean resolutions is planned (needs a reader).
- One agent, one model, one run per cell; the arm-A nudge also partly measures plain retrying.
- Test replay depends on environments that could not be reconstructed for many pull requests; those are excluded, which biases toward Python repositories with runnable tests.
- The sample is a convenience set of 35 or so, drawn from a pool that is itself a 20% sample of one corpus.

## 7. Stopping and safety
Stop if any run attempts a network write, writes outside its checkout, or touches credentials; the sandbox forbids these and the harness logs them. Any pull request whose repository has disappeared is recorded as such, not replaced. No result is reported before the adversarial review of the results.
