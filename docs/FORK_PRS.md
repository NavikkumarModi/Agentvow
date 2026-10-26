# Fork pull requests (experimental, opt-in, not yet run on GitHub)

## The problem
For a pull request **from a fork**, GitHub runs `pull_request` workflows without an OIDC token (and with a read-only `GITHUB_TOKEN`). The service-backed gate (`gate-service.yml`) needs that token in its upload job, so on a fork pull request it reports an error, blocks, and leaves the required check pending. The local gate (`gate.yml`, no credential) works for forks as a local decision.

## What does NOT work, and why
* **`pull_request` plus a second `workflow_run` workflow that uploads the first run's artifact.** The first run's workflow file comes from the pull request, so the fork controls the receipt entirely; the second workflow would sign a forgery with a trusted identity. This breaks the one guarantee the service gives (the receipt came from the trusted replay job).
* **Skipping the approval.** `pull_request_target` runs without GitHub's "approve workflows from outside contributors" step.

## The design: `gate-service-fork.yml`
* It is for **`pull_request_target`**, which runs the workflow file **from the base branch**: the fork cannot change it, so the trusted replay job runs on the fork's code just as it does on a same-repository pull request (sandboxed, in a job with `contents: read` only and no token, with every credential variable removed, checkout without stored credentials), and the upload job (the only one with `id-token: write`) never touches the fork's code.
* It **refuses to start unless a maintainer has applied the label `agentvow-fork-gate`** to the pull request (the guard checks the event's action and label name; only users with triage or write access can label). Review the diff first, label second.
* **The commit that was labelled is the commit that is tested.** A later push by the author does not re-run anything (the workflow listens to `labeled` only); if the head moved before the upload, the service refuses the receipt (`422: not the head of that pull request`), and a fresh look and a fresh label are needed.
* The service trusts this file only when it is listed in **`AGENTVOW_CP_FORK_WORKFLOWS`** (a full 40-character sha, like the regular list), and then **only for `pull_request_target` receipts**; the regular workflow is refused under that event and the fork workflow under any other. For a `pull_request_target` token the run's own `sha` is the base branch's head, so the binding is: the receipt names its pull request, GitHub confirms that the receipt's commit is that pull request's head (and its tree hash), and the token's `ref` must be `refs/heads/<that pull request's base branch>`. Policy is read from the default branch as always.
* The replay job is **identical** to `gate-service.yml`'s except for the guard step (a test enforces it).

## Setup (opt-in)
1. Service: set `AGENTVOW_CP_FORK_WORKFLOWS` to `<owner>/<repo>/.github/workflows/gate-service-fork.yml@<40-character sha>` (the copy with your address in `ALLOWED_SERVICE_URLS`, committed like `gate-service.yml`). Unset = the path does not exist.
2. Repository: create the label `agentvow-fork-gate`; add a caller on the **base branch**:
   ```yaml
   name: agentvow-fork
   on: { pull_request_target: { types: [labeled] } }
   permissions: { contents: read, id-token: write }
   jobs:
     gate:
       uses: <owner>/<repo>/.github/workflows/gate-service-fork.yml@<40-character sha>
       with: { service-url: https://<your control plane>, fail-on: block }
   ```
3. A maintainer reads the fork's diff, then applies the label. The check then behaves as for any pull request (acknowledgement, notification, required check).

## Risks that remain (read before enabling)
* It **runs a stranger's code on your runner** after a human says yes. The sandbox and the credential-free replay job are the same ones used for every pull request, and `pip install` of the fork's requirements can still run build code with network access (documented in `docs/SECURITY_MODEL.md`). Do not label a pull request you have not read.
* Never add steps that use secrets to the fork caller workflow, and never check out or run the fork's code in a job that has a token. This is the usual `pull_request_target` rule; the shipped workflow follows it and a test pins the replay job's permissions.
* The label is the gate: anyone with triage rights can apply it. Keep that group small.
* **Not verified on GitHub at all** (this needs a second GitHub account to open a real fork pull request): that `actions/checkout` with the fork's head sha from the base repository works in this event, that the token's `ref` is `refs/heads/<base>` as assumed, and the approval flow end to end. Treat it as unverified until `docs/LIVE_TESTING.md` records a run.
