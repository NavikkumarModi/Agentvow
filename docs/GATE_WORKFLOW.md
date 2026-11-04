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

**What the check says.** Both the job summary and the control plane's check run explain the decision in plain words (`agentvow policy explain`, Agentvow 0.4.4 and later; older versions print a plain list of rules). Example for an unconfirmed claim: a title "Agentvow: a person must review and acknowledge this"; "Agentvow could not fully confirm this change. A person named in the repository's policy must look at it and acknowledge it before it can merge."; what was found and what to do about it; "To acknowledge: a listed acknowledger comments `/agentvow acknowledge <id>` on this pull request. Listed acknowledgers: @name."; and, every time, "What this does not show: that the change is correct, that the tests are good, or that the code under test did not influence its own test output."

**Policy file** (`agentvow policy init` prints the default): a contradiction always blocks and cannot be acknowledged; UNKNOWN, a capture supplied as a file (not authenticated), a replay that left out pinned packages (`partial_capture`, 0.4.3 and later), a passing result whose change modified existing tests, a file that runs when tests start or the test runner's configuration (`harness_warning`, the release after 0.4.4) and a statement about files or documentation that git's change list disagrees with (`description_mismatch`, 0.4.5), and a missing measurement behind a configured coverage floor each need a named person's acknowledgement by default; optional minimum changed-line coverage and required reproducibility. A pull request that edits the policy file is judged by the old policy. Keep the file at a path that does not start with `.agentvow/` on Agentvow versions before 0.4.1.

**Why separate jobs and `python -I`.** An adversarial review found that steps run by `python` with the pull request's checkout as the working directory would import a planted `json.py` (or run a planted `pip/__main__.py`) with the job's credentials in the environment. Every Python command in the workflows is `python -I` from the runner's temp directory, the replay job has no OIDC permission at all, and the upload job has no pull-request code. A test plants both files and asserts nothing runs.

**What it does not do.** It does not show that the code is correct; the pull request's own code writes the test output, so a pass is evidence to weigh, not verification (`docs/TRUST_MODEL.md`). It runs the pull request's code (sandboxed; installs with network, tests without; no token reaches either). The receipt holds verdicts, counts and category names: no source, no free text, no environment values. **Fork pull requests are not supported** by `gate-service.yml`: GitHub gives fork workflows no OIDC token, so the upload step reports an error and the required check stays pending (`gate.yml` works for forks as a local decision). An experimental, opt-in path exists (`gate-service-fork.yml`, `pull_request_target`, only after a maintainer labels the pull request): `docs/FORK_PRS.md`; it has not been run on GitHub.

**Checked:** `tests/test_gate_workflow.py` runs the workflow's own shell steps locally against a bare `origin`, the mock control plane and a mock OIDC endpoint (a clean change flows through; a permissive policy in the pull request is ignored; an unreadable base branch blocks; a receipt whose content hash does not match is not allowed; planted `json.py` and `pip/` do not run), plus static tests of the permissions, the allow-list, the equality of the replay jobs and `fail-on`. On real GitHub: the three-job workflow in local mode (pull request #4 of this repository, 2026-10-22), the control plane path with a required check pinned to the App (2026-10-23, the workflow called by tag), the cross-repository call with `id-token: write` (2026-10-23). **After the split into two workflows (2026-10-26):** the local `gate.yml` ran with `contents: read` only; the sha-pinned `gate-service.yml` through the service was accepted, and a different commit of the file and a branch-name pin were refused (`docs/LIVE_TESTING.md`). **Not run at all:** a fork pull request, a macOS runner.

## The review queue workflow (`queue.yml`, repository only, not in the wheel)
A third reusable workflow ranks a repository's open pull requests by what the gate found, as a job summary. It is **read-only**: permissions `contents: read`, `pull-requests: read`, `actions: read`; no `id-token`; it checks out nothing, runs no pull-request code and posts nothing. It installs `agentvow` from PyPI at an exact version (0.5.1 or later), reads the gate's `agentvow-gate` artifacts with `gh` (`agentvow queue --github`), and reads the policy from the **default branch** (a missing file means the built-in default policy; any other read failure, or a policy that cannot be parsed, fails the job instead of using a different policy). It is refused on any event except `schedule` and `workflow_dispatch`. `fail-on: never` (default) only reports; `needs_person` fails the job when any pull request is stopped or needs a person.
```yaml
on: { schedule: [{ cron: "0 7 * * 1-5" }], workflow_dispatch: {} }
permissions: { contents: read, pull-requests: read, actions: read }
jobs:
  queue:
    uses: NavikkumarModi/Agentvow/.github/workflows/queue.yml@<40-character commit sha>
    with: { fail-on: never }
```
**Verification (optional):** `verify: report|require` with `signer-digests` (the allowed commits of `gate-attest.yml`, mandatory) passes `--verify` through to `agentvow queue`; it adds `attestations: read` to the token and needs agentvow 0.5.2 or later (the option does not exist in 0.5.1). Off by default. **Not run on GitHub yet** (only the input checks were exercised locally).

