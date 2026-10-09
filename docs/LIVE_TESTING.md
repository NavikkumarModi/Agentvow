# Live-testing AgentMirror with VS Code + Copilot

Verified on a real run (macOS, VS Code agent chat using the Copilot CLI engine, 2026-10-07): the hook fires, Copilot's payload and session format are as described below, and AgentMirror reads the final answer. Where something is documentation-only it says so.

## How it fits together (what was observed)
- VS Code's agent chat can run on the **Copilot CLI engine** (session kind `copilotcli:` in the VS Code agent-host log). That engine **does run `agentStop` hooks** from `.github/hooks/*.json`. VS Code's own logs do **not** record this; the evidence is in the session file `~/.copilot/session-state/<id>/events.jsonl` (`hook.start` / `hook.end` records).
- The hook receives (camelCase): `sessionId`, `transcriptPath` (= that `events.jsonl`), `cwd`, `stopReason`, `stop_hook_active`, `timestamp`.
- The transcript is JSONL: `{type, data, id, timestamp, parentId}`. The agent's reply is an `assistant.message` event with the text in `data.content`; the final reply has `data.phase = "final_answer"`; intermediate messages are `commentary`/tool-call messages. AgentMirror uses the final answer only.
- **Copilot keeps only the hook output fields it knows** (`decision`, `reason`); an extra `systemMessage` is recorded as `{}`. So the verdict can **not** appear inside Copilot's chat text through this hook. It appears in the **VS Code extension** (status bar, report panel) or in `.agentmirror/last/report.html`.
- Optional: `agentmirror check --hook --feedback-to-agent` makes the hook answer `decision: block` + a short reason **once** when a claim is contradicted, so Copilot is asked to revise its summary. Off by default (AgentMirror otherwise never blocks). The reason is built only from the agent's own claim wording and fixed explanations, never from file or test names in the repository.

## Getting the verdict INSIDE the chat (three routes)
A hook cannot write into Copilot's own reply (Copilot keeps only `decision`/`reason` from a Stop hook). Routes that do reach the chat:
1. **`UserPromptSubmit` hook (`agentmirror prompt-hook`), automatic, one turn later. EXPERIMENTAL, off by default.** In the one live session where it first delivered a verdict, the Copilot chat then never received a model response (cause unproven: all AgentMirror hooks finished in under a second, no AgentMirror process was left running, and five earlier sessions without a delivery were fine). Only enable it deliberately (`examples/hooks/agentmirror-with-experimental-chat-hook.json`), and remove the `UserPromptSubmit` entry if a chat stalls. Copilot honours `additionalContext` from the prompt hook (observed in a real session file). On your next prompt it is told AgentMirror's sealed verdict for the previous answer, once, and asked to state it in one line at the start of its reply. This goes through the model, so Copilot may paraphrase or ignore it; the verdict itself is unchanged and the text it receives contains only fixed wording and the agent's own claim text, never file or test names from the repository. `agentmirror prompt-hook --min review` limits it to contradicted claims.
2. **`@agentmirror` in the chat.** Type `@agentmirror` to get the last sealed verdict as a chat message, with an "Open the full report" button. The text is AgentMirror's own, not model output, but it is a separate reply (not part of Copilot's), and chat participants may not be offered in every agent session type.
3. **`--feedback-to-agent` on the Stop hook.** When a claim is contradicted, Copilot is asked (once) to revise its final answer; the revision appears in the chat in the same turn.
The status bar, toast and report panel remain the model-free channels.

## Setup
```bash
cd /path/to/AgentMirror && pip install .
agentmirror doctor --repo /path/to/your/project      # or VS Code: "AgentMirror: Check the setup (doctor)"
```
`doctor` checks the install, runs the whole hook path with both payload styles, and reads Copilot's session files to tell you whether Copilot has run the hook in this repo.
1. VS Code: **AgentMirror: Add the agent hook to this workspace** (writes `.github/hooks/agentmirror.json` using the full path to `agentmirror`; apps launched from the Dock often lack conda/venv directories on PATH).
2. Start a **new** chat after adding the file (hooks are loaded when a session starts).
3. Give the agent a task where it makes checkable claims, for example: "Change the retry limit in X, then tell me whether all tests pass and whether anything else depends on it." A reply that only *reviews* a repository usually makes no checkable claim, and AgentMirror will say so ("no checkable claims found; N statements not examined").
4. Set `agentmirror.notify` to `always` while testing: every finished turn then shows a notification with the verdict (default `review` only notifies when a claim is contradicted). Also look at the VS Code status bar (bottom left; if you do not see one, View > Appearance > Status Bar). Set `agentmirror.autoOpen` to open the report automatically. The extension activates at startup and shows an existing result when the window opens.

