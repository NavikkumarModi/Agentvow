# Changelog

## 0.1.0 (release candidate, 2026-10-08)
First feature-complete prototype. Not a safety verdict; see `docs/SECURITY_MODEL.md` and the limits in README.
- Claim checking (tests pass with counts, backward compatible, no downstream impact) against the repository, sandboxed test runs (macOS), CI reading, differential regression rule, fail-closed statuses and exit codes.
- Visual HTML report, markdown summary, JSON; hook for Claude Code and GitHub Copilot (Stop/agentStop) with sealed results; VS Code extension (status bar, notifications, `@agentmirror`); GitHub Action; `doctor`; `agent-instructions`.
- Security hardening after three adversarial reviews (sandboxed installs/tests, signed evidence and seals, symlink-safe writes, hardened git).
- Studies and honest limits in `docs/research/`.
