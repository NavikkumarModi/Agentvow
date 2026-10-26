# Agentvow 0.4.5

Agentvow checks what a coding agent says it did against what it can independently observe. It informs you; it never approves, rejects or merges, and no language model decides a verdict. Still a prototype, not a safety verdict.

## Changed: the default policy now asks a person when a change could have shaped its own test output
A passing result is no longer simply allowed when the change **modified an existing test file, added or edited a file that runs when tests start** (`conftest.py`, `sitecustomize.py`, `usercustomize.py`, a `.pth` file, a test package's `__init__.py`) **or changed the test runner's configuration** (`pytest.ini`, `.coveragerc`, or pytest and coverage settings in `pyproject.toml`, `setup.cfg`, `tox.ini`). The new policy rule `harness_warning` (default `needs_acknowledgement`) asks a named person to acknowledge such a result; set it to `allow` in your policy file to keep the old behaviour, or `block`. The receipt records the reason per claim in a new field `harness_warning` (`modified_test_file`, `autorun_file`, `test_config`).

**What this means in practice:** a pull request that edits an existing test file now needs an acknowledgement under the default policy. Ordinary changes are unaffected. **A policy file that uses the new key is rejected by Agentvow 0.4.4 and earlier** (an unknown key blocks): pin the gate's `agentvow-version` to 0.4.5 or later, and, if you run the control plane service, raise `AGENTVOW_CP_MIN_TOOL_VERSION` to 0.4.5 so a caller cannot choose an older version to avoid the rule.

## Known limits
As before: Python repositories only; capture covers Python packages, not system packages, services, generated files or secrets; running tests needs macOS or Linux; a pass is evidence to weigh, not verification. The same code hidden in ordinary source or in an extra test file is still believed without a question (a pinned, documented limit of replaying a repository's own test code). The notification, the policy refresh and the fork path of the control plane have not run on GitHub.
