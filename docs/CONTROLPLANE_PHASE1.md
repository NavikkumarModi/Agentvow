# Control plane service, phase 1

Status: **built, adversarially reviewed once (findings fixed, `docs/review/CONTROLPLANE_REVIEW_2026-10-22.md`) and tested against fakes; never run against real GitHub, never deployed.** Code: `controlplane/service/`. Design and threats: `docs/CONTROLPLANE_THREAT_MODEL.md`.

## What it does
1. `POST /v1/receipts` (called by the gate workflow's upload job): verifies the GitHub Actions OIDC token (RS256 against GitHub's keys, issuer, audience, expiry), requires the exact trusted `job_workflow_ref` and an accepted event, requires the token's repository to equal the receipt's, requires the token to have been issued for exactly this receipt (audience `<audience>:<sha256 of the body>`) and to name its pull request or commit, asks GitHub (as oracle) whether the commit's tree hash matches the receipt and whether the commit is the pull request's head, reads the policy from the repository's **default branch** through the GitHub API, evaluates with `agentvow.policy.evaluate` and sets the check run `agentvow/evidence`.
2. `POST /v1/webhook` (GitHub App webhook, HMAC-verified): on pull-request events it creates a pending check (so a required check cannot be satisfied by silence); on a pull-request comment `/agentvow acknowledge` it requires the receipt id (`/agentvow acknowledge <id>`), a person who is a listed acknowledger **and** has write access (and, unless they own the repository account, is not the pull request's author), stores the acknowledgement against the current receipt id, re-evaluates and updates the check.
3. `GET /v1/check`, `GET /v1/audit?format=json|csv`: per-repository key (Bearer); a key for one repository never reads another's records.
4. Operator CLI: `python -m controlplane.service.cli --db PATH set-plan|issue-key|purge|usage`.

Fail-closed rules: an unreadable or invalid base-branch policy blocks; GitHub errors return 5xx and set nothing; the conclusions used are only success, failure, action_required (never neutral or skipped, which would pass a required check); a CONTRADICTED claim cannot be acknowledged away.

## GitHub App to register (owner)
Permissions: Checks read/write, Contents read, Pull requests read, Issues write (comments), Metadata read. Events: Pull request, Issue comment. Webhook URL `https://<host>/v1/webhook`, with a secret. Then protect the target branch with a required status check named `agentvow/evidence` and choose this App as its **source** (with source "any", a writer's own `GITHUB_TOKEN` can post a green check of that name).

## Environment variables
`AGENTVOW_CP_APP_ID`, `AGENTVOW_CP_PRIVATE_KEY_FILE` (path to the PEM; preferred) or `AGENTVOW_CP_PRIVATE_KEY` (PEM, `\n` allowed), `AGENTVOW_CP_WEBHOOK_SECRET`, `AGENTVOW_CP_AUDIENCE` (the audience the gate workflow requests), `AGENTVOW_CP_TRUSTED_WORKFLOWS` (comma-separated exact `job_workflow_ref` values), `AGENTVOW_CP_DB` (default `/data/controlplane.db`). The process refuses to start if one is missing (`uvicorn --factory`).

## Run
`docker build -f controlplane/service/Dockerfile -t agentvow-controlplane .` then run with a `/data` volume and TLS in front. One process only (SQLite with an in-process lock).

## Not verified (honest list)
* Real GitHub JWKS, the real `job_workflow_ref` claim for a reusable workflow, installation-token and check-run API behaviour, webhook payload shapes: tested only against hand-built fakes.
* Whether GitHub accepts a required status from this App on the chosen branch protection; fork pull requests; callers without `id-token: write`.
* Billing: plans are set by the operator by hand; no payment integration. Usage limits and rate limits are in-process.
* No deployment, domain, TLS, backups, monitoring or privacy policy; these need the owner's accounts.
* The fixes have had no second review. Assumptions about GitHub's token claims (`ref`, `sha`, `repository_id`, a custom audience string) are unconfirmed until a live run. Residuals: `docs/review/CONTROLPLANE_REVIEW_2026-10-22.md`.
