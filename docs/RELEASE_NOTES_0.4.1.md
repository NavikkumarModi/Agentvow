# Agentvow 0.4.1

Agentvow checks what a coding agent says it did against what it can independently observe. It informs you; it never approves, rejects or merges, and no language model decides a verdict. Still a prototype, not a safety verdict.

## Fixed
- **A committed `.agentvow/policy.json` no longer breaks the content hash.** In 0.4.0 the hash left out all of `.agentvow/`, so a repository that committed a file there got a receipt whose hash never matched the commit, and a control plane would refuse it. Files the commit tracks under `.agentvow/` now count; Agentvow's own untracked state still does not.
- **Receipts are validated more strictly** (full hexadecimal commit and tree ids, `owner/name` repository) and **a pull request with more than 200 claims** keeps the worst ones and records that some were left out, instead of producing a receipt nobody accepts.
- **Gate workflow** (pin the new tag to get it): the identity token is issued for one specific receipt and a caller can no longer name an arbitrary server for it.

## Also in the source (not in the wheel)
An experimental, self-hostable control plane service (`controlplane/service/`) that publishes the `agentvow/evidence` check on pull requests. It ran once against real GitHub in a throwaway repository; see `docs/LIVE_TESTING.md` for what passed and what was not tested (fork pull requests).

## Known limits
As 0.4.0: Python repositories only; capture covers Python packages, not system packages, services, generated files or secrets; running tests needs macOS or Linux; a pass is evidence to weigh, not verification.
