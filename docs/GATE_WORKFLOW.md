# The Agentvow gate (reusable GitHub workflows)

Two reusable workflows with the **same replay job** (a test enforces that they are identical):

| | `gate.yml` (local decision) | `gate-service.yml` (control plane) |
|---|---|---|
| Jobs | replay, decide | replay, upload, decide |
| Permissions the caller must grant | `contents: read` only | `contents: read` and `id-token: write` (the upload job only) |
| Needs a service | no | yes (`service-url`, one of the addresses written in the file) |
| Who can trust it | nobody: it produces a job summary and a pass/fail | the control plane trusts exactly this file at an exact commit sha |
| Pin the `uses:` reference | to a full commit sha (recommended) | **to a full 40-character commit sha (the service refuses a tag or a branch)** |

**Policy authority, in one place.** In both workflows the replay job evaluates the policy read from the pull request's **base branch** (a local decision shown in the job summary; if it cannot be read the gate blocks, if the base has no policy file the default applies). The control plane, which publishes the required check, reads the policy from the repository's **default branch** through the GitHub API at the commit it resolves at that moment, never from the change and never from a base branch the pull request's author chose. For a pull request into the default branch the two are the same file; for a pull request into another branch only the control plane's decision gates the merge.

## What the jobs do
- **replay** (`permissions: contents: read`): refuses unsafe inputs and events, checks out the exact head with no stored credentials, installs Agentvow **from PyPI at an exact version** (there is deliberately no way to install it from the pull request's own checkout), installs bubblewrap, runs `agentvow check --evidence-pack` and `agentvow receipt` from a neutral directory with every credential-like variable removed, evaluates the policy, writes the job summary and uploads the receipt and the evaluation as an artifact. Its output carries the receipt's sha256.
- **upload** (`gate-service.yml` only; the only job with `id-token: write`): downloads the artifact, refuses unless the receipt's hash equals the replay job's output, refuses unless `service-url` is exactly one of the addresses written in the workflow (`ALLOWED_SERVICE_URLS`) **before any token is requested**, then posts the receipt with a GitHub OIDC token whose audience is `<audience>:<sha256 of the receipt>`. It never checks out or runs pull-request code.
- **decide** (no permissions): applies `fail-on` (`block` default, `needs_acknowledgement`, `never`) to the local decision, and in `gate-service.yml` to the stricter of the local and the service decision. Any missing piece counts as block: an empty or failed local evaluation, a failed replay job, an expected service answer that did not arrive, an error from the service.

```yaml
# local decision only
name: gate
on: pull_request            # never pull_request_target
permissions: { contents: read }
jobs:
  gate:
    uses: NavikkumarModi/Agentvow/.github/workflows/gate.yml@<40-character commit sha>
    with: { fail-on: block }

# with the control plane service
permissions: { contents: read, id-token: write }
jobs:
  gate:
    uses: NavikkumarModi/Agentvow/.github/workflows/gate-service.yml@<40-character commit sha>
    with: { service-url: https://<your control plane>, fail-on: block }
```
When the caller pins by sha, GitHub's token carries that sha in `job_workflow_ref` and in `job_workflow_sha` (seen live on 2026-10-26), so a pinned entry in the service's `AGENTVOW_CP_TRUSTED_WORKFLOWS` names an immutable revision. To self-host, copy `gate-service.yml`, put your address in `ALLOWED_SERVICE_URLS`, and make your service trust your copy at its sha. The hosted address in the shipped file is a placeholder, so nothing uploads from it until one is assigned.

Inputs are validated before anything runs: the event must be `pull_request`, `push` or `workflow_dispatch`; `test-timeout` a whole number; `agentvow-version` an exact version of digits and dots; `policy-path` a plain relative path; `fail-on` one of three values.

**Policy file** (`agentvow policy init` prints the default): a contradiction always blocks and cannot be acknowledged; UNKNOWN, a capture supplied as a file (not authenticated), a replay that left out pinned packages (`partial_capture`, 0.4.3 and later) and a missing measurement behind a configured coverage floor each need a named person's acknowledgement by default; optional minimum changed-line coverage and required reproducibility. A pull request that edits the policy file is judged by the old policy. Keep the file at a path that does not start with `.agentvow/` on Agentvow versions before 0.4.1.

**Why separate jobs and `python -I`.** An adversarial review found that steps run by `python` with the pull request's checkout as the working directory would import a planted `json.py` (or run a planted `pip/__main__.py`) with the job's credentials in the environment. Every Python command in the workflows is `python -I` from the runner's temp directory, the replay job has no OIDC permission at all, and the upload job has no pull-request code. A test plants both files and asserts nothing runs.

**What it does not do.** It does not show that the code is correct; the pull request's own code writes the test output, so a pass is evidence to weigh, not verification (`docs/TRUST_MODEL.md`). It runs the pull request's code (sandboxed; installs with network, tests without; no token reaches either). The receipt holds verdicts, counts and category names: no source, no free text, no environment values. **Fork pull requests are not supported** by `gate-service.yml`: GitHub gives fork workflows no OIDC token, so the upload step reports an error and the required check stays pending (`gate.yml` works for forks as a local decision).

**Checked:** `tests/test_gate_workflow.py` runs the workflow's own shell steps locally against a bare `origin`, the mock control plane and a mock OIDC endpoint (a clean change flows through; a permissive policy in the pull request is ignored; an unreadable base branch blocks; a receipt whose content hash does not match is not allowed; planted `json.py` and `pip/` do not run), plus static tests of the permissions, the allow-list, the equality of the replay jobs and `fail-on`. On real GitHub: the three-job workflow in local mode (pull request #4 of this repository, 2026-10-22), the control plane path with a required check pinned to the App (2026-10-23, the workflow called by tag), the cross-repository call with `id-token: write` (2026-10-23). **After the split into two workflows (2026-10-26):** the local `gate.yml` ran with `contents: read` only; the sha-pinned `gate-service.yml` through the service was accepted, and a different commit of the file and a branch-name pin were refused (`docs/LIVE_TESTING.md`). **Not run at all:** a fork pull request, a macOS runner.
