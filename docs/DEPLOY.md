# Deploying the control plane service

Status (2026-10-26): the image builds and runs (read-only filesystem, non-root, all capabilities dropped) and answers `/healthz` and `/dashboard`; the service has run against real GitHub from a laptop behind a tunnel (`docs/LIVE_TESTING.md`). **It has never run on a hosted machine with a real domain.** Everything below is a recipe, not a record.

## What you need (accounts are yours)
* A machine or container host that can run one container with a persistent volume (a small VM is enough: the service is a single process with SQLite; receipts are small).
* A domain name and TLS in front (Caddy or nginx on the same host, a cloud load balancer, or a Cloudflare named tunnel). The service speaks plain HTTP on port 8080.
* A GitHub **organisation** that owns the production App (needed later for any Marketplace listing: only organisation-owned apps can be sold). Register it with `controlplane/service/register_app.py --tunnel https://<your domain> --repo <owner>/<a test repo> --out secrets` or by hand (`docs/SETUP_GITHUB_APP.md`; permissions: Checks write, Contents read, Pull requests write, Issues write, Metadata read; events: Pull request, Issue comment; GitHub delivers the `installation` and `installation_repositories` events to an App's webhook without a subscription, which the live test did not exercise: unverified).

## First deployment on one VM, step by step (written 2026-10-26; **not yet followed by anyone**: expect the first hosted run to expose a defect, and record it in `docs/LIVE_TESTING.md`)
### Decide first
1. **The GitHub organisation** that will own the production App (only organisation-owned apps can be sold on Marketplace; moving an App later is a transfer).
2. **Domain and host:** a small Linux VM at any provider (cost is a few dollars to about ten per month: an estimate, not checked) and a domain you control, for example `gate.<yourdomain>`.
3. **Where the trusted workflow lives.** The service trusts exactly one `gate-service.yml` at one commit sha. Simplest: keep it in the public Agentvow repository, put your real address in its `ALLOWED_SERVICE_URLS`, commit, and use that commit's sha everywhere.
4. **The licence of `controlplane/`** (`docs/strategy/MONETISATION_UPDATE_2026-10-23.md` section 4); not needed to deploy, needed before customers.

### Steps
1. **Register the App under the organisation** (`docs/SETUP_GITHUB_APP.md` section 3, or the manifest helper: `python -m controlplane.service.register_app --tunnel https://gate.<yourdomain> --repo <owner>/<test repo> --out ./secrets`, run on YOUR machine with a browser signed in to GitHub; leave `--workflow-sha` out, it is not known yet). The helper writes `secrets/app.private-key.pem` and `secrets/webhook_secret` (what compose mounts) and a `cp.env` for running the service directly on that machine (not used with compose) and prints the App id; the webhook URL is set to `https://gate.<yourdomain>/v1/webhook` by the manifest. Permissions: Checks write, Contents read, Pull requests write, Issues write, Metadata read; events: Pull request, Issue comment. Install it on one test repository first. GitHub asks for a passkey or code when you change App settings; that confirmation is yours.
2. **Prepare the VM:** SSH keys only (no password login); firewall open on ports 22, 80 and 443 only; automatic security updates; Docker with the Compose plugin; an A record for `gate.<yourdomain>` pointing at the VM.
3. **Put TLS in front.** The service speaks plain HTTP and the compose file binds it to `127.0.0.1:8080`. Caddy on the same host needs only:
   ```
   gate.<yourdomain> {
       reverse_proxy 127.0.0.1:8080
   }
   ```
   (Caddy gets and renews the certificate itself; nginx with certbot or a Cloudflare named tunnel work too.)
4. **Get the code and the secrets onto the host:**
   ```bash
   git clone https://github.com/NavikkumarModi/Agentvow && cd Agentvow/controlplane/service
   mkdir -p secrets && chmod 700 secrets
   # copy secrets/app.private-key.pem and secrets/webhook_secret to the host with scp (not the cp.env), then:
   sudo chown -R 10001 secrets && sudo chmod 700 secrets && sudo chmod 400 secrets/*   # the container user is uid 10001; every command needs sudo once the files belong to it; not verified on a real Linux host (the image workflow's smoke test hit exactly this permission problem once)
   ```
5. **Set the trusted workflow and start** (put the exports in a root-only env file, not your shell history):
   ```bash
   export AGENTVOW_CP_APP_ID=<id>
   export AGENTVOW_CP_TRUSTED_WORKFLOWS='NavikkumarModi/Agentvow/.github/workflows/gate-service.yml@<40-character sha>'
   docker compose up -d --build
   curl -s http://127.0.0.1:8080/healthz          # ok
   curl -s https://gate.<yourdomain>/healthz      # ok, through Caddy
   ```
   The service refuses to start if a variable is missing or the trusted value is not a full sha.
6. **Check the configuration against real GitHub:** `docker compose exec controlplane python -m controlplane.service.smoke` should end with "OK: the App has what the service needs." (It prints the App's permissions and events and names anything missing.)
7. **Pin the sha in the workflow your customers call.** In `gate-service.yml` set `ALLOWED_SERVICE_URLS` to `https://gate.<yourdomain>`, commit it to the public repository, and use that commit's sha in the service's trusted value and in every caller's `uses:`. A later change to the workflow means a new sha, updated in both places together.
8. **Run the acceptance tests on the real host** (`docs/SETUP_GITHUB_APP.md` section 8, with the production App and a sha-pinned caller; tests 1 to 4, 7, 8 and 10 matter most) and write the result in `docs/LIVE_TESTING.md`.
9. **Make the check required:** branch protection on the target branch requires `agentvow/evidence` with the App chosen as its **source**. With source "any", a writer's own `GITHUB_TOKEN` can post a green check of that name (seen live: it did not count when the source was pinned).
10. **Backups and routine operation** (below): a daily `backup` from cron, with the copy taken off the host (`docker compose cp controlplane:/data/backup-<date>.db .`, then encrypt and move it; the file is mode 600 owned by uid 10001 inside the volume); `stats`; plans set by hand with `set-plan`; keys issued with `issue-key`. `AGENTVOW_CP_MIN_TOOL_VERSION` (default 0.4.3) refuses receipts made by an older Agentvow. `AGENTVOW_CP_NOTIFY=0` turns off the pull request comment that mentions the listed acknowledgers when a change needs an acknowledgement.

### Before any customer's receipts arrive
A privacy policy, terms and a data-processing statement from a lawyer. Receipts hold repository names and category names of what could not be reproduced, not source code, but that is still customer metadata.

### Who does what
You: the organisation, domain, VM, DNS, secrets and the passkey confirmations. The assistant: the workflow edit with your address, the sha bookkeeping, the acceptance run and its record, and the fixes the first hosted run exposes.

## One host with Docker Compose (reference)
```bash
cd controlplane/service && mkdir -p secrets && chmod 700 secrets
cp /path/to/app.private-key.pem secrets/ && printf '%s' "$WEBHOOK_SECRET" > secrets/webhook_secret
sudo chown -R 10001 secrets && sudo chmod 700 secrets && sudo chmod 400 secrets/*   # the container user is uid 10001; unverified on Linux hosts
export AGENTVOW_CP_APP_ID=<id>
export AGENTVOW_CP_TRUSTED_WORKFLOWS='<owner>/<repo>/.github/workflows/gate-service.yml@<40-character commit sha>'   # exact job_workflow_ref values, comma separated, each pinned to a full sha (the service refuses to start with a tag or branch)
docker compose up -d --build
curl -s http://127.0.0.1:8080/healthz        # ok
```
Or use the image the `service-image` workflow publishes when you push a tag `service-v0.1.0` (`ghcr.io/<owner>/agentvow-controlplane`). The container needs: `AGENTVOW_CP_APP_ID`, `AGENTVOW_CP_PRIVATE_KEY_FILE`, `AGENTVOW_CP_WEBHOOK_SECRET_FILE`, `AGENTVOW_CP_AUDIENCE`, `AGENTVOW_CP_TRUSTED_WORKFLOWS`, `AGENTVOW_CP_POLICY_PATH` (optional), `AGENTVOW_CP_DB` (on a volume). It refuses to start if a required value is missing.

Then set the App's webhook URL to `https://<your domain>/v1/webhook` and, in the copy of `gate-service.yml` your customers call, `ALLOWED_SERVICE_URLS` to `https://<your domain>`.

## Operating it
* **Plans and keys** (run inside the container or on the volume): `python -m controlplane.service.cli --db /data/controlplane.db set-plan <owner or owner/repo> team --days 365`, `issue-key owner/repo` (shown once), `stats`, `usage owner/repo`.
* **Backups:** `cli backup /data/backup-$(date +%F).db` is a consistent online copy (mode 600); run it daily from cron and copy it off the host (encrypt it: receipts name repositories and file categories). Restore = stop the service, put the file at `/data/controlplane.db`, start.
* **Retention and erasure:** once a day (and at start if more than a day has passed) the service deletes receipts older than the retention of the best plan the repository or its owner ever had (free 30 days, team 365, business 730; **a lapsed plan never deletes anything**), and, for every repository with stored data, asks GitHub whether the App is still installed: 404 for more than 30 days erases everything stored about the repository (receipts, acknowledgements, key, plan, counters); an unknown answer changes nothing. `cli maintain` runs it by hand (with the service's environment loaded, otherwise only retention runs); `cli erase owner/repo` deletes on request. Deleted rows remain in SQLite's free space and in earlier backups until overwritten.
* **Logs:** every non-2xx answer logs its reason (never a token or receipt body). `/healthz` for monitoring. There are no metrics yet.
* **Upgrades:** pull the new image, restart; the schema is created on start (`create table if not exists`); there is no migration tool yet, so back up first and read the changelog.
* **Secrets rotation:** generate a new App private key in the App settings, replace the file, restart, delete the old key; rotate the webhook secret in the App settings and the secrets file together.

## Build context
`.dockerignore` allows only `agentvow/` and `controlplane/` into the image and always excludes `secrets/`; CI checks this on every build.

## Limits of this recipe
One process, one disk, no high availability; SQLite does not scale to many writers (fine for tens of repositories, revisit before hundreds); no metrics or alerting; no migration tool; dependencies are pinned to exact versions but not by hash; the base image is a floating `python:3.12-slim`. A privacy policy, terms and a data-processing statement are needed before any customer sends receipts (they contain repository names and file and variable category names).
