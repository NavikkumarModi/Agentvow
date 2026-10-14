# Changelog

## 0.2.1 (2026-10-14)
The Evidence pack and capture at test time. Same limits as 0.2.0; see `docs/EVIDENCE_PACK.md` and `docs/CAPSULES.md`.
- `agentvow post-test-hook` (Claude Code PostToolUse on `Bash`): captures the environment right after the agent runs a test command; the Evidence pack gains a Timing line (last test run on the final state / files edited after it and packages changed / only a stop-time capture exists). Capsules now carry their source and the files that differed from HEAD.
- Evidence pack item 4, "Not reproduced by this replay": a static, names-only record of environment variables, external programs, network use, service files and git-ignored files the tests reference and a replay does not recreate, plus Python/OS differences between capture and replay (recorded, not judged; never changes a verdict).
- `--hook --evidence-pack`: the Stop hook captures the agent's environment and the detached background run adds the evidence pack to the result (both contexts, or the project-native one alone when no environment can be captured). Never blocks.
- `--evidence-pack`: one report section with three separate dimensions (execution receipt; reproducibility from the captured environment AND from the project's own setup, with an explanation when they disagree; changed-line coverage naming the lines no test ran). Informational; verdicts unchanged. See docs/EVIDENCE_PACK.md.

## 0.2.0 (2026-10-13)
New since 0.1.0: independent replay of agent-declared recipes and of captured environments, changed-line coverage, session audit, and the fixes found by the real-repository studies in `docs/research/forecast_grounding/`. Still not a safety verdict; see `docs/SECURITY_MODEL.md`.
- Capture at claim time: `agentvow capture` records the Python packages of the agent's environment (signed, bound to the exact commit and working tree); `check --from-capsule` and the hook's `--capture --background-tests` replay the tests in a clean environment built from them, with support basis `captured_environment`; fails closed when no capsule matches the state. Based on the Stage B6 result (see docs/CAPSULES.md).
- `--changed-coverage`: with `--run-tests`, the report says how many of the changed executable source lines the tests actually ran, and names the lines and files that no test reached (measured with `coverage` under an empty rc file inside the sandbox; informational, never changes a verdict). Motivated by a post-hoc study where about half of evidence-closed agent patches had changed lines no test ran.
- When a resource guard (size, disk, timeout) stops an environment install, no tests are run in the partial environment; the result says the environment could not be built and why, instead of a misleading "missing dependency".
- The replay environment size guard (default 700 MB) can be raised with `AGENTVOW_MAX_ENV_MB`; found by Stage B5, where it turned heavy but legitimate captured environments into "missing dependency" results (4 of 18 valid runs).
- A recipe that declares `HOME`/`TMPDIR` is still rejected (a redirected HOME could point tools at agent-planted config) but the message now says why and that the replay already supplies an empty, writable HOME and TMPDIR; agent instructions say so. Found by Stage B2: 2 of 32 agents redirected HOME to work around their own sandbox.
- Recipe replay installs `pytest` (the runner only) when the recipe's test command uses it but does not declare it, and states that in the verdict (`meta.runner_supplied`); found by Stage B2, where 11 of 17 failed recipe replays were an omitted runner.
- `--recipe`: claims with preconditions. The agent declares its setup and test command; Agentvow replays only that in a clean sandbox.
- Recipe `prepare` step (run a repository script in the sandbox before the tests); claim extractor accepts singular and suite forms ("The test passes").
- Recipe hardening from a red-team suite (fail-closed environments, tool-config env prefixes, shadowing, symlinked scripts), test-selection guard, default key dir always hidden.
- Recipe replay: monorepo sub-package installs cleaned up with their sources importable per worktree; changed-tests scoping when the declared command runs more than the claim covers; clearer recipe guidance.

## 0.1.0 (2026-10-09)
First feature-complete prototype. Not a safety verdict; see `docs/SECURITY_MODEL.md` and the limits in README.
- Claim checking (tests pass with counts, backward compatible, no downstream impact) against the repository, sandboxed test runs (macOS), CI reading, differential regression rule, fail-closed statuses and exit codes.
- Visual HTML report, markdown summary, JSON; hook for Claude Code and GitHub Copilot (Stop/agentStop) with sealed results; VS Code extension (status bar, notifications, `@agentvow`); GitHub Action; `doctor`; `agent-instructions`.
- Security hardening after three adversarial reviews (sandboxed installs/tests, signed evidence and seals, symlink-safe writes, hardened git).
- Studies and honest limits in `docs/research/`.

Also in 0.1.0 (listed under "Unreleased" at the time of the tag):
- `agentvow demo` and VS Code command "Try the demo"; second adversarial review fixes (see docs/SECURITY_MODEL.md).
- Per-turn change tracking (changes counted since the previous check, signed state file); `--background-tests` for the hook.
- Linux test sandbox (bubblewrap), validated in CI on ubuntu and macos; sandbox guarantees tested directly (tests/test_sandbox.py).
- Renamed from the working name AgentMirror to Agentvow: package/module/command `agentvow`, folder `.agentvow/`, env `AGENTVOW_*`, VS Code ids `agentvow.*`. Results saved under the old `.agentmirror/` folder are not read.
