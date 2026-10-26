# Publishing Agentvow (0.1.0 first release; 0.2.x and 0.3.x follow the same steps)

Everything that can be prepared without your accounts is done and verified: the sdist and wheel build and pass `twine check`, the sdist installs in a clean virtualenv and runs, the extension packages without warnings, the GitHub environment `pypi` exists, and the release workflow is in place. Three things need *you*, because they are logins I cannot enter.

## 1. PyPI (package `agentvow`, checked free on 2026-10-09)
Trusted publishing: no token is stored anywhere.
1. Sign in at pypi.org -> *Your account* -> *Publishing* -> **Add a new pending publisher** and enter exactly:

   | Field | Value |
   |---|---|
   | PyPI project name | `agentvow` |
   | Owner | `NavikkumarModi` |
   | Repository name | `Agentvow` |
   | Workflow name | `release.yml` |
   | Environment name | `pypi` |

2. Create the GitHub Release (this triggers the workflow and uploads the package):
   ```bash
   gh release create v0.1.0 --repo NavikkumarModi/Agentvow --title "Agentvow 0.1.0" --notes-file docs/RELEASE_NOTES_0.1.0.md
   ```
3. Check: `pip install agentvow && agentvow --version && agentvow demo`.
(Manual alternative: `python -m build && twine upload dist/*` with a PyPI API token.)

## 2. VS Code Marketplace (extension `agentvow`)
1. Create a publisher at marketplace.visualstudio.com/manage (the ID is permanent; it appears as `publisher.extension`).
2. Put that ID in `vscode/package.json` (`"publisher"`; now set to `NavikkumarModi`) and rebuild: `scripts/validate_all.sh` (writes `dist/agentvow-0.1.0.vsix`).
3. Create an Azure DevOps personal access token (organisation: all accessible; scope **Marketplace -> Manage**), then:
   ```bash
   cd vscode && npx @vscode/vsce publish --pat <TOKEN>
   ```
   (or upload `dist/agentvow-0.1.0.vsix` on the manage page).
4. Open VSX (VSCodium, Cursor, Windsurf): register at open-vsx.org, create a namespace, then `npx ovsx publish dist/agentvow-0.1.0.vsix -p <TOKEN>`.

