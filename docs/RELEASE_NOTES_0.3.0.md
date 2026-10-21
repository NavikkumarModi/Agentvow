# Agentvow 0.3.0 (release candidate; not published)

Agentvow checks what a coding agent says it did against what it can independently observe. It informs you; it never approves, rejects or merges, and no language model decides a verdict. Still a prototype, not a safety verdict.

## New
- **`agentvow init`** adds the two Claude Code hooks (PostToolUse `post-test-hook`, Stop `check --hook --evidence-pack`) to `.claude/settings.local.json` (`--shared`: `.claude/settings.json`; `--user`: `~/.claude/settings.json`). It previews, asks for confirmation (`--yes`, `--dry-run`), keeps a backup and the file's permissions, refuses symbolic links, never edits another hook, leaves an Agentvow hook you customised unchanged unless `--force`, and runs the end-to-end self test. `agentvow init --remove` undoes it.
- **A fairer project-native context.** The evidence pack's "project-native setup" is built from the repository's own files: setup and requirements files, the `pip install` lines of the first CI workflow job that runs the tests, Dockerfile `pip install` lines and other requirements files, validated like a recipe; the pack lists the steps and CI environment names it used, says which of those files the change touched, and notes steps that failed or were left out. No new dependency. Requirements files with index or URL options, VCS requirements, outside includes or symbolic links are not installed.
- **Actionable UNKNOWN.** When a context did not reproduce, the pack adds a plain-language next step: the missing package and which context lacked it, a credential the tests need, a size/disk/time guard (with the setting to change), a command that ran no tests, a timeout, a failure, or the project's own package not importable.
- **The receipt says what the replay saw beyond the commit**: uncommitted changes and new untracked files (copied in), uncommitted symbolic links not copied, and that git-ignored files are not included.

## Security note
A replay of an untrusted repository installs the PyPI names that the repository's own files name and runs its tests in the sandbox (network off for tests; network on for installs). An sdist build executes code at install time. Treat it like running the project's tests. See `docs/SECURITY_MODEL.md`.

## Known limits
Python repositories only; capture covers Python packages, not system packages, services, generated files or secrets; running tests needs macOS or Linux; the hook shapes are verified for Claude Code 2.1.263 and (earlier) Copilot in VS Code only; `agentvow init` supports Claude Code only; the workflow reader supports a subset of YAML (compared with PyYAML on 531 public workflow files: identical on 518, different on 3, 10 not compared; flow-style YAML is refused with a note); results come from feasibility-scale studies (one model, small samples) and reproduction is not correctness.
