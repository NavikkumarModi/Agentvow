# Set up the Agentvow GitHub App and run the live test

Goal: register a GitHub App, run the control plane service on your own machine, point a throwaway repository at it, and confirm (or refute) the assumptions listed in `docs/CONTROLPLANE_PHASE1.md` under "Not verified". Time: about 60 to 90 minutes. Cost: nothing (a free GitHub account, a free tunnel). Everything below was written from GitHub's documentation (read 2026-10-23) and **has not been run by anyone yet**: if a screen differs from these words, trust the screen and tell me what it said.

Rules for this test: use a **throwaway public repository**, never a real project; the App's private key is a password, so keep it outside every repository; stop the service and delete the key when you are done (section 10).

## 0. What you need
* A GitHub account (personal is fine) and a browser signed in to it.
* Python 3.10+ and this repository checked out. Install the service's dependencies: `pip install -r controlplane/service/requirements.txt`.
* A tunnel that gives your laptop a public https address. Easiest: Cloudflare quick tunnels, no account: `brew install cloudflared`. (Alternative: ngrok.)

## 1. Create the throwaway repository
On GitHub: **New repository** → name `agentvow-live-test` → **Public** (the free plan refuses private repositories) → add a README → **Create**. Then clone it and add a tiny Python project:
```bash
git clone https://github.com/<you>/agentvow-live-test && cd agentvow-live-test
printf 'def f():\n    return 1\n' > lib.py
mkdir tests && touch tests/__init__.py
printf 'import unittest\nfrom lib import f\n\nclass T(unittest.TestCase):\n    def test_f(self):\n        self.assertEqual(f(), 1)\n' > tests/test_lib.py
printf '.agentvow/\n' > .gitignore
git add -A && git commit -m "tiny project" && git push
```

## 2. Start the tunnel first (you need its address for the App)
In a terminal that stays open:
```bash
cloudflared tunnel --url http://localhost:8080
```
It prints an address like `https://random-words.trycloudflare.com`. **Write it down**; this is `<TUNNEL>` below. It changes every time you restart cloudflared, so do not restart it during the test (if you must, see Troubleshooting).

## 3. Register the GitHub App
1. Click your profile picture (top right) → **Settings** → at the bottom of the left sidebar **Developer settings** → **GitHub Apps** → **New GitHub App**.
2. Fill in:

| Field | Value |
|---|---|
| GitHub App name | `agentvow-<your-user>-test` (34 characters or fewer, unique on GitHub) |
| Homepage URL | your test repository's URL |
| Callback URL, Setup URL | leave empty |
| Expire user authorization tokens | leave as is (unused) |
| Request user authorization (OAuth) during installation | **unchecked** |
| Enable Device Flow | **unchecked** |
| Webhook → **Active** | checked |
| Webhook URL | `<TUNNEL>/v1/webhook` |
| Webhook secret | the output of `openssl rand -hex 32`; **save it**, you need it in step 5 |
| SSL verification | **Enable** |

3. **Repository permissions** (leave every other permission at *No access*; account and organization permissions all *No access*):

| Permission | Access | Why |
|---|---|---|
| Checks | Read and write | create and update the `agentvow/evidence` check run |
| Contents | Read-only | read the policy file and resolve commits and branches |
| Issues | Read and write | post the acknowledgement replies (pull-request comments go through the issues API) |
| Pull requests | Read-only | read a pull request's head commit and author |
| Metadata | Read-only | selected automatically |

4. **Subscribe to events**: tick **Pull request** and **Issue comment** (the boxes appear after you grant the permissions above).
5. **Where can this GitHub App be installed?** → **Only on this account**.
6. **Create GitHub App**.
7. On the page that opens: note the **App ID** (a number near the top, in the "About" box). Scroll to **Private keys** → **Generate a private key**. A `.pem` file downloads. Move it out of Downloads to a private place and lock it:
```bash
mv ~/Downloads/agentvow-*.private-key.pem ~/agentvow-app.private-key.pem && chmod 600 ~/agentvow-app.private-key.pem
```