## 3. Before and after
- Already public: the GitHub repository. The history uses a GitHub no-reply address; one closed test pull request (#1) still references an older commit with a personal address (accepted).
- Not a trademark search: do one before promoting the name.
- PyPI: published 2026-10-09 (v0.1.0, trusted publishing). The README now shows the PyPI and CI badges; add a Marketplace badge after the extension is published. The PyPI page keeps the README as of the release; it refreshes with the next version.
- Support burden to expect: hooks and Copilot integration are Preview features that can change; the limits are in the README.

## Status (2026-10-09)
PyPI `agentvow` 0.1.0 and Marketplace `NavikkumarModi.agentvow` 0.1.0 are published and verified by installing each from its registry into a clean environment.

## Status (2026-10-13): 0.2.0
PyPI `agentvow` 0.2.0 published (GitHub release v0.2.0, trusted publishing) and verified by installing it from the registry into a clean environment (version, `demo`, `capture`, `check --from-capsule --changed-coverage`, `doctor`). CI green on ubuntu and macos for the release commit; 38/38 validation checks. The extension `dist/agentvow-0.2.0.vsix` is attached to the GitHub release; the Marketplace upload needs the publisher's login (`npx @vscode/vsce publish --packagePath dist/agentvow-0.2.0.vsix` after `vsce login NavikkumarModi`, or upload the file at marketplace.visualstudio.com/manage).

## Status (2026-10-14): 0.2.1
PyPI `agentvow` 0.2.1 published (GitHub release v0.2.1, trusted publishing) and verified by installing it from the registry into a clean environment (version, `demo`, `post-test-hook`, `check --evidence-pack` showing the Timing line, coverage and the not-reproduced manifest, `doctor`). CI green on ubuntu and macos for the release commit; 38/38 validation checks. The extension `dist/agentvow-0.2.1.vsix` is attached to the GitHub release; it has no functional change from 0.2.0 (the version was kept in step), so the Marketplace upload is optional.

## Status (2026-10-22): 0.3.0 PUBLISHED (see the verification paragraph at the end of this file)
Version 0.3.0 is prepared (version bump, changelog, `docs/RELEASE_NOTES_0.3.0.md`, `dist/agentvow-0.3.0-py3-none-any.whl` and `dist/agentvow-0.3.0.vsix` built by `scripts/validate_all.sh`) but nothing has been uploaded or tagged. To publish, follow sections 1 and 2 with the 0.3.0 files after reviewing the release notes: `gh release create v0.3.0 --repo NavikkumarModi/Agentvow --title "Agentvow 0.3.0" --notes-file docs/RELEASE_NOTES_0.3.0.md` (triggers the trusted-publishing workflow). The extension has no functional change from 0.2.0 (the version is kept in step), so its Marketplace upload is optional.

### Publish review of the 0.3.0 candidate (2026-10-22), before any upload
Checked, with results: git tree clean and `main` pushed; CI green on ubuntu and macos for commit `49abc3b`; `scripts/validate_all.sh` 38 of 38 (364 Python and 32 Node tests); the wheel `dist/agentvow-0.3.0-py3-none-any.whl` is byte-identical to the working tree for every `agentvow/*.py`, passes `twine check`, installs into a fresh environment and reports `agentvow 0.3.0`; from that installed wheel a real repository run (capture, then `check --from-capsule --evidence-pack`) reproduced in both contexts and listed the CI-derived install step; versions agree in `pyproject.toml`, `agentvow/__init__.py` and `vscode/package.json`; the release notes' numbers match recorded checks (reader comparison 518/3/10 of 531; derivation 15 identical, 6 with an added base install line, 1 different; the 5 re-replays; the Linux case); an adversarial review of the new code was done and its findings fixed (docs/RELEASE_NOTES_0.3.0.md, CHANGELOG).
Known and accepted at release: Claude Code only for `agentvow init`; Python only; the sandbox's read rules were not tested against a hostile `pip` build backend; the workflow reader is a YAML subset (flow style refused with a note); new replays install PyPI names a repository's own files name (documented in docs/SECURITY_MODEL.md); results behind the product claims are feasibility-scale.
**On publish day** (nothing below has been done): (1) set the CHANGELOG heading to `## 0.3.0 (<date>)`, the README status line to `Status: 0.3.0 (prototype).`, and this file's status to published, in ONE commit; (2) push, wait for CI green; (3) `gh release create v0.3.0 --repo NavikkumarModi/Agentvow --title "Agentvow 0.3.0" --notes-file docs/RELEASE_NOTES_0.3.0.md --target main` (this triggers the trusted-publishing workflow; a release cannot be unpublished from PyPI, only yanked); (4) when PyPI shows 0.3.0, install it into a clean environment and repeat: `agentvow --version`, `agentvow demo`, `agentvow doctor`, `agentvow init --dry-run`; (5) attach `dist/agentvow-0.3.0.vsix` to the release; the Marketplace upload is optional (no functional extension change), `npx @vscode/vsce publish --packagePath dist/agentvow-0.3.0.vsix` needs your publisher login.

### 0.3.0 published and verified (2026-10-22)
GitHub release v0.3.0 created from commit `f98cbbb` (CI green on ubuntu and macos); the trusted-publishing workflow succeeded and PyPI `agentvow` 0.3.0 is live. Verified by installing `agentvow==0.3.0` from the registry into a clean environment: `agentvow --version` (0.3.0), `demo`, `doctor` (both hook payloads), `init --dry-run`, and a real repository run (`capture`, then `check --from-capsule --evidence-pack`) that reproduced in both contexts. `dist/agentvow-0.3.0.vsix` is attached to the release; the Marketplace upload is optional (no functional extension change) and needs the publisher's login.

## Status (2026-10-22): 0.3.1 PUBLISHED (see the verification paragraph at the end of this file)
Version 0.3.1 is prepared (version bump in the three files, changelog, `docs/RELEASE_NOTES_0.3.1.md`); nothing has been tagged or uploaded. The latest published release is 0.3.0. Publish steps are the same as in the 0.3.0 publish review above (changelog date and README status in one commit, CI green, `gh release create v0.3.1 ... --notes-file docs/RELEASE_NOTES_0.3.1.md`, install check from PyPI, attach `dist/agentvow-0.3.1.vsix`).

### 0.3.1 published and verified (2026-10-22)
GitHub release v0.3.1 created from commit `b1b8189` (CI green on ubuntu and macos); the trusted-publishing workflow succeeded and PyPI `agentvow` 0.3.1 is live (the package index took about a minute to list it). Verified by installing `agentvow==0.3.1` from the registry into a clean environment: version, `demo`, `doctor`, `init --dry-run`, `check --evidence-pack` without a capture on a repository whose only declaration of a dependency is its CI workflow (project-native context passed and listed the install step; changed-line coverage measured) and, after `capture`, `check --from-capsule --evidence-pack` reproducing in both contexts. `dist/agentvow-0.3.1.vsix` is attached to the release; the Marketplace upload is optional (no functional extension change) and needs the publisher's login. The new `run-tests` event guard was tested locally only; it has not run on GitHub.

## Status (2026-10-22): 0.4.0 PUBLISHED (see the verification paragraph at the end of this file)
Version 0.4.0 is prepared (version bump in the three files, changelog, `docs/RELEASE_NOTES_0.4.0.md`) after an adversarial review whose findings are fixed; nothing is tagged or uploaded. The latest published release is 0.3.1. The gate workflow defaults to `agentvow-version: 0.4.0`, so publish the package BEFORE anyone calls the workflow. Before publishing, run the three-job gate workflow once on GitHub in local-policy mode (a test pull request that calls `./.github/workflows/gate.yml` cannot install 0.4.0 from PyPI until it exists: use a throwaway pre-release or call it after publishing). Publish steps as for 0.3.0 and 0.3.1.

### 0.4.0 published and verified (2026-10-22)
GitHub release v0.4.0 created from commit `6b32bf0` (CI green on ubuntu and macos); the trusted-publishing workflow succeeded and PyPI `agentvow` 0.4.0 is live (listed within about a minute). Verified by installing `agentvow==0.4.0` from the registry into a clean environment: version, `demo`, `doctor`, `capture --export`, `check --from-capture` (SUPPORTED, `capture_source` bundle), `receipt`, `policy evaluate` (needs_acknowledgement because the capture was supplied as a file, as the default policy intends), `pilot-report`, and a tampered tree refused as UNKNOWN. `dist/agentvow-0.4.0.vsix` is attached to the release; the Marketplace upload is optional (no functional extension change). The three-job gate workflow then ran once on GitHub with 0.4.0 from PyPI (`docs/LIVE_TESTING.md`, pull request #4, closed unmerged).

## Status (2026-10-23): 0.4.1 prepared, NOT published
Version 0.4.1 is prepared (version bump in the three files, changelog entry dated 2026-10-23, `docs/RELEASE_NOTES_0.4.1.md`); nothing is tagged or uploaded. The latest published release is 0.4.0. Publish-day steps (each needs the owner's explicit yes): (1) DONE: changelog dated and README status updated in the release commit; (2) CI green on ubuntu and macos on that commit; (3) `gh release create v0.4.1 ... --notes-file docs/RELEASE_NOTES_0.4.1.md` (trusted publishing uploads to PyPI); (4) install `agentvow==0.4.1` from PyPI into a clean environment and check version, `demo`, `doctor`, `capture --export`, `check --from-capture`, `receipt` on a repository that commits `.agentvow/policy.json` (the receipt's `git_tree` must equal `git rev-parse HEAD^{tree}`); (5) attach `dist/agentvow-0.4.1.vsix`; (6) only after PyPI lists 0.4.1: raise the default `agentvow-version` in `.github/workflows/gate.yml` to `0.4.1` and move the `@v1` style tag callers pin. The gate workflow's default stays `0.4.0` until then because it installs from PyPI.

### 0.4.1 published (2026-10-23) and a regression found in it
GitHub release v0.4.1 created from commit `dccd9d9` (CI green on ubuntu and macos); the trusted-publishing workflow succeeded and PyPI `agentvow` 0.4.1 is live. Verified from a clean environment: version, `demo`, `doctor`, and on a repository that commits `.agentvow/policy.json` the receipt's `git_tree` equals `git rev-parse HEAD^{tree}` (the fix works). `dist/agentvow-0.4.1.vsix` attached to the release. **Regression found by that same check:** a `check` that cannot collect (a repository with one commit and no base) reports its commit as `?`; `agentvow receipt` copied it, and 0.4.1's stricter validation then evaluates such a receipt as `block` (0.4.0 gave needs_acknowledgement). Fixed in the source (see the changelog, "Unreleased"); it needs a 0.4.2 to ship. The gate workflow's default `agentvow-version` was therefore NOT raised to 0.4.1; raise it to 0.4.2 when that is published.

## Status (2026-10-23): 0.4.2 prepared, NOT published
Version 0.4.2 is prepared (version bump in the three files, changelog entry dated 2026-10-23, `docs/RELEASE_NOTES_0.4.2.md`); nothing is tagged or uploaded. The latest published release is 0.4.1 (with the regression described above). Publish-day steps, each needing the owner's explicit yes for the release command: (1) DONE: changelog dated, README status in the release commit; (2) CI green on ubuntu and macos on that commit; (3) `gh release create v0.4.2 --target <FULL 40-character sha> --title "Agentvow 0.4.2" --notes-file docs/RELEASE_NOTES_0.4.2.md` (an abbreviated sha is refused); (4) install `agentvow==0.4.2` from PyPI into a clean environment and check version, `demo`, and on a repository that commits `.agentvow/policy.json` that the receipt's `git_tree` equals `HEAD^{tree}` AND on a single-commit repository that `receipt` then `policy evaluate` gives needs_acknowledgement, not block (keep the files you create OUTSIDE the repository: untracked files change the content hash); (5) attach `dist/agentvow-0.4.2.vsix`; (6) only after PyPI lists 0.4.2: raise the default `agentvow-version` in `.github/workflows/gate.yml` to `0.4.2`.

### 0.4.2 published and verified (2026-10-23)
GitHub release v0.4.2 created from commit `dd820a0` (CI green on ubuntu and macos); the trusted-publishing workflow succeeded and PyPI `agentvow` 0.4.2 is live. Verified by installing `agentvow==0.4.2` from the registry into a clean environment, with every working file kept outside the repositories: version, `demo`; on a repository that commits `.agentvow/policy.json` the receipt's `git_tree` equals `HEAD^{tree}` and `policy evaluate` gives needs_acknowledgement (UNKNOWN claim); on a single-commit repository (the check's commit field is `?`) the receipt is valid and `policy evaluate` gives needs_acknowledgement (rule `unknown`), not block. `dist/agentvow-0.4.2.vsix` attached. The gate workflow's default `agentvow-version` is now `0.4.2`. The 0.4.1 regression is fixed in the published package.

## Status (2026-10-26): 0.4.3 prepared, NOT published
Version 0.4.3 is prepared (version bump in the three files, changelog entry dated 2026-10-26, `docs/RELEASE_NOTES_0.4.3.md`); nothing is tagged or uploaded. The latest published release is 0.4.2. Publish-day steps, the release command needing the owner's explicit yes: (1) DONE: changelog dated, README status in the release commit; (2) CI green on ubuntu and macos on that commit; (3) `gh release create v0.4.3 --target <FULL 40-character sha> --title "Agentvow 0.4.3" --notes-file docs/RELEASE_NOTES_0.4.3.md`; (4) install `agentvow==0.4.3` from PyPI into a clean environment (working files OUTSIDE the repositories) and check version, `demo`, `receipt` then `policy evaluate` (provenance fields present: `capture_authenticated`, `state_binding`, `partial_replay`; a receipt with `dropped_pins` needs acknowledgement), the single-commit case still giving needs_acknowledgement, and `agentvow policy init` printing `partial_capture`; (5) attach `dist/agentvow-0.4.3.vsix`; (6) only after PyPI lists 0.4.3: raise the default `agentvow-version` in `.github/workflows/gate.yml` and `gate-service.yml` to `0.4.3` (a test requires the two files' inputs to match). The service-backed workflow should be re-run on GitHub (sha-pinned) before it is described as verified.

