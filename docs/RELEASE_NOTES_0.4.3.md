# Agentvow 0.4.3

Agentvow checks what a coding agent says it did against what it can independently observe. It informs you; it never approves, rejects or merges, and no language model decides a verdict. Still a prototype, not a safety verdict.

## New in the package
- **Receipts say what the capture proves, in separate fields.** Per claim: `capture_authenticated` (true for a local signed capsule, false for a supplied bundle, null when there is none), `state_binding` (`capsule` or `git_tree`) and `partial_replay` (the replay left out pinned packages that pip could not install on the runner). They are never merged into one "verified" flag. Receipts without the fields stay valid.
- **A new policy rule, `partial_capture`** (default `needs_acknowledgement`): a supported result from a replay that left out pinned packages needs a named person's acknowledgement; set it to `allow` or `block` in your policy file. **A policy file that uses this key is rejected by Agentvow 0.4.2 and earlier** (an unknown key blocks), so pin the gate's `agentvow-version` to 0.4.3 or later when you add it.

## New in the repository (not in the wheel)
- **Two gate workflows.** `gate.yml` is now the local-decision workflow: replay and decide, `contents: read` only, no OIDC permission. `gate-service.yml` adds the upload to the control plane and is the only file the service trusts; the service refuses to start unless each trusted workflow is pinned to a full 40-character commit sha, and it checks the token's `job_workflow_sha`. Pin your `uses:` references to a commit sha.
- **`docs/TRUST_MODEL.md`**: what a local capsule, a supplied bundle, a replay result, a receipt and a control plane check do and do not establish; the golden-path page; the current capture evidence with sample sizes and caveats in `docs/EVIDENCE_AND_LIMITS.md`; hostile-test-harness tests that pin what the tool does when a repository's own tests try to fake a pass.
- The control plane service (experimental, not deployed) gained account plans, retention, erasure after the App is uninstalled, a dashboard, backup commands and a deployment recipe, and went through three adversarial reviews.

## Known limits
As before: Python repositories only; capture covers Python packages, not system packages, services, generated files or secrets; running tests needs macOS or Linux; a pass is evidence to weigh, not verification. A repository's own test code can fake its output: a fully deceptive harness is believed (the finding names a modified test file). Fork pull requests are not supported by the service-backed gate. The sha-pinned `gate-service.yml` has not yet been run on GitHub.
