# Adversarial review of the phase-1 control plane (2026-10-22)

Reviewer: an independent agent instructed to falsify the service (CLAUDE.md: adversarial review before a milestone). It read the code and docs, wrote proof-of-concept scripts against the service with fakes, and classed each finding CONFIRMED (reproduced), PLAUSIBLE (reasoned) or REFUTED. Verdict on the version reviewed (commit 2c48609): **not safe**. All findings below were fixed in the commit that adds this file; each has a regression test in `tests/test_cp_service.py::Findings`.

| ID | Class | Finding | Fix |
|---|---|---|---|
| A | CONFIRMED, critical | The OIDC token was not bound to the receipt; a pull request could point `service-url` at its own server, collect a valid token and replay it with a forged receipt | Token audience is `<audience>:<sha256 of the receipt>`; the service verifies it against the body. The token's `ref` (pull request) or `sha` (push) must match the receipt; `repository_id` is required and bound to the name |
| B | CONFIRMED, critical | Policy was read from the pull request's base branch, which its author chooses; a second pull request into a weak branch turned the shared check green | Policy is read from the default branch only |
| C | CONFIRMED, high | The check showed the last receipt to arrive, not the latest workflow run | The published result is always that of the latest run; a re-posted receipt keeps the highest run order |
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

## Residuals (not fixed, stated)
* A sandbox escape inside the replay job can still forge a receipt that carries a valid token (the replay job has no token, but its output is what the upload job sends).
* Write permission of an acknowledger is checked when the comment is processed, not again on every later evaluation.
* No hash-pinned dependencies or base-image digest; no per-request read timeouts beyond uvicorn's keep-alive limit.
* Everything is still verified only against fakes; the claims `ref`, `sha`, `repository_id` and the audience format are assumptions about GitHub's tokens until a live run.
