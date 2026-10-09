First public release of Agentvow (prototype).

Agentvow checks what a coding agent *said* it did against what is *in your repository*, and shows you the difference. It informs; it never approves, rejects or merges, and no language model is in the verdict path. UNKNOWN is a real result.

- Checks "tests pass" (sandboxed test runs on macOS and Linux, plus CI results), "backward compatible" (public API diff) and "no downstream impact" (import graph).
- Works with Claude Code and GitHub Copilot hooks, a VS Code extension (status bar, report panel, notifications, `@agentvow`), and a GitHub Action for pull requests.
- Optional feedback mode asks the agent once to correct a contradicted statement; optional background test runs update the verdict when your suite finishes.
- Hardened after three adversarial reviews; residual risks are listed in docs/SECURITY_MODEL.md. Not a safety verdict; test results are only as trustworthy as the repository's own test code.

Install: `pip install agentvow` (once published) or from a clone `pip install .`; extension from the Marketplace or `dist/agentvow-0.1.0.vsix`.