### 0.4.3 published and verified (2026-10-26)
GitHub release v0.4.3 created from commit `8316b33` (CI green on ubuntu and macos); the trusted-publishing workflow succeeded and PyPI `agentvow` 0.4.3 is live. Verified by installing `agentvow==0.4.3` from the registry into a clean environment, working files outside the repositories: version, `demo`, `policy init` prints `partial_capture`; on a single-commit repository the receipt is valid, its `git_tree` equals `HEAD^{tree}`, the provenance fields are present (`capture_authenticated` null, `state_binding` empty, `partial_replay` false) and `policy evaluate` gives needs_acknowledgement (rule `unknown`); a receipt whose claim came from a partial local capture gives needs_acknowledgement with the rules `supported` and `partial_capture`, and `allow` under a policy that sets `partial_capture` to `allow`. `dist/agentvow-0.4.3.vsix` attached. The default `agentvow-version` of both gate workflows is now `0.4.3`. **Afterwards the same day:** the sha-pinned `gate-service.yml` was run through the service on real GitHub with Agentvow 0.4.3 (accepted; a different commit of the file and a branch-name pin refused: `docs/LIVE_TESTING.md`). The pending check and the acknowledgement flow were also re-verified with the sha-pinned files. **Not verified:** fork pull requests, a hosted deployment.
