# Agentvow

[![VS Code Marketplace](https://img.shields.io/visual-studio-marketplace/v/NavikkumarModi.agentvow)](https://marketplace.visualstudio.com/items?itemName=NavikkumarModi.agentvow) [![PyPI](https://img.shields.io/pypi/v/agentvow)](https://pypi.org/project/agentvow/) [![CI](https://github.com/NavikkumarModi/Agentvow/actions/workflows/ci.yml/badge.svg)](https://github.com/NavikkumarModi/Agentvow/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**Don't take an agent's word for it. Check the claim.**

When a coding agent says "all tests pass" or "nothing else depends on this", Agentvow checks that against the repository, independently of the agent, and tells you in plain language what it confirmed, what it contradicted, and what it could not check. No LLM decides the result, and nothing is approved, rejected or merged for you.

![An agent says it added retries to fetch() and that all tests pass. Agentvow records the packages of the agent's environment, replays the tests in a clean sandbox built from them, and reports the claim supported with the basis stated, while also saying that 6 of the 11 changed source lines were run by the tests and naming the lines that were not.](https://github.com/NavikkumarModi/Agentvow/blob/main/assets/demo.gif?raw=true)

*Recorded from [examples/demo_capture.py](https://github.com/NavikkumarModi/Agentvow/blob/main/examples/demo_capture.py) on the released package: a real virtualenv with pytest, a real commit, a real `agentvow capture`, a real sandboxed replay and a real changed-line coverage measurement. Staged for the recording, not faked: the pacing and simulated typing of the two commands, the "agent" scene (a pre-made commit stands in for a live agent), and the line wrapping of the report text so it fits the terminal. Note what the report does and does not say: the tests pass and the result reproduces from the captured packages, but nearly half of the changed lines were never run by any test, which is exactly what a person would want to know before trusting "all tests pass".*

## What you get
- **Independent replay.** Tests are re-run in a clean sandbox, built from the packages the agent's own environment actually had, and compared with a build from the project's own setup (CI files, Dockerfile, requirements).
- **Honest answers, three ways.** *Contradicted*, *supported (with the basis stated)*, or *UNKNOWN*. Missing evidence is never turned into "OK", and every UNKNOWN comes with the next step that would resolve it.
- **Changed-line coverage.** Says how many of the changed source lines the tests really ran, and names the ones they did not.
- **Claim checks beyond tests.** Backward compatibility (public-API diff) and downstream impact (import graph) for Python.
- **Portable evidence.** A minimal receipt and a capture bundle that can be verified on another machine, bound to the exact files by git tree hash.
- **Team gate.** A reusable GitHub workflow and Action publish an `agentvow/evidence` check on pull requests; policy lives on the base branch and acknowledgements are recorded by name.
- **Where you work.** Claude Code hooks (`agentvow init`), GitHub Copilot in VS Code, the VS Code extension, the command line, GitHub Actions.
- **Safe by construction.** Sandboxed test runs (macOS `sandbox-exec`, Linux bubblewrap), network denied, sealed results, text from agents escaped in reports.

## How it works
1. The agent works and stops (or opens a pull request).
2. Agentvow reads its message and extracts the checkable claims by rules.
3. It replays and measures: tests at base and head, captured-environment replay, project-native replay, changed-line coverage.
4. You get a plain-language verdict with evidence, scope and what was not examined.

## Quick start
```bash
pip install agentvow                    # from PyPI; or from a checkout: pip install .  (no dependencies; Python 3.10+)
agentvow doctor --repo /path/to/project       # checks your setup and runs the whole hook path end to end
agentvow init --repo /path/to/project         # Claude Code: add the two hooks (preview, confirmation, backup; --dry-run, --remove; see docs/CAPSULES.md)
echo "I changed X. All 12 tests pass. Nothing else depends on it." | agentvow check --repo /path/to/project
agentvow check --repo . --transcript msg.txt --run-tests --python venv/bin/python   # also run the tests (sandboxed, macOS/Linux)
agentvow check --repo . --transcript msg.txt --run-tests --changed-coverage           # also say how many changed source lines the tests actually ran
agentvow check --repo . --transcript msg.txt --evidence-pack --html report.html   # receipt + reproducibility (captured vs project setup) + changed-line coverage (docs/EVIDENCE_PACK.md)
agentvow capture --repo . && agentvow check --repo . --transcript msg.txt --run-tests --from-capsule   # replay from the packages captured when the agent ran its tests (docs/CAPSULES.md)
agentvow check --repo . --transcript msg.txt --ci --html report.html                # also read CI results; write a visual report
```
`--recipe recipe.json` replays the agent's *own declared* setup and test command in a clean sandbox (see `docs/RECIPES.md`).
`agentvow audit-env --session <session.jsonl> [--recipe recipe.json]` lists what an agent session installed or exported and whether the repository or recipe declares it.
Exit codes: `0` no contradiction found (scoped), `1` review required, `2` insufficient evidence, `3` tool error. Other options: `--markdown`, `--json`, `--session <Claude Code session.jsonl>`, `--base <ref>`, `--test-cmd`, `--test-timeout`, `--setup auto`, `--new-test-failures review`.

![What the verdict view shows](https://raw.githubusercontent.com/NavikkumarModi/Agentvow/main/docs/images/report.png)

## See it in 10 seconds
```bash
agentvow demo          # builds a small demo repo, checks "no downstream impact" against it and writes a sealed result
```
In VS Code run **Agentvow: Try the demo**: it shows the red verdict panel and copies a prompt you can paste into Copilot (in the demo folder, with the hook added) to see the same on a real agent turn.

## What it checks
| Claim in the agent's message | How it is checked |
|---|---|
| "tests pass" (with an optional count) | tests run at the base and head states in a sandbox; a regression is a test that passed before and fails now; the claimed count is compared; failures that also occur at base are treated as environmental; deleted/skipped tests and modified existing tests prevent a plain "supported"; CI test jobs for the commit are read with `--ci` |
| "backward compatible" | static public-API diff of changed Python files (removed or renamed names and parameters, new required parameters, `__init__` re-exports) |
| "no downstream impact" | static import graph (src layout aware); deleted modules, dynamic imports and non-Python code make the result UNKNOWN |

Anything else the agent says is listed as **unchecked**, and the report says how many statements were not examined. **UNKNOWN is a real result**: missing evidence, a failed collector, an unreadable message or an unfamiliar format never become "OK". The best possible status is `NO CONTRADICTION FOUND (scoped, not a safety verdict)`.

## Where it plugs in (and how well each is verified)
| Where | How | Status |
|---|---|---|
| **GitHub Copilot in VS Code** (agent chat, Copilot CLI engine) | `.github/hooks/agentvow.json` (extension command *Agentvow: Add the agent hook*) | **Verified on a real run:** Copilot ran the hook, its payload and session file (`events.jsonl`) are parsed, the result is sealed and detected by the extension. Hooks are a Preview feature |
| **Claude Code** | `agentvow init` writes the two hooks below after a preview and a confirmation; by hand: Stop hook `agentvow check --hook` (settings: `{"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "agentvow check --hook --evidence-pack"}]}]}}` in `.claude/settings.json`) | **Verified on real runs** (Claude Code 2.1.263, `claude -p`): payload and transcript parsed, result sealed, never blocks; the `--evidence-pack` background run (capture, both replay contexts, changed-line coverage) verified on one toy project |
| Copilot CLI (terminal), Copilot cloud agent | same hook file | From documentation only |
| Codex, Cursor, Gemini CLI | their stop hooks → `agentvow check --hook` | Not tested; `AGENTVOW_DEBUG=1` records only the *structure* of what an agent sends so an adapter can be built |
| Any agent's pull request | GitHub Action `action.yml`: PR description as the claim, CI results, comment + report; opt-in `run-tests: true` also replays the tests in the sandbox on the runner and adds the evidence pack | Run on a real pull request of this repository (docs/LIVE_TESTING.md); `run-tests` run once on GitHub on a pull request of this repository (docs/LIVE_TESTING.md) |
| Anything else | paste or pipe the message; VS Code commands for clipboard/selection | Tested |

## Seeing the verdict
Copilot keeps only `decision`/`reason` from a hook's output, so **a hook cannot add text to Copilot's own reply.** The verdict is shown in:
- the VS Code **status bar**, a **notification** (`agentvow.notify`: `review` default, `always`, `never`) and the **report panel**; the extension logs to the *Agentvow* output channel;
- `@agentvow` in the chat: prints the last sealed verdict as its own message (not part of Copilot's reply);
- `agentvow agent-instructions --write .github/copilot-instructions.md`: tells the chat agent to run the check itself and show its output (works through the model; the agent chooses the draft it checks, so the independent hook remains the check that does not depend on the agent);
- `agentvow check --hook --feedback-to-agent` (opt-in): asks the agent, once, to revise an answer with a contradicted claim (the only mode in which the hook can block);
- `agentvow post-test-hook` (opt-in, Claude Code `PostToolUse` on `Bash`): captures the environment right after the agent runs its tests, so the pack can say whether files were edited after the last test run (docs/CAPSULES.md).
- `agentvow check --hook --evidence-pack` (opt-in): after the agent stops, a background run captures its environment, replays the tests in the captured environment and in the project's own setup, measures changed-line coverage and updates the result with an Evidence pack (docs/EVIDENCE_PACK.md).
- `agentvow check --hook --background-tests` (opt-in): the hook answers at once with what it can see, then runs your tests in the background (sandboxed, macOS/Linux) and updates the verdict when they finish, so slow suites do not hit the agent's hook timeout. Changes are counted since the previous check in the repository (not since your last commit), so earlier uncommitted work is not blamed on the agent.
- **experimental, off by default:** a `UserPromptSubmit` hook (`agentvow prompt-hook`) that tells the agent the last verdict on your next prompt. In one live session the first delivery coincided with a Copilot chat that stalled (cause unproven).
Details and a step-by-step live test: `docs/LIVE_TESTING.md`.

## Install the VS Code extension
From the [Marketplace](https://marketplace.visualstudio.com/items?itemName=NavikkumarModi.agentvow): search for **Agentvow**, or run `code --install-extension NavikkumarModi.agentvow`. (From a checkout: `code --install-extension dist/agentvow-0.4.0.vsix --force`.) You also need the command-line tool (`pip install agentvow`).
Then **Developer: Reload Window**, and click **Agentvow** in the status bar to try the demo. The extension is plain JavaScript with no dependencies; it calls the `agentvow` command, which must be reachable by path (use the full path in `agentvow.command` if VS Code does not see your shell's PATH).

## Team gate and control plane
The gate workflow (`docs/GATE_WORKFLOW.md`) replays on the runner, builds a receipt, and applies your policy from the base branch. A self-hostable control plane service (`controlplane/service/`, in development; `docs/CONTROLPLANE_PHASE1.md`) publishes the `agentvow/evidence` check, records named acknowledgements and offers a per-repository audit export. It stores receipts only and never runs your code.

## Evidence, scope and limits
Agentvow 0.4.0 is a prototype for Python repositories; running tests needs macOS or Linux. A pass is evidence to weigh, not a safety verdict. Studies, measured numbers, known limits and the security model are in [docs/EVIDENCE_AND_LIMITS.md](docs/EVIDENCE_AND_LIMITS.md) and `docs/SECURITY_MODEL.md`.

## Develop and validate
```bash
scripts/validate_all.sh        # tests, consistency, secret scan, wheel + clean-room install, extension package, leaks (builds dist/)
python3 -m unittest discover -s tests && node --test vscode/test/extension.test.js vscode/test/helpers.test.js
```
Design and research: `docs/research/` (start with `NOVELTY_BOUNDARY.md`, `RISKS.md`, `PILOT_P0.md`), product notes `docs/product/`, rules for contributors `CLAUDE.md`. License: MIT (`LICENSE`).

<!-- test counts, checked by scripts/validate_all.sh: 491 Python tests, 32 node tests -->