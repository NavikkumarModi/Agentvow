# Agentvow

[![VS Code Marketplace](https://img.shields.io/visual-studio-marketplace/v/NavikkumarModi.agentvow)](https://marketplace.visualstudio.com/items?itemName=NavikkumarModi.agentvow) [![PyPI](https://img.shields.io/pypi/v/agentvow)](https://pypi.org/project/agentvow/) [![CI](https://github.com/NavikkumarModi/Agentvow/actions/workflows/ci.yml/badge.svg)](https://github.com/NavikkumarModi/Agentvow/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**Don't take an agent's word for it. Check the claim.**

When a coding agent says "all tests pass" or "nothing else depends on this", Agentvow checks that against the repository, independently of the agent, and tells you in plain language what it confirmed, what it contradicted, and what it could not check. No LLM decides the result, and nothing is approved, rejected or merged for you.

![An agent says it added retries to fetch() and that all tests pass. Agentvow records the packages of the agent's environment, replays the tests in a clean sandbox built from them, and reports the claim supported with the basis stated, while also saying that 6 of the 11 changed source lines were run by the tests and naming the lines that were not.](https://github.com/NavikkumarModi/Agentvow/blob/main/assets/demo.gif?raw=true)

*Recorded from [examples/demo_capture.py](https://github.com/NavikkumarModi/Agentvow/blob/main/examples/demo_capture.py) on the released package: a real virtualenv with pytest, a real commit, a real `agentvow capture`, a real sandboxed replay and a real changed-line coverage measurement. Staged for the recording, not faked: the pacing and simulated typing of the two commands, the "agent" scene (a pre-made commit stands in for a live agent), and the line wrapping of the report text so it fits the terminal. Note what the report does and does not say: the tests pass and the result reproduces from the captured packages, but nearly half of the changed lines were never run by any test, which is exactly what a person would want to know before trusting "all tests pass".*

*Video versions (MP4) of every recording on this page: [capture and replay](assets/demo.mp4), [the gate on three pull requests](assets/demo_gate.mp4), [what a reviewer reads](assets/demo_explain.mp4).*

## What you get
- **Independent replay.** Tests are re-run in a clean sandbox, built from the packages the agent's own environment actually had, and compared with a build from the project's own setup (CI files, Dockerfile, requirements).
- **Honest answers, three ways.** *Contradicted*, *supported (with the basis stated)*, or *UNKNOWN*. Missing evidence is never turned into "OK", and every UNKNOWN comes with the next step that would resolve it.
- **Changed-line coverage.** Says how many of the changed source lines the tests really ran, and names the ones they did not.
- **Claim checks beyond tests.** Backward compatibility (public-API diff) and downstream impact (import graph) for Python.
- **Portable evidence.** A minimal receipt and a capture bundle that can be verified on another machine, bound to the exact files by git tree hash.
- **Team gate.** A reusable GitHub workflow replays on the runner, builds a receipt and applies your policy from the base branch; a pull request that is contradicted cannot be merged when `agentvow/evidence` is a required check, and a person can acknowledge an UNKNOWN result by name (`/agentvow acknowledge <id>`). A self-hostable control plane service publishes that check; see below.
- **Plain-language decisions.** The check, the job summary and the CLI (`agentvow policy explain`) say what happened, what it means for the merge, what to do next, who can acknowledge and how, and what a pass does *not* show; the control plane also notifies the listed acknowledgers on the pull request and refreshes open pull requests when the policy file changes (both tested against fakes, not yet seen on GitHub).
- **Policy as a file.** `agentvow policy` turns a receipt into allow, needs acknowledgement or block under rules you write (contradictions always block; unauthenticated captures and unmeasured coverage can require a named acknowledger).
- **Evidence for a team.** `agentvow pilot-report` summarises a folder of receipts mechanically (decisions, reproducibility, coverage, what could not be recreated) and states what it does not show.
- **Where you work.** Claude Code hooks (`agentvow init`), GitHub Copilot in VS Code, the VS Code extension, the command line, GitHub Actions.
- **Safe by construction.** Sandboxed test runs (macOS `sandbox-exec`, Linux bubblewrap), network denied, sealed results, text from agents escaped in reports.

## How it works
1. The agent works and stops (or opens a pull request). Agentvow's hook records the packages of the agent's environment right after its tests.
2. Agentvow reads the agent's message and extracts the checkable claims by rules (no model).
3. It replays and measures: tests at base and head in a clean sandbox, from the captured packages and from the project's own setup, plus changed-line coverage.
4. It writes a **receipt** (verdicts, counts and category names; no source) and applies your **policy** from the base branch: *allow*, *needs acknowledgement* or *block*. A contradiction always blocks.
5. In a pull request, the **check** says all this in plain words; a named person acknowledges an unconfirmed result with one comment, and the acknowledgement is recorded.

```text
agent -> capture -> check -> receipt -> policy -> explain -> pull request check -> acknowledgement
```

## Demos (all real output; staged only as stated)
Each recording is a real run of the commands shown; what is staged is said under it. **The same flow, four views:**

**1. An agent's claim is replayed from its own packages** (the recording at the top of this page).

**2. An agent's claim, checked, and what it becomes.** The agent says it added `g` and that 9 tests pass; Agentvow runs the tests and finds 1. It reports UNKNOWN and says why, not "OK"; a receipt keeps only verdicts, counts and category names; a policy turns it into a decision (output of 0.4.2, trimmed):
```text
$ agentvow check --repo . --base HEAD~1 --transcript msg.txt --run-tests --test-cmd "{py} -m unittest discover -s tests -t ."
STATUS: INSUFFICIENT EVIDENCE
? The agent said: "All 9 tests pass."
   UNKNOWN: The agent reported 9 passing tests but Agentvow ran 1 test suite(s) on this exact state
   (tests: 1 passed, 0 failed); total 1 passed, 0 failed, 0 skipped. The numbers differ, which may mean
   the agent ran a different set or configuration.
$ agentvow receipt --decision d.json --repo-slug you/project --repo . -o receipt.json
$ agentvow policy evaluate --receipt receipt.json
needs_acknowledgement
```

**3. The gate on three agent pull requests.** The steps of the gate workflow run on three pull-request branches: the claim is true (allow), the claim is false because the change breaks a test (block), and the claim cannot be confirmed because the agent said 9 tests passed and one exists (needs acknowledgement).

![Three screens, one per agent pull request. The first, "I added g(). All tests pass.", ends in allow, with the grey note that the required check passes. The second, "I simplified f(). All tests pass.", ends in block because the claim is contradicted and cannot be acknowledged away. The third, "I added h(). All 9 tests pass.", ends in needs_acknowledgement.](https://github.com/NavikkumarModi/Agentvow/blob/main/assets/demo_gate.gif?raw=true)

*Recorded from [examples/demo_gate.py](https://github.com/NavikkumarModi/Agentvow/blob/main/examples/demo_gate.py) on the released 0.4.2 package, real commands on a throwaway project with a real virtualenv and pytest; the decisions are not scripted. Staged: the pacing and simulated typing, the pre-made branches that stand in for agents (their pull-request descriptions are the claims), the working files kept outside the repository, the commands shortened on screen (the real ones also pass `--python .venv/bin/python` and longer paths), and the grey "on GitHub" notes (what the required check then does: shown for real in view 5 and in `docs/LIVE_TESTING.md`). [MP4](assets/demo_gate.mp4)*

**4. What a reviewer reads.** The next step: `agentvow policy explain` turns the decision into the plain-language text that the check run and the job summary show (available from Agentvow 0.4.4; the gate workflows default to 0.4.4).

![Two screens. In the first, a pull request whose claim was contradicted: "Agentvow will not let this through", what was found in plain words, "This cannot be acknowledged away". In the second, a pull request whose claim could not be confirmed: "Agentvow could not fully confirm this change. A person named in the repository's policy must look at it and acknowledge it before it can merge", what to do, who is listed as acknowledger, and that a contradiction can never be acknowledged.](https://github.com/NavikkumarModi/Agentvow/blob/main/assets/demo_explain.gif?raw=true)

*Recorded from [examples/demo_explain.py](https://github.com/NavikkumarModi/Agentvow/blob/main/examples/demo_explain.py) with the 0.4.4 candidate built from this repository (0.4.4 has since been published to PyPI), on the same throwaway project as view 3; the decisions are not scripted. Staged as in view 3, plus: a policy that lists one acknowledger (alice), and the closing paragraph ("what this does not show", which every explanation ends with) left out of the picture. [MP4](assets/demo_explain.mp4)*

**5. On a real pull request.** The gate workflow and the control plane service, run against GitHub in a throwaway repository (`docs/LIVE_TESTING.md`): a pull request whose tests are broken but whose description says "All tests pass." gets a failing, **required** `agentvow/evidence` check from the Agentvow App, and the merge button is disabled. A pull request that merely could not be confirmed waits for a named person to acknowledge it, and the acknowledgement flow worked end to end. (That run predates the plain-language text, the notification and the policy refresh; those have not yet run on GitHub.)

![A pull request with the required check agentvow/evidence failing with "Agentvow: block"; the Merge pull request button is greyed out.](https://raw.githubusercontent.com/NavikkumarModi/Agentvow/main/docs/images/gate-blocked-pr.png)

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
# portable evidence and a team decision (docs/GATE_WORKFLOW.md):
agentvow capture --repo . --export bundle.json && agentvow check --repo . --transcript msg.txt --from-capture bundle.json   # anyone with the same files can replay it; refused if the files differ
agentvow check --repo . --transcript msg.txt --json > d.json && agentvow receipt --decision d.json --repo-slug you/project --repo . -o receipt.json
agentvow policy init > policy.json && agentvow policy evaluate --receipt receipt.json --policy policy.json > result.json   # allow / needs_acknowledgement / block
agentvow policy explain --result result.json                                              # the same decision in plain words (0.4.4+): what happened, what to do, who can acknowledge
agentvow pilot-report --receipts ./receipts -o report.md                                  # a mechanical evidence report over many receipts
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
| "added / changed / removed `f.py`", "did not touch `f.py`" | git's own change list (committed, uncommitted and new files); a disagreement is shown as a mismatch for a person to check (not as a block: about two thirds to nine tenths of such mismatches were real on real descriptions); a bare file name that several files share, or a path git ignores, is UNKNOWN; it says which files changed, not what changed in them |
| "updated the README / the docs / the changelog" | a documentation file (README, CHANGELOG, `docs/`, `.md`/`.rst`) is among the changed files; "documentation" with only Python changed is UNKNOWN (docstrings are not read) |
| "`ruff check` passes" (also `ruff format`, `black`, `flake8`) | the named linter is run in the sandbox on the changed Python files (it must already be installed; its version is reported; any other tool is UNKNOWN); "lint passes" with no tool is resolved from the repository's own ruff / black / flake8 / pre-commit configuration, and is UNKNOWN when none is configured or the change touches another language |

Anything else the agent says is listed as **unchecked**, and the report says how many statements were not examined. **UNKNOWN is a real result**: missing evidence, a failed collector, an unreadable message or an unfamiliar format never become "OK". The best possible status is `NO CONTRADICTION FOUND (scoped, not a safety verdict)`.

## Where it plugs in (and how well each is verified)
| Where | How | Status |
|---|---|---|
| **GitHub Copilot in VS Code** (agent chat, Copilot CLI engine) | `.github/hooks/agentvow.json` (extension command *Agentvow: Add the agent hook*) | **Verified on a real run:** Copilot ran the hook, its payload and session file (`events.jsonl`) are parsed, the result is sealed and detected by the extension. Hooks are a Preview feature |
| **Claude Code** | `agentvow init` writes the two hooks below after a preview and a confirmation; by hand: Stop hook `agentvow check --hook` (settings: `{"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "agentvow check --hook --evidence-pack"}]}]}}` in `.claude/settings.json`) | **Verified on real runs** (Claude Code 2.1.263, `claude -p`): payload and transcript parsed, result sealed, never blocks; the `--evidence-pack` background run (capture, both replay contexts, changed-line coverage) verified on one toy project |
| Copilot CLI (terminal), Copilot cloud agent | same hook file | From documentation only |
| Codex, Cursor, Gemini CLI | their stop hooks → `agentvow check --hook` | Not tested; `AGENTVOW_DEBUG=1` records only the *structure* of what an agent sends so an adapter can be built |
| Any agent's pull request | GitHub Action `action.yml`: PR description as the claim, CI results, comment + report; opt-in `run-tests: true` also replays the tests in the sandbox on the runner and adds the evidence pack | Run on a real pull request of this repository (docs/LIVE_TESTING.md); `run-tests` run once on GitHub on a pull request of this repository (docs/LIVE_TESTING.md) |
| Any pull request, as a team gate | two reusable workflows: `gate.yml` (replay on the runner, receipt, local decision; needs no credential) and `gate-service.yml` (the same replay plus an upload to the control plane service; pinned to a commit sha); see `docs/GATE_WORKFLOW.md` and `docs/SETUP_GITHUB_APP.md` | **Run on real pull requests** before the split into two files (local-policy mode, 2026-10-22; with the control plane service and a required check pinned to its App, 2026-10-23: contradicted and unconfirmed pull requests blocked, acknowledgement by comment worked); the two-file version also ran on GitHub on 2026-10-26; fork pull requests: the service path does not support them, an experimental opt-in path exists (`docs/FORK_PRS.md`, never run on GitHub) (`docs/LIVE_TESTING.md`) |
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
From the [Marketplace](https://marketplace.visualstudio.com/items?itemName=NavikkumarModi.agentvow): search for **Agentvow**, or run `code --install-extension NavikkumarModi.agentvow`. (From a checkout: `code --install-extension dist/agentvow-0.4.5.vsix --force`.) You also need the command-line tool (`pip install agentvow`).
Then **Developer: Reload Window**, and click **Agentvow** in the status bar to try the demo. The extension is plain JavaScript with no dependencies; it calls the `agentvow` command, which must be reachable by path (use the full path in `agentvow.command` if VS Code does not see your shell's PATH).

## Team gate and control plane
The gate workflows (`docs/GATE_WORKFLOW.md`) replay on the runner, build a receipt, and apply your policy (the local decision reads the pull request's base branch; the service reads the default branch). The GitHub Action, the local gate and the service-backed gate are **different levels of enforcement**: only the last can make a check required and keep a named acknowledgement record. What each artifact proves, and does not: `docs/TRUST_MODEL.md`. A self-hostable control plane service (`controlplane/service/`, in development, first live run on GitHub passed on 2026-10-23; `docs/CONTROLPLANE_PHASE1.md`; to try it with your own GitHub App: `docs/SETUP_GITHUB_APP.md`) publishes the `agentvow/evidence` check, records named acknowledgements and offers a per-repository audit export. It stores receipts only and never runs your code.

## Evidence, scope and limits
Agentvow 0.4.5 is a prototype for Python repositories; running tests needs macOS or Linux. A pass is evidence to weigh, not a safety verdict. Studies, measured numbers, known limits and the security model are in [docs/EVIDENCE_AND_LIMITS.md](docs/EVIDENCE_AND_LIMITS.md) and `docs/SECURITY_MODEL.md`.

## Develop and validate
```bash
scripts/validate_all.sh        # tests, consistency, secret scan, wheel + clean-room install, extension package, leaks (builds dist/)
python3 -m unittest discover -s tests && node --test vscode/test/extension.test.js vscode/test/helpers.test.js
```
Design and research: `docs/research/` (start with `NOVELTY_BOUNDARY.md`, `RISKS.md`, `PILOT_P0.md`), product notes `docs/product/`, rules for contributors `CLAUDE.md`. License: MIT (`LICENSE`).

<!-- test counts, checked by scripts/validate_all.sh: 711 Python tests, 32 node tests -->