# Quickstart for pilot participants

You need Python 3.10+, git, and a Python project with pytest tests, on macOS or Linux. Everything stays on your machine.

**1. Install the release**
```bash
python3 -m venv ~/.agentvow-pilot && ~/.agentvow-pilot/bin/pip install "agentvow==0.2.1"
~/.agentvow-pilot/bin/agentvow --version   # agentvow 0.2.1
```
**2. Check your setup**
```bash
cd your-project && ~/.agentvow-pilot/bin/agentvow doctor --repo .
```
**3. Try it once by hand (nothing is changed in your project except a `.agentvow/` folder; add it to `.gitignore`)**
```bash
echo "I changed the code. All tests pass." | ~/.agentvow-pilot/bin/agentvow check --repo . --transcript - --run-tests --changed-coverage --python .venv/bin/python
```
Use the Python of your project's environment for `--python` (the one where pytest is installed). For the changed-line coverage part, that environment also needs `coverage` (`.venv/bin/pip install coverage`); without it the report says coverage is unavailable. (With `--setup auto` instead of `--python`, Agentvow builds its own environment and installs `coverage` itself.)
**4. Turn on the hooks (opt-in).** For Claude Code, add to `.claude/settings.json` in your project (this shape was verified on a real Claude Code 2.1.263 run; check with `agentvow doctor` afterwards). Use the absolute path to your pilot environment's `agentvow`, for example `/Users/you/.agentvow-pilot/bin/agentvow`:
```json
{"hooks": {
  "PostToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "/Users/you/.agentvow-pilot/bin/agentvow post-test-hook", "timeout": 30}]}],
  "Stop": [{"hooks": [{"type": "command", "command": "/Users/you/.agentvow-pilot/bin/agentvow check --hook --evidence-pack", "timeout": 60}]}]}}
```
The first hook records your agent's environment right after it runs a test command; the second checks the turn when the agent stops. Your project needs a `.venv`, `venv` or `env` folder (or an active virtual environment) with the packages your tests use, so there is something to capture. For GitHub Copilot in VS Code use the extension's command "Agentvow: Add the agent hook" (Stop hook only; add `--evidence-pack` to its command, no test-time capture). To switch it off, delete the hook entries. Add `.agentvow/` and `.claude/settings.json` to your `.gitignore` if you do not want to commit them.
**5. Work as usual.** After each agent turn Agentvow answers at once with what it can see and, about a minute later, replaces the result with an **Evidence pack**: the tests replayed in a clean sandbox from the packages your agent had installed and, separately, from your project's own setup; which changed lines no test ran; whether files were edited after the agent's last test run; and a list of things the replay does not recreate (environment variables, external programs, network, ignored files). Open it from `.agentvow/last/report.html` or the editor extension.
**What the words mean:** SUPPORTED = independently checked and holds under the stated basis; CONTRADICTED = an independent run or CI disagrees with the claim; UNKNOWN = not enough evidence (this is an honest answer, not an error); "changed-line coverage" = how many of the changed lines the tests actually ran; basis "captured environment" = reproduced from the Python packages your agent had installed, not proof that a fresh clone works; "Not reproduced by this replay" = things the tests reference that a replay cannot recreate, listed by name only, not a finding.
**Problems:** the hook never blocks your agent. If something looks wrong or slow, remove the hook entry, then tell us what happened (no code needed). Stop any time.
