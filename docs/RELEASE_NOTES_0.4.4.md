# Agentvow 0.4.4

Agentvow checks what a coding agent says it did against what it can independently observe. It informs you; it never approves, rejects or merges, and no language model decides a verdict. Still a prototype, not a safety verdict.

## New in the package
- **Plain-language explanations.** `agentvow policy explain --result FILE` (and the control plane's check, and the gate's job summary from this version on) says what happened, what it means for the merge, what to do, who can acknowledge and with which exact command, and what a pass does *not* show, instead of a list of rule names. A policy that sets a rule to block is no longer offered an acknowledgement; each receipt that needs one is listed with its own command.
- **A wider warning when a change could have shaped its own test output.** The result is downgraded from "supported" to "no contradiction found" with a plain warning when the change modified an existing test file, **or added or edited a file that runs when tests start** (`conftest.py`, `sitecustomize.py`, `usercustomize.py`, a `.pth` file, a test package's `__init__.py`), **or changed what the test runner selects or measures** (`pytest.ini`, `.coveragerc`, or pytest and coverage settings in `pyproject.toml`, `setup.cfg`, `tox.ini`; ordinary edits of those files do not warn). The same code hidden in ordinary source or in an extra test file is still believed without a warning: this is a known limit of replaying a repository's own test code, pinned by tests and stated in `docs/TRUST_MODEL.md`.
- `capture_authenticated` in a receipt must be a real true, false or null.
- `agentvow policy evaluate` also prints the policy's `acknowledgers`; `policy explain` names them, and in its local mode (the command line and the gate's job summary) explains how to acknowledge without a pull request comment flow, which is the control plane's.

## In the repository (not in the wheel; the control plane service is experimental and not deployed)
- **Acknowledgement notification:** the service comments on the pull request, mentioning the listed acknowledgers, once when a change first needs an acknowledgement (capped and rate limited, never breaks the check, can be switched off).
- **Policy refresh:** on a push to the default branch, open pull requests whose published decision used an older policy are re-evaluated (needs the App subscribed to the Push event).
- **Fork pull requests, experimental and opt-in** (`docs/FORK_PRS.md`): a separate sha-pinned workflow for `pull_request_target` that runs only after a maintainer labels the pull request; never run on GitHub.
- Five adversarial reviews of the service and the gate, with their findings fixed (`docs/review/CONTROLPLANE_REVIEW_2026-10-22.md`); the gate workflows now give the plain explanation when the installed Agentvow has it (set the default `agentvow-version` to 0.4.4 or later).

## Known limits
As before: Python repositories only; capture covers Python packages, not system packages, services, generated files or secrets; running tests needs macOS or Linux; a pass is evidence to weigh, not verification; a repository's own test code can fake its output. Not run on GitHub: the notification, the policy refresh and the fork path.
