# The Agentvow gate (reusable GitHub workflow; unreleased, phase 0)

`.github/workflows/gate.yml` is a reusable workflow for pull requests. It replays the pull request's tests in Agentvow's sandbox, builds a minimal **receipt**, evaluates it under the **policy from the base branch**, optionally posts the receipt to a control plane, and fails the job according to `fail-on`. It needs an Agentvow release that has `receipt` and `policy` (0.4.0 or later; not released yet).

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
Steps, in order: refuse unsafe events (anything but `pull_request`, `push`, `workflow_dispatch`), a non-numeric timeout or a bad `fail-on`; check out the exact head with no stored credentials; install Agentvow; install bubblewrap (GitHub-hosted runners); `agentvow check --evidence-pack` and `agentvow receipt` with every credential-like variable removed from the environment (`env -u ACTIONS_ID_TOKEN_REQUEST_TOKEN ... GITHUB_TOKEN`); read `.agentvow/policy.json` **from `origin/<base branch>`** (never from the pull request) and run `agentvow policy evaluate`; if `service-url` is set, request an OIDC token for the audience and POST the receipt; upload the receipt as an artifact; apply `fail-on` to the stricter of the local and the service decision (an error from the service counts as block; no result at all counts as block).

**Policy file** (`agentvow policy init` prints the default): contradicted always blocks and cannot be acknowledged; unknown needs a named person's acknowledgement by default; optional minimum changed-line coverage, required reproducibility, and how to treat an unauthenticated capture. **Without a policy file in the base branch the default applies.** A pull request that edits the policy file is judged by the old policy.

**What it does not do.** It does not show that the code is correct; the pull request's own code writes the test output, so a pass is evidence to weigh, not verification. It runs the pull request's code (sandboxed, installs with network, tests without; no token reaches either), so use it only where you would run the project's tests anyway. The receipt holds verdicts, counts and category names, no source, no free text, no environment values.
**Trust, in one line:** the control plane should accept a receipt only when the OIDC claim `job_workflow_ref` names this workflow at a pinned reference **[assumption about the claim, to confirm before the real service]**; pin the `uses:` reference so the pull request cannot swap the workflow (`docs/CONTROLPLANE_THREAT_MODEL.md`).
**Checked:** `tests/test_gate_workflow.py` runs the workflow's own shell steps locally, in order, against a bare `origin`, the mock control plane and a mock OIDC endpoint (a clean change flows through and is allowed; a permissive policy added by the pull request is ignored in favour of the base branch's strict one; a receipt whose content hash GitHub's side does not match is not allowed), plus static tests of the guards and `fail-on`. **Not checked:** a run on GitHub itself (the real OIDC token, the called-workflow identity claim, `actions/checkout` of a fork).
