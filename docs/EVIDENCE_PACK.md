# Evidence pack

`agentvow check --run-tests --evidence-pack` (it turns on the test run and changed-line coverage for you) adds one section to the report with **three separate dimensions of evidence**. They are never combined into a score or a badge, and the pack changes no verdict.

1. **Execution receipt.** What ran (the test command), on which exact state (commit, plus uncommitted changes if any), compared with which base, and that the receipt is valid only for that state: any later edit makes it stale.
2. **Reproducibility.** The same tests are run in up to two clean sandboxes: one built from the packages **captured when the agent ran its tests** (needs `agentvow capture`, see `docs/CAPSULES.md`) and one built **from the project's own declarations** (the zero-config setup). The pack states whether the result reproduces in both, in one only, or in neither, and when the two disagree it says what was observed, for example "reproduces from the captured packages but NOT from the project's own setup (missing dependency: six): someone who clones the repository may not be able to reproduce it". Without a capsule only the project-native context runs and the pack says the captured replay is missing.
3. **Changed-line coverage.** How many changed executable source lines the tests ran, with the lines and files that no test reached (and the first line's text), and files the tests never loaded. "Ran" is not "was checked": line coverage can show a line was not executed; it cannot show a line was asserted.

**In the agent hook:** `agentvow check --hook --evidence-pack` (the flag implies the background test run and the environment capture). The hook answers at once with what it can see, then a detached run captures the agent's packages, replays in both contexts, measures changed-line coverage and replaces the result with one that includes the pack. Without a project environment to capture, the pack shows only the project-native context and says the captured replay is missing. The hook never blocks the agent.

```bash
agentvow capture --repo .                                   # right after the agent's tests
agentvow check --repo . --transcript msg.txt --evidence-pack --html report.html
```

**What it does not do:** it does not run a second claim check (the verdict comes from the primary replay as before), does not cover system packages, services, generated files or secrets, and a pass in both contexts is not a correct change. It informs a person; it never approves, rejects or merges. A failure while building the pack is reported in the scope line and never hides or changes the verdict.
**Cost:** two environment builds and two test runs instead of one.
