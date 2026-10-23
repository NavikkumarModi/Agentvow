# Control plane service, phase 1

Status: **built, run once against real GitHub (`docs/LIVE_TESTING.md`, 2026-10-23: 10 acceptance tests passed after two defects were fixed; fork pull requests not tested), adversarially reviewed twice (findings fixed, `docs/review/CONTROLPLANE_REVIEW_2026-10-22.md`) and tested against fakes; never run against real GitHub, never deployed.** Code: `controlplane/service/`. Design and threats: `docs/CONTROLPLANE_THREAT_MODEL.md`.

## What it does
1. `POST /v1/receipts` (called by the gate workflow's upload job): verifies the GitHub Actions OIDC token (RS256 against GitHub's keys, issuer, audience, expiry), requires the exact trusted `job_workflow_ref` and an accepted event, requires the token's repository to equal the receipt's, requires the token to have been issued for exactly this receipt (audience `<audience>:<sha256 of the body>`) and to name its pull request or commit, asks GitHub (as oracle) whether the commit's tree hash matches the receipt and whether the commit is the pull request's head, reads the policy from the repository's **default branch** through the GitHub API, evaluates with `agentvow.policy.evaluate` and sets the check run `agentvow/evidence`.
2. `POST /v1/webhook` (GitHub App webhook, HMAC-verified): on pull-request events it creates a pending check (so a required check cannot be satisfied by silence); on a pull-request comment `/agentvow acknowledge` it requires the receipt id (`/agentvow acknowledge <id>`), a person who is a listed acknowledger **and** has write access (and, unless they own the repository account, is not the pull request's author), stores the acknowledgement against the current receipt id, re-evaluates and updates the check.
3. `GET /v1/check`, `GET /v1/audit?format=json|csv`: per-repository key (Bearer); a key for one repository never reads another's records.
4. Operator CLI: `python -m controlplane.service.cli --db PATH set-plan|issue-key|purge|usage`.

Fail-closed rules: an unreadable or invalid base-branch policy blocks; GitHub errors return 5xx and set nothing; the conclusions used are only success, failure, action_required (never neutral or skipped, which would pass a required check); a CONTRADICTED claim cannot be acknowledged away.

## GitHub App to register (owner)
Permissions: Checks read/write, Contents read, Pull requests write, Issues write (comments), Metadata read. Events: Pull request, Issue comment. Webhook URL `https://<host>/v1/webhook`, with a secret. Then protect the target branch with a required status check named `agentvow/evidence` and choose this App as its **source** (with source "any", a writer's own `GITHUB_TOKEN` can post a green check of that name).

## Environment variables
`AGENTVOW_CP_APP_ID`, `AGENTVOW_CP_PRIVATE_KEY_FILE` (path to the PEM; preferred) or `AGENTVOW_CP_PRIVATE_KEY` (PEM, `\n` allowed), `AGENTVOW_CP_WEBHOOK_SECRET`, `AGENTVOW_CP_AUDIENCE` (the audience the gate workflow requests), `AGENTVOW_CP_TRUSTED_WORKFLOWS` (comma-separated exact `job_workflow_ref` values), `AGENTVOW_CP_DB` (default `/data/controlplane.db`). The process refuses to start if one is missing (`uvicorn --factory`).

## Run
`docker build -f controlplane/service/Dockerfile -t agentvow-controlplane .` then run with a `/data` volume and TLS in front. One process only (SQLite with an in-process lock).

## Not verified (honest list)
* **Confirmed live (2026-10-23, `docs/LIVE_TESTING.md`):** GitHub's JWKS and RS256 tokens, the claims `repository_id`, `ref`, `sha`, `event_name`, `job_workflow_ref`, a custom audience, installation tokens, check-run creation and update, webhook signatures and payloads, pull-request comments, a required status pinned to the App (a spoofed check from `GITHUB_TOKEN` did not count), a caller without `id-token: write` (run fails to start; check stays pending).
* Still unverified: fork pull requests; a run with real concurrency or rate limits; slash-containing default branch names; macOS runners; `pull_request` events from organisations' repositories; private repositories on a paid plan.
* Billing: plans are set by the operator by hand; no payment integration. Usage limits and rate limits are in-process.
* No deployment, domain, TLS, backups, monitoring or privacy policy; these need the owner's accounts.
* A third review of the later additions is in the review record (3-C1 to 3-P6, fixed). A second review of the fixes found more (2-1 to 2-9 in the review record); those are fixed and have had no third review.  Residuals: `docs/review/CONTROLPLANE_REVIEW_2026-10-22.md`.

## Added after the live run (2026-10-23)
* **Account plans:** `set-plan <owner>` covers every repository of an account; a repository's own plan wins; an ended plan falls back.
* **Tenant lifecycle:** the App's `installation` and `installation_repositories` events are recorded; the daily `maintain` asks GitHub whether the App is still on each repository with stored data and erases a repository the App has been gone from for 30 days (the webhook events are hints, not the trigger). Receipts are deleted after the plan's retention (free 30 days, team 365, business 730). GitHub should deliver these two events without a subscription; the payload handling follows GitHub's documented shape but has not been seen live (unverified).
* **Read-only dashboard** at `/dashboard`: the repository and its audit key are sent in a POST body (never a URL); the page is escaped and served with a strict content security policy.
* **Operator commands:** `backup`, `stats`, `erase`, `maintain`, `unbind-repo`; deployment recipe in `docs/DEPLOY.md`; image workflow `.github/workflows/service-image.yml`.
* **Fork pull requests are not supported.** GitHub gives workflows triggered from forks no OIDC token (not verified by a fork run here), so the gate's upload step reports an error, the effective decision is block, and the required check stays pending. A maintainer who wants to merge a fork's change pushes it to a branch of the repository (which then runs with a token) or merges through a documented exception.
