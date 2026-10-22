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

## Status (2026-10-22): 0.3.0 release commit prepared; the GitHub release (which uploads to PyPI) is the remaining step and has NOT been made
Version 0.3.0 is prepared (version bump, changelog, `docs/RELEASE_NOTES_0.3.0.md`, `dist/agentvow-0.3.0-py3-none-any.whl` and `dist/agentvow-0.3.0.vsix` built by `scripts/validate_all.sh`) but nothing has been uploaded or tagged. To publish, follow sections 1 and 2 with the 0.3.0 files after reviewing the release notes: `gh release create v0.3.0 --repo NavikkumarModi/Agentvow --title "Agentvow 0.3.0" --notes-file docs/RELEASE_NOTES_0.3.0.md` (triggers the trusted-publishing workflow). The extension has no functional change from 0.2.0 (the version is kept in step), so its Marketplace upload is optional.

### Publish review of the 0.3.0 candidate (2026-10-22), before any upload
Checked, with results: git tree clean and `main` pushed; CI green on ubuntu and macos for commit `49abc3b`; `scripts/validate_all.sh` 38 of 38 (364 Python and 32 Node tests); the wheel `dist/agentvow-0.3.0-py3-none-any.whl` is byte-identical to the working tree for every `agentvow/*.py`, passes `twine check`, installs into a fresh environment and reports `agentvow 0.3.0`; from that installed wheel a real repository run (capture, then `check --from-capsule --evidence-pack`) reproduced in both contexts and listed the CI-derived install step; versions agree in `pyproject.toml`, `agentvow/__init__.py` and `vscode/package.json`; the release notes' numbers match recorded checks (reader comparison 518/3/10 of 531; derivation 15 identical, 6 with an added base install line, 1 different; the 5 re-replays; the Linux case); an adversarial review of the new code was done and its findings fixed (docs/RELEASE_NOTES_0.3.0.md, CHANGELOG).
Known and accepted at release: Claude Code only for `agentvow init`; Python only; the sandbox's read rules were not tested against a hostile `pip` build backend; the workflow reader is a YAML subset (flow style refused with a note); new replays install PyPI names a repository's own files name (documented in docs/SECURITY_MODEL.md); results behind the product claims are feasibility-scale.
**On publish day** (nothing below has been done): (1) set the CHANGELOG heading to `## 0.3.0 (<date>)`, the README status line to `Status: 0.3.0 (prototype).`, and this file's status to published, in ONE commit; (2) push, wait for CI green; (3) `gh release create v0.3.0 --repo NavikkumarModi/Agentvow --title "Agentvow 0.3.0" --notes-file docs/RELEASE_NOTES_0.3.0.md --target main` (this triggers the trusted-publishing workflow; a release cannot be unpublished from PyPI, only yanked); (4) when PyPI shows 0.3.0, install it into a clean environment and repeat: `agentvow --version`, `agentvow demo`, `agentvow doctor`, `agentvow init --dry-run`; (5) attach `dist/agentvow-0.3.0.vsix` to the release; the Marketplace upload is optional (no functional extension change), `npx @vscode/vsce publish --packagePath dist/agentvow-0.3.0.vsix` needs your publisher login.
