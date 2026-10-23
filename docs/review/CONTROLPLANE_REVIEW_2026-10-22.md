# Adversarial review of the phase-1 control plane (2026-10-22)

Reviewer: an independent agent instructed to falsify the service (CLAUDE.md: adversarial review before a milestone). It read the code and docs, wrote proof-of-concept scripts against the service with fakes, and classed each finding CONFIRMED (reproduced), PLAUSIBLE (reasoned) or REFUTED. Verdict on the version reviewed (commit 2c48609): **not safe**. All findings below were fixed in the commit that adds this file; each has a regression test in `tests/test_cp_service.py::Findings`.

| ID | Class | Finding | Fix |
|---|---|---|---|
| A | CONFIRMED, critical | The OIDC token was not bound to the receipt; a pull request could point `service-url` at its own server, collect a valid token and replay it with a forged receipt | Token audience is `<audience>:<sha256 of the receipt>`; the service verifies it against the body. The token's `ref` (pull request) or `sha` (push) must match the receipt; `repository_id` is required and bound to the name |
| B | CONFIRMED, critical | Policy was read from the pull request's base branch, which its author chooses; a second pull request into a weak branch turned the shared check green | Policy is read from the default branch only |
| C | CONFIRMED, high | The check showed the last receipt to arrive, not the latest workflow run | Receipts are ranked by run; a re-posted receipt keeps its highest run order. (Second review: see 2-1 below for the cross-event gap)|
| D | CONFIRMED, high | The ASGI entry point was a plain function: every request failed under uvicorn; missing configuration failed per request, not at start-up | `create_app` factory (`uvicorn --factory`), built eagerly; test loads it through uvicorn |
| E | PLAUSIBLE, high | The receipt passes from the replay job to the upload job through the artifact store | The replay job's output carries the receipt hash; the upload job refuses a changed file; the hash is also in the token audience. Residual: a forgery from inside the replay job itself is not prevented |
| F | CONFIRMED, medium | `commit` and `git_tree` were not validated; a crafted value reached a GitHub API path | Full hexadecimal ids and `owner/name` are enforced in the receipt schema, in the service and in the GitHub client |
| G1 | PLAUSIBLE, medium | A 404 on the policy ref (deleted branch) was read as "no policy" | The default branch is resolved to a commit first; failure to resolve blocks |
| G2 | CONFIRMED, low | Directory at the policy path and non-ASCII signatures raised unhandled errors | Typed checks, byte comparison, and any unexpected exception sets the check to failure |
| H | CONFIRMED, medium | Concurrent first publishes created two check runs | One publisher at a time per (repository, commit) |
| I | CONFIRMED, medium | A reopened pull request reset a finished check to pending | An existing receipt is re-evaluated instead |
| J | CONFIRMED, medium | `/agentvow acknowledge` without an id bound to the newest receipt; replayable; the author could acknowledge their own pull request | The receipt id is required; webhook delivery ids are refused a second time; the pull request's author cannot acknowledge unless they own the repository account |
| K | CONFIRMED, low-medium | Quota counting was not atomic and refusals kept counting | Store-and-count in one transaction; refusals count nothing |
| L | PLAUSIBLE, low-medium | Unbounded rate-limiter memory; JWKS outage retried on every request; audit fetched the policy per receipt; no early body limit | Bounded limiter, locked refresh with negative caching, policy fetched once per export (decisions are labelled "under the current policy"), body limit before token verification and from Content-Length |
| M | CONFIRMED, low | `set-plan --days 0` was permanent; names, not ids, keyed plans; `issue-key` overwrote | `--days` must be 1 or more; repository id bound to the name; `--rotate` required to replace a key |

Documentation overclaims corrected: threat-model rows 1, 2, 3 and 5, the "start-up fails" statement, and a warning that branch protection must name the App as the check's source.

## Follow-up after the first fixes
The caller-chosen `service-url` was pinned: it may only select an address written into `gate.yml` (`ALLOWED_SERVICE_URLS`, exact match, checked before a token is requested). The hosted address is a placeholder until one is assigned.

## Second review (commits f9cd5dc and 64bcf7c) and its fixes
A second independent reviewer attacked the fixes and mutation-checked the regression tests (18 killed their mutation; 7 survived, listed below and strengthened).

| ID | Class | Finding | Fix |
|---|---|---|---|
| 2-1 | CONFIRMED, high | A later push or dispatch run (no claims, no pull request) of the same commit superseded a pull request run's CONTRADICTED receipt; with `no_claims: allow` the check turned green | Receipts record the triggering event; the check shows the WORST decision among the latest receipt of each event kind |
| 2-2 | CONFIRMED, medium-high | Read, evaluate and publish were not one step; a slow acknowledgement published a stale `success` over a newer result | Read, decide and publish happen under one per-(repository, commit) lock |
| 2-3 | CONFIRMED, medium | A receipt stored but not published (GitHub 5xx) left an older green check | The commit is marked dirty and re-published by `reconcile()` on every receipt and webhook and by a 60-second loop |
| 2-4 | CONFIRMED, medium | The published check can drift from the current policy; the audit listed acknowledgements the policy does not count | `/v1/check` says it is "under the policy in force now"; the audit lists only counted acknowledgements. Not fixed: re-publishing open pull requests when the policy file changes (needs push-event subscriptions) |
| 2-5 | CONFIRMED, medium | Webhook delivery id recorded before processing; a failed delivery's redelivery was dropped | Recorded only after success |
| 2-6 | CONFIRMED, low-medium | `repository_id` was bound before the trust checks, so an untrusted token could claim a name; no way to undo | Bound after all trust checks and the rate limit; operator `unbind-repo` |
| 2-7 | CONFIRMED, low | More than 200 claims made a legitimate receipt unacceptable; a undecodable policy file raised untyped errors | `build_receipt` keeps the worst claims and adds an UNKNOWN "truncated" claim; decode errors are typed |
| 2-8 | PLAUSIBLE, medium | Branch names with a slash were percent-encoded in the ref lookup | Slashes kept; unverified against GitHub |
| 2-9 | note | `env` context inside a called workflow is an assumption | The redundant `${{ env... }}` lines were removed; the value is read from the workflow-level `env` |

