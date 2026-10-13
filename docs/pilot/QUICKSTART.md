# Quickstart for pilot participants

You need Python 3.10+, git, and a Python project with pytest tests, on macOS or Linux. Everything stays on your machine.

**1. Install the pinned build**
```bash
python3 -m venv ~/.agentvow-pilot && ~/.agentvow-pilot/bin/pip install "git+https://github.com/NavikkumarModi/Agentvow@c21160bc06b8600456bd0c2231a50acaec1652ec"
~/.agentvow-pilot/bin/agentvow --version
```
**2. Check your setup**
```bash
cd your-project && ~/.agentvow-pilot/bin/agentvow doctor --repo .
```
**3. Try it once by hand (nothing is changed in your project except a `.agentvow/` folder; add it to `.gitignore`)**
```bash
echo "I changed the code. All tests pass." | ~/.agentvow-pilot/bin/agentvow check --repo . --transcript - --run-tests --changed-coverage --python .venv/bin/python
```
Use the Python of your project's environment for `--python` (the one where pytest is installed).
**4. Turn on the hook (opt-in) for your agent.** For Claude Code, add to `.claude/settings.json` in your project (check with `agentvow doctor` afterwards):
```json
{"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "~/.agentvow-pilot/bin/agentvow check --hook --background-tests --capture"}]}]}}
```
For GitHub Copilot in VS Code use the extension's command "Agentvow: Add the agent hook" or follow the README. To switch it off, delete the hook entry.
**5. Work as usual.** After each agent turn Agentvow answers at once with what it can see and, a little later, updates the verdict from a sandboxed test run built from the packages your agent had installed. Open the report from `.agentvow/last/report.html` or the editor extension.
**What the words mean:** SUPPORTED = independently checked and holds under the stated basis; CONTRADICTED = an independent run or CI disagrees with the claim; UNKNOWN = not enough evidence (this is an honest answer, not an error); "changed-line coverage" = how many of the changed lines the tests actually ran; basis "captured environment" = reproduced from the Python packages your agent had installed, not proof that a fresh clone works.
**Problems:** the hook never blocks your agent. If something looks wrong or slow, remove the hook entry, then tell us what happened (no code needed). Stop any time.
