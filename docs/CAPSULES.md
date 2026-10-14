# Environment capsules (capture at claim time)

An agent's "the tests pass" is true in the environment it worked in. A **capsule** records the Python packages of that environment at the moment the agent stops, so a later check can replay the tests in a clean sandbox built from exactly those packages and say whether the result reproduces.

```bash
agentvow capture --repo .                              # right after the agent ran its tests: writes .agentvow/capsules/<commit>_<tree>.json
agentvow check --repo . --transcript msg.txt --run-tests --from-capsule
agentvow check --hook --background-tests --capture ... # in the Stop hook: capture when the agent stops, then run the background tests from the capsule
```

**Capture at the test run, not only at the stop.** If the agent edits files after its last test run, a capsule taken only when it stops cannot tell. In Claude Code, add a PostToolUse hook on the `Bash` tool next to the Stop hook:
```json
{"hooks": {
  "PostToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "agentvow post-test-hook", "timeout": 30}]}],
  "Stop": [{"hooks": [{"type": "command", "command": "agentvow check --hook --evidence-pack"}]}]}}
```
`post-test-hook` reads the tool call, and only when the command looks like a test run (`pytest`, `python -m pytest|unittest`, `tox`, `nox`, `manage.py test`, `make test`; each `&&`/`;`/`|` segment is checked at its start, so `pip install pytest` is not one) it captures the environment right then and records the command and the files that differed from HEAD. It is silent, fast, never blocks, and swallows any error (the Stop hook still captures). At the stop the Evidence pack then says one of: the last test run was on the final state (nothing edited after it); the last test run was on an earlier state and these files were edited after it (and which packages were added or removed since); or no test-time capture exists, so edits after the last test run cannot be ruled out. The replay itself is always of the final state; this only tells you how much of it the agent had actually tested. Verified on a real Claude Code 2.1.263 run (the agent ran pytest, then edited `lib.py`; the pack named `lib.py`). Other agents: only Claude Code's hook shape has been verified.

**What is captured:** the `pip freeze` of the agent's interpreter (found in `.venv`, `venv`, `env`, or the active `VIRTUAL_ENV`; or pass `--python`), reduced to plain `name==version` pins (editable installs, direct URLs, the project's own distribution and `pip` are dropped), and the Python version. **Never captured:** environment variable values, secrets, system packages, services, generated files. The interpreter is run inside the platform sandbox to read the list.
**Bound to the exact state:** the capsule is signed and tied to the commit and working-tree hash. If the code changes after the capture, `--from-capsule` finds no capsule and **fails closed** (UNKNOWN, with the reason); it never falls back to another environment.
**What a result means:** SUPPORTED/NOT_CONTRADICTED with basis `captured_environment` says the result is reproducible from the captured packages in a clean environment. It does not show the repository declares those packages (a fresh clone may still fail), does not cover anything outside Python packages, and reproducibility is not correctness. The report states the captured and replay Python versions.
**Evidence:** in the pre-registered Stage B6 study (40 random agent-PR tasks, 22 valid runs), replaying from captured packages reproduced 20 of 22 valid passing results (91%) against 12 of 22 (55%) for reconstructing the environment from the repository; see `docs/research/forecast_grounding/STAGE_B6_RESULTS.md`. One model, Python packages only.
**Limits you may hit:** a replay environment larger than 700 MB stops (raise it with `AGENTVOW_MAX_ENV_MB`); projects whose importable package is not at the repository root can fail because the project's own distribution is dropped from the list; tests that need a credential skip or fail by design.
