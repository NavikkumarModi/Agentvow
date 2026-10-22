# The Agentvow gate (reusable GitHub workflow)

`.github/workflows/gate.yml` is a reusable workflow for pull requests, in three jobs so that **no job that runs the pull request's code holds a credential**:
- **replay** (`permissions: contents: read`): refuses unsafe inputs and events, checks out the exact head with no stored credentials, installs Agentvow **from PyPI at an exact version** (there is deliberately no way to install it from the pull request's own checkout), installs bubblewrap, runs `agentvow check --evidence-pack` and `agentvow receipt` from a neutral directory with every credential-like variable removed, reads the policy **from the base branch**, evaluates it, writes the job summary and uploads the receipt and the evaluation as an artifact.
- **upload** (only when `service-url` is set; the only job with `id-token: write`): downloads the artifact and posts the receipt to the control plane with a GitHub OIDC token. It never checks out or runs pull-request code.
- **decide** (no permissions): applies `fail-on` to the stricter of the local and the service decision. Any missing piece counts as block: an empty or failed local evaluation, a failed replay job, an expected service answer that did not arrive, an error from the service.

```yaml
name: gate
on: pull_request            # never pull_request_target
permissions: { contents: read, id-token: write }    # id-token only when you set service-url
jobs:
  gate:
    uses: NavikkumarModi/Agentvow/.github/workflows/gate.yml@<release tag or commit>
    with:
      fail-on: block        # block | needs_acknowledgement | never
      # service-url: https://...   # the control plane; empty = local policy evaluation only (free tier)
```
Inputs are validated before anything runs: the event must be `pull_request`, `push` or `workflow_dispatch`; `test-timeout` a whole number; `agentvow-version` an exact version of digits and dots; `policy-path` a plain relative path; `service-url` https (or localhost for tests).

**Policy file** (`agentvow policy init` prints the default): a contradiction always blocks and cannot be acknowledged; UNKNOWN, a capture supplied as a file (not authenticated), and a missing measurement behind a configured coverage floor each need a named person's acknowledgement by default; optional minimum changed-line coverage and required reproducibility. **If the policy cannot be read from the base branch the gate blocks** (it does not fall back to a weaker default); if the base branch simply has no policy file the default applies. A pull request that edits the policy file is judged by the old policy.

**Why three jobs and `python -I`.** An adversarial review of this workflow found that steps run by `python` with the pull request's checkout as the working directory would import a planted `json.py` (or run a planted `pip/__main__.py`) with the job's credentials in the environment. Now every Python command in the workflow is `python -I` from the runner's temp directory, the replay job has no OIDC permission at all, and the upload job has no pull-request code. A test plants both files and asserts nothing runs.
**What it does not do.** It does not show that the code is correct; the pull request's own code writes the test output, so a pass is evidence to weigh, not verification. It runs the pull request's code (sandboxed; installs with network, tests without; no token reaches either). The receipt holds verdicts, counts and category names: no source, no free text, no environment values.
**Trust, in one line:** the control plane should accept a receipt only from this workflow at an exactly pinned reference (the OIDC claim `job_workflow_ref`) **[assumption about the claim, to confirm before the real service]**; pin the `uses:` reference (`docs/CONTROLPLANE_THREAT_MODEL.md`).
**Checked:** `tests/test_gate_workflow.py` runs the workflow's own shell steps locally against a bare `origin`, the mock control plane and a mock OIDC endpoint (a clean change flows through; a permissive policy in the pull request is ignored; an unreadable base branch blocks; a receipt whose content hash does not match is not allowed; planted `json.py` and `pip/` do not run), plus static tests of the permissions, the validations and `fail-on`. An earlier version of the workflow ran once on GitHub (pull request #3, local-policy mode, `docs/LIVE_TESTING.md`); **this three-job version has not yet run on GitHub**, and neither has the OIDC token path, a fork pull request or a macOS runner.
