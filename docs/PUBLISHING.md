# Publishing

Nothing is published yet. Everything below needs your accounts; AgentMirror cannot do it for you.

## PyPI (package `agentmirror-check`)
1. Create a PyPI account and, on pypi.org, add a *pending trusted publisher*: owner `NavikkumarModi`, repository `AgentMirror`, workflow `release.yml`, environment `pypi`.
2. In the GitHub repository create an environment named `pypi`.
3. Make the repository public (or keep it private; PyPI does not need it to be public), then create a GitHub Release (tag `v0.1.0`). The `release` workflow builds, runs `twine check` and publishes. No token is stored anywhere.
4. Check: `pip install agentmirror-check && agentmirror --version`.
Manual alternative: `python -m build && twine upload dist/*` with a PyPI API token.

## VS Code Marketplace (extension `agentmirror`)
1. Create a publisher at marketplace.visualstudio.com/manage and replace `"publisher": "agentmirror-dev"` in `vscode/package.json` with your publisher ID (the current value is a placeholder).
2. Create an Azure DevOps personal access token with the *Marketplace (Manage)* scope.
3. `cd vscode && npx @vscode/vsce publish` (or upload `dist/agentmirror-0.1.0.vsix` on the manage page).
Open VSX (for VSCodium/Cursor): `npx ovsx publish dist/agentmirror-0.1.0.vsix -p <token>`.

## Before making it public
- The repository contains research notes and study results (`docs/research/`); `data/` is not in git. Review that you are comfortable publishing them.
- The README states the limits (not a safety verdict; hostile repositories; macOS/Linux only for tests). Keep them.