## 4. Install the App on the test repository only
Settings → Developer settings → GitHub Apps → **Edit** next to your App → **Install App** → **Install** next to your account → **Only select repositories** → choose `agentvow-live-test` → **Install**.

## 5. Configure and check the service
```bash
cp controlplane/service/env.example ~/agentvow-cp.env      # edit it: App ID, key path, webhook secret, trusted workflow, DB path
set -a; . ~/agentvow-cp.env; set +a
python -m controlplane.service.smoke
```
`smoke` signs a JWT with your key and asks GitHub who the App is. Expected last line: `OK: the App has what the service needs.` If it prints PROBLEM lines, fix the App's permissions or events (Settings → your App → Permissions & events; an installed App asks you to approve changed permissions on its installation page) and run it again. `CONFIG:` means an environment variable is missing; `GitHub refused…` means a wrong App ID or key.

`AGENTVOW_CP_TRUSTED_WORKFLOWS` must be, exactly, `<you>/agentvow-live-test/.github/workflows/gate.yml@refs/tags/v1` (this is the value you will confirm in step 8).

Start the service (second terminal, from the Agentvow checkout, with the environment loaded):
```bash
python -m uvicorn --factory controlplane.service.asgi:create_app --host 127.0.0.1 --port 8080
curl -s <TUNNEL>/healthz        # prints: ok
```
It refuses to start if a variable is missing. Warnings (every non-2xx answer, with its reason, never a token) print in this terminal: **this is your main instrument during the test.**

Check the webhook path: GitHub App settings → **Advanced** → **Recent Deliveries**. After the first pull request event you should see deliveries with a green tick (HTTP 200). A red entry shows GitHub's request and our answer; use **Redeliver** to retry.

## 6. Put the gate workflow in the test repository
The reusable workflow lives in the test repository itself for this test (a public copy of the vendor workflow is what you would use in production). In `agentvow-live-test`:
```bash
mkdir -p .github/workflows .agentvow
cp <path-to-Agentvow>/.github/workflows/gate.yml .github/workflows/gate.yml
```
Edit `.github/workflows/gate.yml`: change the line `ALLOWED_SERVICE_URLS: "https://controlplane.agentvow.example"` to `ALLOWED_SERVICE_URLS: "<TUNNEL>"` (no trailing slash). Create the caller `.github/workflows/agentvow-pr.yml`:
```yaml
name: agentvow
on: pull_request
permissions:
  contents: read
  id-token: write
jobs:
  gate:
    uses: <you>/agentvow-live-test/.github/workflows/gate.yml@v1
    with:
      service-url: <TUNNEL>
      audience: agentvow-control-plane
      fail-on: block
```
Add a policy on the default branch that lets you acknowledge, `.agentvow/policy.json`:
```json
{"schema": "agentvow-policy/1", "acknowledgers": ["<you>"]}
```
Commit to `main`, push, then tag the workflow and push the tag (the pin the service trusts):
```bash
git add -A && git commit -m "gate workflow, caller, policy" && git push
git tag v1 && git push origin v1
```
Because the workflow is called by its tag, **edits to `gate.yml` take effect only after you move the tag** (`git tag -f v1 && git push -f origin v1`).

