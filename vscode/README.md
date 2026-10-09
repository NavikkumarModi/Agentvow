# Agentvow for VS Code

Shows, after any coding agent finishes, whether what it *said* matches what is *in your repository*: a verdict banner, a claim-to-reality map, and exactly what your approval would and would not mean.

Works with **any agent**: paste its final message, use the clipboard or a selection, or point it at the latest Claude Code session. It calls the `agentvow` command (install with `pip install .` from the repository root), so the VS Code part has no logic of its own and the same report works in a terminal, a browser or CI.

Commands (Command Palette): *Check an agent's message*, *Check the message on the clipboard*, *Check the selected text*, *Check the latest Claude Code session in this workspace*, *Show the last report*. A status-bar item shows the last result.

Safety: by default the extension only runs the `agentvow` command you installed (static checks); the project's own tests are never run unless you enable the setting. Settings can enable running the project's tests (in a network-denied sandbox on macOS; this runs the workspace's test code, and is disabled in untrusted workspaces) and reading CI results via the GitHub CLI. The report webview has scripts, network, forms and frames disabled. The `command`, `python` and `testCommand` settings can only be set in user (machine) settings, never by a workspace. Results from the agent hook are displayed only if sealed by Agentvow (HMAC with a key outside the repository); this stops a repository from forging a green status but not a process running as you that can read that key.

This is a prototype; it informs your decision and never approves, rejects or merges anything.
