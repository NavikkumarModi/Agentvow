# Control plane service, phase 1

Status (2026-10-26), as a matrix instead of a sentence:

| Part | State |
|---|---|
| Receipt upload, OIDC verification, policy, check run, acknowledgement by comment, audit export | **Live-tested** once against real GitHub from a laptop behind a tunnel (`docs/LIVE_TESTING.md`, 2026-10-23: 10 acceptance tests passed after two defects were fixed) |
| Required check pinned to the App as its source; a spoofed check from `GITHUB_TOKEN` did not count | **Live-tested** (same run) |
| Commit-sha pins for the trusted workflow, `job_workflow_sha` check, the split into `gate.yml` and `gate-service.yml` | **Live-tested 2026-10-26** (`docs/LIVE_TESTING.md`): a sha-pinned caller was accepted and published the check; another commit of the same file and a branch-name pin were refused with 403; a tag-pinned configuration is refused at startup. The pending check on open and the acknowledgement flow (bare, wrong id, correct id) were re-run with the sha-pinned files the same day: they work |
| Account plans, retention, erasure driven by GitHub's answer, dashboard, backup, image, compose recipe | **Tested against fakes**; the image builds and runs (local Docker and CI); never on a hosted machine |
| Installation events (`installation`, `installation_repositories`) | Handled per GitHub's documented shape; **never seen live** |
| Fork pull requests | **Experimental, opt-in** (`docs/FORK_PRS.md`: `gate-service-fork.yml`, `AGENTVOW_CP_FORK_WORKFLOWS`): tested against fakes and the workflow's own guard; **never run on GitHub** (needs a second account) |
| Real concurrency, rate limits, macOS runners, private repositories on a paid plan | **Not tested** |
| Deployment (domain, TLS, hosting, billing, monitoring, privacy policy) | **Not done**; needs the owner's accounts |
| Adversarial review | Three rounds, findings fixed (`docs/review/CONTROLPLANE_REVIEW_2026-10-22.md`); the fixes of the third round and the later changes have had no further review |

Code: `controlplane/service/`. Design and threats: `docs/CONTROLPLANE_THREAT_MODEL.md`.

## What it does
1. `POST /v1/receipts` (called by the gate workflow's upload job): verifies the GitHub Actions OIDC token (RS256 against GitHub's keys, issuer, audience, expiry), requires the exact trusted `job_workflow_ref` (a full commit sha; the service refuses to start with a tag or branch) and that `job_workflow_sha` agrees and an accepted event, requires the token's repository to equal the receipt's, requires the token to have been issued for exactly this receipt (audience `<audience>:<sha256 of the body>`) and to name its pull request or commit, asks GitHub (as oracle) whether the commit's tree hash matches the receipt and whether the commit is the pull request's head, reads the policy from the repository's **default branch** through the GitHub API (the gate workflow's local decision reads the pull request's base branch; see `docs/GATE_WORKFLOW.md`, "Policy authority"), evaluates with `agentvow.policy.evaluate` and sets the check run `agentvow/evidence` with a plain-language title and explanation (`agentvow.explain`).
   **Notification:** when a change first needs an acknowledgement, the service also comments on the pull request and mentions the listed acknowledgers (`AGENTVOW_CP_NOTIFY=0` turns it off). It posts once per commit and set of receipts, never repeats on a republish, reopen, retry or restart, mentions at most 10 people, and sends at most 20 such comments per repository per hour. A failed comment never breaks the check. Tested against fakes; **not yet seen on real GitHub.**
   **Policy refresh:** on a push to the default branch the service compares the policy file's content with the one the last published decision used; if it differs, every open pull request that has a receipt is re-evaluated and its check republished (50 at once, the rest by the background loop). It compares content, not the push payload's list of files, so a truncated payload cannot hide a change. Needs the App subscribed to the Push event; an unreadable policy changes nothing and fails the delivery. Tested against fakes; **not yet seen on real GitHub.**
2. `POST /v1/webhook` (GitHub App webhook, HMAC-verified; events Pull request, Issue comment and, recommended, **Push**): on pull-request events it creates a pending check (so a required check cannot be satisfied by silence); on a pull-request comment `/agentvow acknowledge` it requires the receipt id (`/agentvow acknowledge <id>`), a person who is a listed acknowledger **and** has write access (and, unless they own the repository account, is not the pull request's author), stores the acknowledgement against the current receipt id, re-evaluates and updates the check.
3. `GET /v1/check`, `GET /v1/audit?format=json|csv`: per-repository key (Bearer); a key for one repository never reads another's records.
4. Operator CLI: `python -m controlplane.service.cli --db PATH set-plan|issue-key|purge|usage`.

Fail-closed rules: an unreadable or invalid base-branch policy blocks; GitHub errors return 5xx and set nothing; the conclusions used are only success, failure, action_required (never neutral or skipped, which would pass a required check); a CONTRADICTED claim cannot be acknowledged away.

## GitHub App to register (owner)
Permissions: Checks read/write, Contents read, Pull requests write, Issues write (comments), Metadata read. Events: Pull request, Issue comment. Webhook URL `https://<host>/v1/webhook`, with a secret. Then protect the target branch with a required status check named `agentvow/evidence` and choose this App as its **source** (with source "any", a writer's own `GITHUB_TOKEN` can post a green check of that name).

## Environment variables
`AGENTVOW_CP_APP_ID`, `AGENTVOW_CP_PRIVATE_KEY_FILE` (path to the PEM; preferred) or `AGENTVOW_CP_PRIVATE_KEY` (PEM, `\n` allowed), `AGENTVOW_CP_WEBHOOK_SECRET`, `AGENTVOW_CP_AUDIENCE` (the audience the gate workflow requests), `AGENTVOW_CP_TRUSTED_WORKFLOWS` (comma-separated exact `job_workflow_ref` values, each ending in a full 40-character sha; `AGENTVOW_CP_ALLOW_MUTABLE_REFS=1` is for development only), `AGENTVOW_CP_DB` (default `/data/controlplane.db`). The process refuses to start if one is missing (`uvicorn --factory`).

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