## 7. Branch protection (do this after the first check run exists)
Settings → **Branches** → **Add branch ruleset** or classic **Add rule** for `main` → require status checks to pass → search for `agentvow/evidence` (it appears only after the App has created it once; do step 8 test 1 first, then come back) → add it and, where GitHub shows a **source** choice next to the check, choose **your App** (not "any source"; with "any source" any workflow's `GITHUB_TOKEN` could post a check with that name).

## 8. The acceptance tests
Open each pull request from a branch of the test repository. For every test write down: what you saw on the pull request, the service terminal lines, and the Actions log. **Never paste the OIDC token, the private key or the webhook secret.** Redact the tunnel address if you wish.

| # | Do | Expect | Confirms |
|---|---|---|---|
| 1 | Open a pull request that adds a function `g` and says "I added g. All tests pass." | A check `agentvow/evidence` appears as in progress at once, then **success** after the gate run. Service log: no warnings. | webhook delivery and signature; App can create and update checks; the OIDC `job_workflow_ref` equals your configured value (if not: log says "exact trusted gate workflow"); `ref` = `refs/pull/N/merge`, `repository_id` present, custom audience accepted |
| 2 | Open a pull request with the message "All 9 tests pass." | check **action_required** (UNKNOWN claim) | verdict and policy path |
| 3 | On test 2's pull request comment `/agentvow acknowledge` | the App replies with the receipt id to use; then comment `/agentvow acknowledge <id>` → check turns **success**, the App replies "acknowledged" | comment webhook; write-permission lookup; owner exception for the author rule |
| 4 | Open a pull request that breaks `f` (return 2) and says "All tests pass." | check **failure**; acknowledging it is refused or has no effect | contradiction cannot be acknowledged |
| 5 | In the caller, set `service-url: https://example.com` on a branch and open a pull request | the upload job reports it is not an allowed address; **no token is requested**; the check stays pending (fail closed) | the service-URL pin |
| 6 | Remove `id-token: write` from the caller on a branch | upload says no OIDC token is available; check stays pending | behaviour without the permission (still blocks) |
| 7 | Change `.agentvow/policy.json` inside a pull request to `{"schema":"agentvow-policy/1","unknown":"allow"}` and also send a wrong claim | the pull request's policy is **ignored** (check stays action_required) | default-branch policy |
| 8 | Re-run the gate workflow from the Actions tab ("Re-run all jobs") | still one check run, same result | latest-run logic, one check run |
| 9 | If you have a second GitHub account: fork the repository and open a pull request from the fork | record what happens (GitHub normally gives fork workflows no OIDC permission; the check should stay pending) | fork behaviour (currently unverified) |
| 10 | `python -m controlplane.service.cli --db <DB> issue-key <you>/agentvow-live-test`, then `curl -H "Authorization: Bearer <key>" "<TUNNEL>/v1/audit?repo=<you>/agentvow-live-test"` | JSON of every receipt with its decision; a wrong key gives 401 | audit export, tenant key |

If test 1 does not pass, do not continue: send me the service terminal output and the failing step's log.

## 9. Troubleshooting
| Symptom | Likely cause |
|---|---|
| `smoke`: GitHub refused the App credentials | wrong App ID, or the key file is not the one generated for this App |
| Service log: `exact trusted gate workflow` | `AGENTVOW_CP_TRUSTED_WORKFLOWS` differs from the real `job_workflow_ref`; the log of the Actions run (or a debug step that decodes the token payload, never the signature, for you only) shows the real value; fix the variable, restart the service |
| `token refused: wrong audience` | the caller's `audience` input differs from `AGENTVOW_CP_AUDIENCE`, or GitHub ignored the custom audience (then tell me: that assumption is false) |
| `the token's pull request is not the receipt's` | `ref` claim is not `refs/pull/N/merge`; tell me the real value |
| `this repository name belongs to a different repository` | you recreated the repository under the same name; run `python -m controlplane.service.cli --db <DB> unbind-repo <you>/agentvow-live-test` |
| `GitHub could not confirm the receipt` | the App is not installed on that repository, or lacks Contents/Pull requests read |
| Deliveries red in the App's Recent Deliveries | tunnel down or address changed (App settings → General → Webhook URL), or wrong webhook secret (401) |
| Tunnel address changed | update the App's Webhook URL, `ALLOWED_SERVICE_URLS` in the test repository's `gate.yml`, move the `v1` tag, and the caller's `service-url` |
| Check never appears | the service was not running when the pull request opened; push a new commit |

## 10. Clean up
Stop the service and the tunnel. In the App's settings → **Private keys**: delete the key. Optionally **Advanced → Suspend** or delete the App, and delete the throwaway repository. Remove `~/agentvow-cp.env` and `~/agentvow-app.private-key.pem`.

## 11. After the test
Tell me the results table (pass / fail / different). I will correct `docs/CONTROLPLANE_PHASE1.md`, the threat model and the code for whatever GitHub actually does, and record the run in `docs/LIVE_TESTING.md`. Production later needs: hosting with TLS and a stable address (replacing the tunnel and the placeholder address in `gate.yml`), a Marketplace or private distribution decision, a privacy policy and terms, and billing.
