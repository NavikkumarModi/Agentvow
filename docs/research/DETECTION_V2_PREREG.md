# Detection study v2 — pre-registration (written 2026-10-09, BEFORE screening results were looked at)

Why: `DETECTION_STUDY.md` showed detection on real CI-failing PRs was not demonstrated (0 of 19 contradicted; 15 never produced a usable run), and the `--new-test-failures review` refinement was tuned on those same PRs (in-sample). This study uses **fresh PRs** and **rules fixed here**, so the result can falsify the tool.

## Questions
- **Q1 (recall, conditional):** among agent PRs whose CI test job FAILED and whose local suite could be run, in what share does Agentvow (a) say CONTRADICTED, (b) say REVIEW REQUIRED only under `--new-test-failures review`, (c) say UNKNOWN with no alert, (d) say SUPPORTED/NOT_CONTRADICTED (a miss)?
- **Q2 (false alerts):** among CI-PASSING controls that ran, in what share does it alert (CONTRADICTED, or REVIEW REQUIRED under `review`)?
- **Q3 (reachability):** what share of CI-failing PRs reach a usable local test run with the shipped zero-config setup (`--setup auto`)? (Reported as a funnel; failures are categorised, not hidden.)

## Population and sampling (fixed)
1. AIDev PRs (hao-li/AIDev v4) in repositories whose language is Python, non-empty body, where `claims.extract` finds a `tests_pass` claim, **excluding every PR already screened in `data/ci_study.jsonl`**. Random sample, seed 2027, up to 250 per agent (all agents in the data).
2. Ground truth label from the GitHub check-runs API at the PR head commit, exactly as `scripts/ci_study_analyze.py` classifies (`TEST_JOB` regex; CONTRADICTED-by-CI = a completed test job concluded failure; SUPPORTED-by-CI = test jobs all success). PRs without a conclusive test job are dropped. **CI is the label, not the detector input:** Agentvow is run WITHOUT `--ci`.
3. Eligible: repository size < 300 MB. At most 3 PRs per repository (random) to limit clustering. All eligible CI-failed PRs are run; CI-passed controls are drawn to match the number of CI-failed PRs, preferring the same repositories.
4. Environment: the shipped `--setup auto` ladder only (no per-project hand setup), 240 s per test run, sandbox as shipped. A PR "reaches a usable run" only if the base run has at least one passing test.

## Detector configurations (both fixed now)
- Default: `--new-test-failures unknown`.
- Review: `--new-test-failures review` with the rule exactly as in the repository at the commit that contains this file (unresolved failures in tests added/changed by the PR raise attention; ignored when the suite had no passing tests at base).
Verdict classes: CONTRADICTED, REVIEW REQUIRED (UNKNOWN + attention), UNKNOWN, SUPPORTED / NOT_CONTRADICTED.

## Analysis (fixed)
Report counts, Wilson 95% intervals, and repository-level counts (a repository counts once for "at least one"). Q1 is conditional on a usable run and says nothing about PRs that never ran; Q3 states the unconditional funnel. No rule will be changed after seeing these results; any change is reported as a post-hoc follow-up needing yet another fresh sample.

## Known limits (stated in advance)
CI failure is an imperfect label (flaky or environment-specific jobs); one annotator for failure categories; AIDev's agent mix is dominated by a few repositories; only Python; zero-config setup will leave many PRs unreachable; claims are taken from PR bodies, not agent transcripts.

## Amendment 1 (2026-10-09, before any screening result was inspected)
The explicit-claim population is nearly exhausted: only 214 claiming PRs not already screened in `ci_study.jsonl` exist, all from Copilot. The question "does the checker flag a false 'tests pass' statement?" does not need the statement to come from the PR body, so the population is widened: fresh Python-repository AIDev PRs of any agent (random, seed 2027, up to 400 per agent, not in `ci_study.jsonl`), and the statement checked is the fixed sentence **"All tests pass."** For PRs whose own body claims tests pass (the 214 Copilot PRs and any others) the PR's real claim is checked instead and they form a separate reported stratum ("real claim" vs "hypothetical claim"). All other rules above are unchanged. This is a design change made before looking at outcomes; it is disclosed in the results.

## Amendment 2 (2026-10-09; written after the first 13 of 140 result rows were seen — all unusable because of missing dependencies — and before any further result)
The primary arm (A) is the shipped zero-config ladder, as pre-registered, and its funnel (Q3) is reported as is. Because reachability will probably be low, a **second arm (B, "install-the-missing-module")** is added and reported separately and never merged into A: for PRs where arm A did not reach a usable run, the runner reads the "missing dependency" stop, installs the named top-level modules in the sandboxed pip (distribution name = module name with `_`->`-`, plus a fixed alias table for yaml, PIL, cv2, sklearn, bs4, dotenv, dateutil, jwt, git, attr, magic, serial; at most 6 per round, 3 rounds, 12 in total) and retries the base run. Everything else (detector configurations, analysis, limits) is unchanged. Arm B changes only how often a PR becomes runnable; it can raise or lower apparent recall, so it is a sensitivity analysis, not the headline. Safety note: installing a name taken from a hostile repository's import error is a dependency-confusion risk; installs run inside the sandbox on a disposable environment and the arm is research tooling, not a shipped feature.

## Deviation log
- 2026-10-09: the first reproduction launch used two parallel workers; their cleanup deleted each other's shared pip temp directory, so every environment install failed (80 of 140 rows, all "missing dependency", 0 usable). Those rows are invalid (kept as `data/detection_v2_results_INVALID_2worker_race.jsonl`, not used in any estimate). The study was restarted from scratch with one worker. The same run configuration otherwise.
- 2026-10-09 (second invalid start): the one-worker restart also produced 0 usable runs. Cause found by reproducing one repository by hand: the script passed ONE shared `home` directory to `envsetup.build_env`, which caches the project copy in `<home>/proj`; every repository after the first was therefore installed from the first repository's source. This is a bug in the study script (the shipped CLI uses a fresh `home` per run), not in the product. Fixed (per-repository home); those rows are kept as `data/detection_v2_results_INVALID_shared_home.jsonl` and not used. The study restarted a third time from scratch with the same sample and rules.
