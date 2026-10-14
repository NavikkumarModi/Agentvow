# Agentvow 0.2.1

Agentvow checks what a coding agent says it did against what it can independently observe. It informs you; it never approves, rejects or merges, and no language model decides a verdict. Still a prototype, not a safety verdict.

## New
- **Evidence pack** (`check --run-tests --evidence-pack`, or the Stop hook `agentvow check --hook --evidence-pack`): one report section with three separate dimensions and a record, never a score. (1) An execution receipt: what ran, on which exact state. (2) Reproducibility: the tests replayed from the environment captured when the agent ran them AND from the project's own setup, with the observed cause named when they disagree. (3) Changed-line coverage: how many changed executable lines the tests ran, naming the ones no test reached. (4) A names-only record of what the replay does not recreate (environment variables, external programs, network, service files, git-ignored files, Python or OS differences). Docs: `docs/EVIDENCE_PACK.md`.
- **Capture at test time** (`agentvow post-test-hook`, a Claude Code `PostToolUse` hook on `Bash`): captures the agent's environment right after it runs a test command; the pack then says whether files were edited after the last test run. Docs: `docs/CAPSULES.md`.
- Hook integration: `--hook --evidence-pack` captures at the stop and adds the pack in the background; a missing capture or an unavailable coverage module is stated in the report, never hidden.

## Known limits
Python repositories only; capture covers Python packages, not system packages, services, generated files or secrets; running tests needs macOS or Linux; the hook shapes are verified for Claude Code 2.1.263 and (earlier) Copilot in VS Code only; the studies behind these features are small and Claude-only (`docs/research/`). A reproduced result is not a correct change.
