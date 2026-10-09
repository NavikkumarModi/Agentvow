# Publishing Agentvow 0.1.0

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
