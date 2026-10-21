# Product plan (2026-10-21): the replayable receipt for an agent's "tests pass"

Status: a plan for the owner to accept or change. The pilot is dropped (owner decision, 2026-10-21), so this plan does not depend on recruited participants. Evidence cited comes from this repository's studies at feasibility scale; statements about other tools come from their READMEs (`docs/research/forecast_grounding/PRIOR_ART_2026-10-10.md`, update 4). Uniqueness is a potential gap requiring further verification, not an established fact.

## 1. The product in one sentence
After an agent finishes a turn, the developer sees whether its "tests pass" reproduces independently: re-run in a clean sandbox from the environment the agent actually used, with the changed lines the tests never ran and everything that could not be checked, and no claim that the code is correct.

## 2. Who it is for (assumption, untested)
A developer who lets an agent (Claude Code first; Copilot hooks exist but are untested live) change a Python repository on macOS or Linux and wants a second opinion that does not come from the agent. Not for non-Python repositories, not for teams that need an audit service, not as a merge gate (the tool never approves or merges).

## 3. What exists (0.2.1) and what the evidence says it is worth
Exists: `check`, `capture`, replay from a captured environment, changed-line coverage, the evidence pack (receipt, captured-versus-project-setup reproducibility, not-reproduced manifest, timing), Claude Code Stop and PostToolUse hooks, a VS Code extension, PyPI and Marketplace releases.
Evidence: on a random sample of agent PRs the captured environment reproduced 91% of valid passing results (20 of 22) against 55% for zero-config reconstruction; against a stronger CI, Dockerfile and requirements-file baseline capture reproduced 16 of 18 re-runnable runs and the baseline 9; the captures re-ran unchanged 8 days later. One model, Python packages only, one macOS host. No study shows that people act on the output or that replay changes a verdict.

## 4. Roadmap (each item ships value alone and has a check that does not need participants)
**0.3.0, "make the receipt the default" (next).**
1. *(Done 2026-10-21, unreleased; see CHANGELOG.) Project-native comparison uses the strong baseline.* The evidence pack's "project setup" arm is the zero-config ladder today. Move the CI-workflow, Dockerfile and extra-requirements derivation from `research/preconditions/strong_baseline.py` into the product (validated recipes only), so the pack states fairly when capture and the repository disagree. Check (met): 311 Python tests and the 38 validation checks pass; a differential check of the small workflow reader against PyYAML on 531 public workflow files (518 identical, 3 differ, 10 not compared; `scripts/workflow_reader_check.py`); on the 22 valid B6 tasks the product derives the same setup as the research baseline for 15, differs only by an added base `pip install .` line for 6, and differs for 1 excluded run (AGI-Alpha; the product does not validate the CI test command); replaying the 5 re-runnable runs whose derivation differs under the product baseline gave the same result as the registered replay in all 5 (`stageb6_product_replay_2026-10-21.jsonl`, local); a live run showed a dependency that only the CI workflow installs (six) turning the project-native context from "missing dependency" into a pass, with the steps listed in the pack.
2. *(Done 2026-10-21, unreleased; see CHANGELOG and docs/LIVE_TESTING.md.) One-command setup.* `agentvow init` writes the Claude Code hook settings (Stop plus PostToolUse) and prints what it did; `doctor` verifies the path end to end. Check: a clean-machine install test in CI and a live Claude Code run (done for 0.2.1 hooks; repeat).
3. *(Done 2026-10-21, unreleased; see CHANGELOG.) Actionable UNKNOWN.* When the replay cannot build an environment, say which package or file is missing and which context lacked it (the explain codes exist; add the next step). Check: scripted scenarios for the six miss types seen in B6 (missing dependency, credential skip, untracked files, size limit, no tests, test failure).
4. *(Done 2026-10-21, unreleased, in a corrected form; see CHANGELOG.) Untracked-file honesty.* B6 showed 4 of 22 runs cannot be rebuilt from the patch because the agent created untracked files. Capture should record that fact and the replay should say "could not rebuild from the saved state" instead of failing silently. Check: a fixture with an untracked test helper. Correction made while building it: the 4 of 22 B6 runs that could not be rebuilt were a limit of the research harness, which re-applied a saved patch (`git diff` has no untracked files). The product replays the working tree itself, so untracked files are included; the real silent gaps were symlinks (skipped) and git-ignored files (not in a clone), and those are now stated in the receipt and, on a failure, in the next step.
**0.4.0, "trust in other places".**
5. *Linux and CI replay.* Run the capture replay in the GitHub Action on a Linux runner and compare with the macOS result; this is also the missing cross-machine evidence. Check: a pre-registered re-replay of the B6 captures on Linux (needs Docker or a runner; not started).
6. *Fault-injection check.* A scripted set of known-false claims (planted faults) run through capture-based and reconstruction-based replay, as a regression benchmark and the missing "replay changes a decision" evidence.
7. *Second agent.* Hook adapters for one more agent only after its hook format can be tested live.
**Not planned:** non-Python ecosystems, a hosted service, merge or approval actions, an LLM in any verdict, mutation testing as a defect finding (opt-in "executed but not noticed" at most), a new version-control substrate.

## 5. How to know it works without participants
- *Regression benchmark:* a fixed random sample of agent PRs (the B6 protocol) re-run per release; report the reproduced share by context and the reasons for each miss. A release that lowers the capture rate is not shipped without an explanation.
- *Scenario suite:* the six miss types plus the demo, run by `validate_all.sh`.
- *Dogfooding:* the owner uses the hooks on the owner's own agent sessions and records, in a log kept in the repository, the cases where the output was wrong, confusing or ignored. This is one person's experience, not a user study, and should be labelled as such in any text.
- *Public signal:* PyPI and Marketplace install counts and GitHub issues are weak, unverified indicators; they are not evidence that the output helps.

## 6. Messaging rules (so the product does not outrun the evidence)
Say "reproduced / not reproduced / unknown", not "verified" or "safe". State the scope on the first screen: Python packages only; not correctness; one model family tested. Do not say "unique" or "first" without the prior-art caveat. Keep the mutation and real-bug results out of product claims: they show survivors on executed lines are common (29.6%) but not that they are defects.

## 7. Risks
Forges or agent vendors ship independent replay inside their products (the first falsifier). Output ignored by users (cannot be measured without users; dogfooding only). Capture breaks on other platforms or after weeks (E1 so far: 8 days, macOS). Weak positioning if "replay" is read as "verification".

## 8. Decisions for the owner
Audience (individual developers, teams or fleets); open-source posture and goal (reputation, company or research); whether to spend on a second model family and on a Linux/CI check before 0.4.0; whether 0.3.0 scope above is right; paper timing relative to the product (the short paper is separate and does not depend on any of this).
