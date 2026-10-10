# Changelog

## 0.1.0 (release candidate, 2026-10-08)
First feature-complete prototype. Not a safety verdict; see `docs/SECURITY_MODEL.md` and the limits in README.
- Claim checking (tests pass with counts, backward compatible, no downstream impact) against the repository, sandboxed test runs (macOS), CI reading, differential regression rule, fail-closed statuses and exit codes.
- Visual HTML report, markdown summary, JSON; hook for Claude Code and GitHub Copilot (Stop/agentStop) with sealed results; VS Code extension (status bar, notifications, `@agentvow`); GitHub Action; `doctor`; `agent-instructions`.
- Security hardening after three adversarial reviews (sandboxed installs/tests, signed evidence and seals, symlink-safe writes, hardened git).
- Studies and honest limits in `docs/research/`.

### Unreleased
- `agentvow demo` and VS Code command "Try the demo"; second adversarial review fixes (see docs/SECURITY_MODEL.md).
- Per-turn change tracking (changes counted since the previous check, signed state file); `--background-tests` for the hook.
- Linux test sandbox (bubblewrap), validated in CI on ubuntu and macos; sandbox guarantees tested directly (tests/test_sandbox.py).
- Renamed from the working name AgentMirror to Agentvow: package/module/command `agentvow`, folder `.agentvow/`, env `AGENTVOW_*`, VS Code ids `agentvow.*`. Results saved under the old `.agentmirror/` folder are not read.
- `--recipe`: claims with preconditions. The agent declares its setup and test command; Agentvow replays only that in a clean sandbox.
- Recipe `prepare` step (run a repository script in the sandbox before the tests); claim extractor accepts singular and suite forms ("The test passes").
- Recipe hardening from a red-team suite (fail-closed environments, tool-config env prefixes, shadowing, symlinked scripts), test-selection guard, default key dir always hidden.
- Recipe replay: monorepo sub-package installs cleaned up with their sources importable per worktree; changed-tests scoping when the declared command runs more than the claim covers; clearer recipe guidance.
