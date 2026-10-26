# Golden path: one supported setup, end to end

One path that has been exercised, with what was and was not verified at each step. Anything not on this page is experimental. Target: a **Python repository**, Claude Code (hooks verified live on 2.1.263) or the command line, and a **customer-run GitHub Actions gate**. Time: about 30 minutes for steps 1 to 4, a few hours with a service.

## 1. Install and check the machine (verified, repeatedly)
```bash
pip install agentvow==0.4.2          # from PyPI; Python 3.10+; macOS or Linux (tests are refused on Windows)
agentvow doctor --repo /path/to/project
```
`doctor` says what is missing (a sandbox on Linux: bubblewrap, and on Ubuntu 24.04+ the user-namespace setting) and runs the whole hook path.

## 2. Capture at the agent's turn (Claude Code verified live; other agents experimental)
```bash
agentvow init --repo /path/to/project        # preview, confirmation, backup of the settings file; --dry-run, --remove
```
Adds the `PostToolUse` capture hook and the `Stop` check hook. Nothing is blocked; the verdict appears in the VS Code panel or the CLI output. Without Claude Code, call `agentvow capture` after the agent's test run yourself.

## 3. Check a claim on the command line (verified)
```bash
echo "I added X. All 12 tests pass." > ../msg.txt        # keep working files OUTSIDE the repository: untracked files change the content hash
agentvow check --repo . --base main --transcript ../msg.txt --run-tests --json > ../check.json
agentvow receipt --decision ../check.json --repo-slug you/project --repo . -o ../receipt.json
agentvow policy init > ../policy.json && agentvow policy evaluate --policy ../policy.json --receipt ../receipt.json
```
Expect one of: `allow`, `needs_acknowledgement` (an UNKNOWN claim, a supplied capture, a partial replay), `block` (a contradiction; it cannot be acknowledged away). The staged recording in the README shows the three.

## 4. The local gate on pull requests (verified on GitHub on 2026-10-26 with `contents: read` only)
Add to the repository `agentvow-policy.json` (default branch) and `.github/workflows/agentvow-gate.yml`:
```yaml
name: agentvow-gate
on: pull_request
permissions: { contents: read }
jobs:
  gate:
    uses: NavikkumarModi/Agentvow/.github/workflows/gate.yml@<40-character commit sha at or after 275a655>
    with: { fail-on: block, policy-path: agentvow-policy.json }
```
Open a pull request: the `gate / replay` and `gate / decide` checks run; the job summary shows the decision and reasons. This path needs no credential, no service and no OIDC permission, and also works for pull requests from forks as a local decision (not run on a fork here).

## 5. The service-backed gate (a required check and a named-acknowledgement record)
Needs a deployed control plane (`docs/DEPLOY.md`), an organisation-owned GitHub App (`docs/SETUP_GITHUB_APP.md`), a copy of `gate-service.yml` with your address in `ALLOWED_SERVICE_URLS`, the service's trusted value set to that copy at a full commit sha, and branch protection naming the App as the required check's source. **Verified from a laptop behind a tunnel: on 2026-10-23 with the previous single-file workflow (ten acceptance tests), and on 2026-10-26 with the sha-pinned `gate-service.yml` (accepted; another commit and a branch-name pin refused). The pending check and the acknowledgement flow were re-verified with the sha-pinned files. Not verified: a hosted deployment. Fork pull requests are not supported on this path** (the required check stays pending).

## 6. Collect evidence for a team (verified on synthetic and live-test receipts)
```bash
agentvow pilot-report --receipts receipts/ --acks acks/ --policy agentvow-policy.json -o report.md
```
`docs/pilot/SAMPLE_REPORT_LIVE_TEST.md` shows the shape. It claims no defects prevented and no time saved.

## Exit criteria for this path
A clean machine completes steps 1 to 4 from this page without editing Agentvow's code; step 5 is repeated on a throwaway repository after any change to the workflows or the service, and the result is recorded in `docs/LIVE_TESTING.md`.
