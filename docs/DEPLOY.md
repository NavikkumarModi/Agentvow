# Deploying the control plane service

Status: the image builds and runs (read-only filesystem, non-root, all capabilities dropped) and answers `/healthz` and `/dashboard`; the service has run against real GitHub from a laptop behind a tunnel (`docs/LIVE_TESTING.md`). **It has never run on a hosted machine with a real domain.** Everything below is a recipe, not a record.

## What you need (accounts are yours)
* A machine or container host that can run one container with a persistent volume (a small VM is enough: the service is a single process with SQLite; receipts are small).
* A domain name and TLS in front (Caddy or nginx on the same host, a cloud load balancer, or a Cloudflare named tunnel). The service speaks plain HTTP on port 8080.
* A GitHub **organisation** that owns the production App (needed later for any Marketplace listing: only organisation-owned apps can be sold). Register it with `controlplane/service/register_app.py --tunnel https://<your domain> --repo <owner>/<a test repo> --out secrets` or by hand (`docs/SETUP_GITHUB_APP.md`; permissions: Checks write, Contents read, Pull requests write, Issues write, Metadata read; events: Pull request, Issue comment; GitHub delivers the `installation` and `installation_repositories` events to an App's webhook without a subscription, which the live test did not exercise: unverified).

## One host with Docker Compose
```bash
cd controlplane/service && mkdir -p secrets && chmod 700 secrets
cp /path/to/app.private-key.pem secrets/ && printf '%s' "$WEBHOOK_SECRET" > secrets/webhook_secret && chmod 600 secrets/*
export AGENTVOW_CP_APP_ID=<id>
export AGENTVOW_CP_TRUSTED_WORKFLOWS='<owner>/<repo>/.github/workflows/gate.yml@refs/tags/v1'   # exact job_workflow_ref values, comma separated
docker compose up -d --build
curl -s http://127.0.0.1:8080/healthz        # ok
```
Or use the image the `service-image` workflow publishes when you push a tag `service-v0.1.0` (`ghcr.io/<owner>/agentvow-controlplane`). The container needs: `AGENTVOW_CP_APP_ID`, `AGENTVOW_CP_PRIVATE_KEY_FILE`, `AGENTVOW_CP_WEBHOOK_SECRET_FILE`, `AGENTVOW_CP_AUDIENCE`, `AGENTVOW_CP_TRUSTED_WORKFLOWS`, `AGENTVOW_CP_POLICY_PATH` (optional), `AGENTVOW_CP_DB` (on a volume). It refuses to start if a required value is missing.

Then set the App's webhook URL to `https://<your domain>/v1/webhook` and, in the copy of `gate.yml` your customers call, `ALLOWED_SERVICE_URLS` to `https://<your domain>`.

## Operating it
* **Plans and keys** (run inside the container or on the volume): `python -m controlplane.service.cli --db /data/controlplane.db set-plan <owner or owner/repo> team --days 365`, `issue-key owner/repo` (shown once), `stats`, `usage owner/repo`.
* **Backups:** `cli backup /data/backup-$(date +%F).db` is a consistent online copy (mode 600); run it daily from cron and copy it off the host (encrypt it: receipts name repositories and file categories). Restore = stop the service, put the file at `/data/controlplane.db`, start.
* **Retention and erasure:** the service deletes receipts older than the plan's retention (free 30 days, team 365, business 730) and erases everything stored about a repository 30 days after the App is uninstalled from it; both run daily in-process (`cli maintain` runs them by hand; `cli erase owner/repo` deletes on request, for example for a data-subject request).
* **Logs:** every non-2xx answer logs its reason (never a token or receipt body). `/healthz` for monitoring. There are no metrics yet.
* **Upgrades:** pull the new image, restart; the schema is created on start (`create table if not exists`); there is no migration tool yet, so back up first and read the changelog.
* **Secrets rotation:** generate a new App private key in the App settings, replace the file, restart, delete the old key; rotate the webhook secret in the App settings and the secrets file together.

## Limits of this recipe
One process, one disk, no high availability; SQLite does not scale to many writers (fine for tens of repositories, revisit before hundreds); no metrics or alerting; no migration tool; dependencies are pinned to exact versions but not by hash; the base image is a floating `python:3.12-slim`. A privacy policy, terms and a data-processing statement are needed before any customer sends receipts (they contain repository names and file and variable category names).