## Timing note (observed live)
Copilot ran the `agentStop` hook 5 ms after writing the final answer, before the transcript file contained it. AgentMirror therefore waits up to 3 s (`AGENTMIRROR_WAIT`) for the final answer of the CURRENT turn (it never falls back to an earlier turn's answer); if it never appears the result says the message could not be read, which is not the same as "no claims".

## If the verdict doesn't show
- `agentmirror doctor` says whether Copilot ran the hook ("Copilot ran the agentStop hook in this repo: N time(s)") and whether the command path is safe.
- Probe whether any hook runs at all: `.github/hooks/probe.json` with `{"hooks": {"Stop": [{"type": "command", "command": "cat >> /tmp/am_probe.log", "timeout": 10}]}}`, new chat, then `cat /tmp/am_probe.log`.
- See what an unknown agent really sends, without sharing content: `AGENTMIRROR_DEBUG=1` in the hook command writes `.agentmirror/last/payload_shape.json` with key names, types and string lengths only.
- A hook result is displayed by the extension only if it carries a valid seal (`decision.sig`).

## Without hooks (always works)
Copy the agent's final message, then **AgentMirror: Check the message on the clipboard**, or select it and run **Check the selected text**.

## Not covered
Copilot cloud agent (use the GitHub Action: `examples/workflows/agentmirror.yml`), Codex/Cursor/Gemini hooks, Windows/Linux (the test sandbox is macOS-only).

## Live results (2026-10-09, run by the developer-side agent on the author's machine)
All of these are single runs, with claims the test steered the agent into; they show the mechanism works, not how often it fires.
- **Copilot in VS Code (Copilot CLI engine, model mai-code-1.1-flash), feedback mode:** the agent ended a turn with "There is no downstream impact."; the hook returned `decision: block` with the fixed reason; Copilot accepted it as a new instruction, searched and read the dependent modules, and rewrote its answer. The second stop (`stop_hook_active`) passed silently. Evidence: the session's `events.jsonl` (`agentStop` hook.end with the block output, then new tool calls).
- **Claude Code 2.1.x (`claude -p`, Stop hook, feedback mode):** same sequence; the revised answer began with a line saying an independent check flagged the previous answer (the disclosure instruction). Changed files listed: only the one the agent edited.
- **Background tests (Copilot, 374-test suite):** quick verdict first (tests: unknown), then ~4.5 minutes later the sealed result updated to "374 passed, matches the agent's count". Two toasts, status bar refreshed. Background results cannot feed back to the agent (it has already stopped); they only update the verdict.
- **Tests-pass contradiction (hook run directly with a Copilot-style payload, real sandboxed run):** a repo where the edit breaks both tests, claim "All 2 tests pass." -> CONTRADICTED (0 passed, 2 failed; 2 regressions), `decision: block`.
- **Claude declined to claim untested passes:** when told not to run tests it refused to say they pass; AgentMirror recorded the statement as unchecked and did not invent a verdict.
- **Not tested live:** Codex, Cursor, Gemini CLI; Copilot cloud agent; Linux/Windows (no test sandbox there: AgentMirror refuses to run tests).

## GitHub Action and CI (2026-10-09, GitHub-hosted runners, private repository)
- **CI (`.github/workflows/ci.yml`):** the full suite (199 tests incl. `tests/test_sandbox.py`) and the node tests pass on `ubuntu-latest` (bubblewrap sandbox) and `macos-latest` (sandbox-exec). Nothing skipped. `agentmirror doctor` reports the sandbox as working on both.
- **Action (`action.yml`, run as `uses: ./` on a real pull request):** the PR description was the claim ("no downstream impact. All 199 tests pass."). It posted one comment: no-downstream-impact CONTRADICTED (15 modules import the edited file), tests UNKNOWN. After the PR description was edited the same comment was updated in place (no duplicate).
- **Finding and fix:** the first runs executed while the test jobs were still running, so CI evidence was missing. The action now waits (`ci-wait`, default 600 s) for running test jobs; on the next run the tests claim became SUPPORTED by the CI result, with the caveat that CI does not check the agent's count and that a PR can edit CI configuration.
- Not run: fork pull requests (comment permission), Copilot cloud-agent PRs.