**What it does not do:** unless `verify` is on, the receipts are read from workflow artifacts and are **not authenticated** (a pull request can edit its own workflow; the control plane is the authenticated path); a pull request without a receipt is listed as "no receipt", which is no information, not a clean result; "no flag raised" is not a safety statement. **Checked:** 8 static tests (`tests/test_queue_workflow.py`: read-only permissions, no checkout, schedule or manual dispatch only, inputs only through environment variables, pinned actions, isolated Python, policy failure modes) and the job's own shell step run locally against GitHub for a missing policy (default) and an unparseable one (fails). **Not run:** on GitHub Actions, and against a repository with open gated pull requests.

## Authenticated receipts (`gate-attest.yml` and `queue --github --verify`, repository workflow)
The queue's receipts come from workflow artifacts that a pull request can forge by editing its own workflow. `gate-attest.yml` is the gate with a third job, `attest`, that checks the receipt is the exact file the replay hashed and signs it with GitHub's artifact attestation (`actions/attest-build-provenance`, reused, no signing of our own). The replay job is identical to `gate.yml`'s and still holds no token; `attest` runs no pull-request code and is the only job with `id-token: write` and `attestations: write`. Callers grant those two permissions and pin the workflow by full sha.

`agentvow queue --github OWNER/NAME --verify report|require --signer-digest <40-hex sha of gate-attest.yml>` runs `gh attestation verify` on each receipt (the bytes in the artifact) against the pinned signer workflow, then checks the signer's commit against the allowed list you give. **The list is mandatory**: the live experiments (`docs/research/RECEIPT_AUTH_DESIGN.md`, section 9) showed that a pull request which edits the signer file at the same path still passes a path-only check. A receipt that does not verify is shown as **not authenticated** (`report`) or **needs a person** (`require`); it is never ranked as "no flag raised". A stop stays a stop.

Limits: attestations exist only for public repositories (or GitHub Enterprise Cloud); fork pull requests get no OIDC token and stay unverified; a verified receipt says the gate workflow produced the file, not that its replay was right (the pull request's code still wrote the test output); the signer path and commit list are yours to maintain; the check needs `gh` and network access to GitHub. **Tested:** 18 tests with a fake `gh` and static checks of the workflow; the attestation mechanism itself in a throwaway public repository with a stand-in signer (one honest receipt verified, three forgeries rejected). **Run live (2026-11-03, public throwaway repository):** the real `gate-attest.yml` produced an attested receipt that `--verify` accepted, and a pull request that uploaded its own forged `agentvow-gate` artifact was ranked "no flag raised" without `--verify` and "not authenticated" or "needs a person" with it (`docs/research/RECEIPT_AUTH_DESIGN.md`, section 10). **Not tested:** fork pull requests; private repositories.

### The gate's configuration (receipt `gate_inputs`, policy `allowed_test_commands`, `min_tool_version`, `require_gate_inputs`)
The caller workflow is a file the pull request can edit, so a pull request can set the gate's `test-command` and `agentvow-version` even when the gate itself is pinned and its receipt is **verified**. An adversarial pass found that the attestation does not bind these inputs and the receipt did not record them (`docs/research/RECEIPT_AUTH_DESIGN.md`, section 11). The four gate workflows now pass `test-command` and `test-timeout` to the receipt step (`AGENTVOW_GATE_TEST_COMMAND`, `AGENTVOW_GATE_TEST_TIMEOUT`), and the receipt records them as `gate_inputs` (capped printable text and a whole number; older workflows and versions record nothing).

Three policy keys, read from the base branch like the rest of the policy, all off by default so nothing changes until you set them: `allowed_test_commands` (a list; a command not in it, other than the default empty one, needs a person), `min_tool_version` (a receipt from an older Agentvow, or one that does not say, needs a person) and `require_gate_inputs` (a receipt without `gate_inputs` needs a person, which also catches a pull request that picks an old version that does not record them). Because a pull request chooses the version, the floor and `require_gate_inputs` belong together. Listing no commands (`[]`) means only the default test command is trusted.

What this does not do: it does not stop the pull request from editing the workflow, it makes the edit visible and routes it to a person. A policy that does not set these keys leaves the gap open. **Tested:** 13 tests (recording, validation, each rule, acknowledgement, a contradiction still blocks, all four workflows pass the inputs); the `receipt` command run locally with and without the environment variables. **Not run:** on GitHub.