Weak regression tests found by mutation and fixed: empty `repository_id`, schema-level hex strictness, the real `branch_sha` error path, acknowledgement refusals (each now fires for its own reason), an acknowledgement of another receipt, a contradiction that an acknowledgement cannot clear, and the stale-publish race.

## Third review (commits after e102798: lifecycle, retention, dashboard, helpers, image) and its fixes
A third independent reviewer attacked the code added after the live run and mutation-checked its tests (19 mutations; 5 survivors, strengthened).

| ID | Class | Finding | Fix |
|---|---|---|---|
| 3-C1 | CONFIRMED, high | When a paid plan ended (a late invoice, a typo in `--days`) the next daily run deleted every receipt older than the free plan's 30 days | Retention follows the best plan the repository or owner ever had; a lapse never deletes (data leaves by retention while paid, by `erase`, or after uninstall) |
| 3-C2 | CONFIRMED, medium | An exception ended the background thread (and the retry of unpublished checks); maintenance first ran 24 hours after every start | `background_pass`: each step isolated and logged; the last maintenance time is persisted, so restarts do not postpone it |
| 3-C3 | CONFIRMED, medium | Erasure followed webhook order: a stale "removed" event could mark a live repository for erasure; a repository whose "created" event was missed was never erased | Erasure asks GitHub (`GET /repos/{r}/installation`): 404 for longer than the grace period erases, 200 resets, anything else changes nothing; removal events are scoped by installation id; an installation can only name its own account's repositories |
| 3-C4 | CONFIRMED, low-medium | Plan keys were case-sensitive (`set-plan Acme` did not cover `acme/x`) | Plan keys are lower-cased |
| 3-C5 | CONFIRMED, low | `deliveries` grew forever; an open pull request older than the retention loses its receipt (the check then shows pending, fail closed) | Deliveries pruned daily; the open-pull-request case documented. `checks` rows (a few bytes each) still only leave with `erase` |
| 3-C6 | CONFIRMED, medium | A local `docker compose up --build` copied the git-ignored `secrets/` directory into the image | `.dockerignore` (allow-list: only `agentvow` and `controlplane`, never `secrets`); verified by building with a dummy secret; the image workflow also checks it |
| 3-C7 | CONFIRMED, low | Glob characters in untracked `.agentvow/` file names (`*`, `p?licy.json`) removed the tracked policy from the hash | Literal pathspecs for that step |
| 3-P1 | PLAUSIBLE | Dashboard and audit had no cap or rate limit (one large tenant could stall the single worker and spend API quota) | Dashboard shows the latest 500 receipts; audit and dashboard are rate limited like uploads |
| 3-P2/P3 | PLAUSIBLE | The registration helper accepted any Host header (DNS rebinding), followed links and kept the modes of existing files | Host allow-list, files replaced (never written through), directory mode forced, `--repo` validated |
| 3-P4 | PLAUSIBLE | The image smoke test never started the app; `:latest` floated | The workflow starts the container with a generated key and checks `/healthz` and the absence of `secrets`; only the version tag is pushed |
| 3-P5/P6 | PLAUSIBLE | Erase was not atomic; no frame protection on the dashboard | One transaction; `frame-ancestors 'none'` and `X-Frame-Options: DENY` |

Weak tests found by mutation and fixed: erase touching every table, retention removing acknowledgements, the dashboard's security headers, the helper's file modes with pre-existing files; missing tests added for plan lapse, the loop, out-of-order events, glob names.

Not fixed, stated: deleted rows stay in SQLite's free pages and in older backups; compose file-secrets keep the host's ownership, so on Linux the secrets directory must be readable by uid 10001 (documented, not shown to work on Linux); the base image and transitive dependencies float.

## Residuals (not fixed, stated)
* A sandbox escape inside the replay job can still forge a receipt that carries a valid token (the replay job has no token, but its output is what the upload job sends).
* Write permission of an acknowledger is checked when the comment is processed, not again on every later evaluation.
* No hash-pinned dependencies or base-image digest; no per-request read timeouts beyond uvicorn's keep-alive limit.
* A malformed receipt (422) from a verified token cannot be attached to a check run because the commit is not trusted at that point; the gate job reports the service decision as an error, which the workflow treats as block.
* Everything is still verified only against fakes; the claims `ref`, `sha`, `repository_id` and the audience format are assumptions about GitHub's tokens until a live run.
