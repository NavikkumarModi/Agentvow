# Agentvow 0.5.2

Agentvow checks what a coding agent says it did against what it can independently observe. It informs you; it never approves, rejects or merges, and no language model decides a verdict. Still a prototype, not a safety verdict.

This release makes the review queue harder to fool. Until now `agentvow queue --github` trusted any `agentvow-gate` artifact, and a pull request can forge one by editing its own workflow.

## New: authenticated receipts for `agentvow queue --github`
`--verify report|require` checks each receipt with GitHub's artifact attestations (`gh attestation verify`) against a pinned signer workflow and a **mandatory** list of allowed signer commits (`--signer-digest`, repeatable; `--signer-workflow` to change the signer). Each receipt is then verified or not authenticated:
- A receipt that does not verify is shown as **not authenticated** (`report`) or **needs a person** (`require`). It is never ranked as "no flag raised", and a stop is never weakened.
- The list of signer commits is required because a signer **path** alone is not enough: in a live test, a pull request that edited the signer file at the same path still passed a path-only check. With the commit list, the forgeries tried failed.
- `--verify` needs `--github`. Without an allowed commit the command refuses (exit 3) before calling `gh`. The default stays off, so existing setups do not change.

**Repository, not in the wheel:** `.github/workflows/gate-attest.yml` is the gate with an extra `attest` job. Only that job holds the OIDC and attestation permissions; it runs no pull-request code and signs the exact file the replay hashed. `.github/workflows/queue.yml` gains `verify` (off by default), `signer-digests` (mandatory when verifying) and `signer-workflow`.

## New: the receipt records how the gate was configured
A verified receipt shows that the pinned gate produced the file. It does not show that the pull request left the gate's inputs alone: the caller workflow can set the test command, timeout and Agentvow version. Receipts now carry `gate_inputs` (test command, timeout; `tool_version` was already recorded), and the policy gains three opt-in keys:
- `allowed_test_commands`: any other test command needs a person.
- `min_tool_version`: an older, missing or unreadable version needs a person.
- `require_gate_inputs`: a receipt without `gate_inputs` needs a person.

All three are off by default, so there is **no behaviour change until you set them**. A policy file that uses them is rejected by older Agentvow versions (unknown keys block), so pin the gate's `agentvow-version` to this release first. The four gate workflows pass the inputs through environment variables that older versions ignore.

## What was run, and what was not
- Run on GitHub, in a public throwaway repository, with the real `gate-attest.yml`: an honest same-repository pull request verified; a pull request that deleted the gate and uploaded its own forged `agentvow-gate` artifact ranked "no flag raised" with verification off, "not authenticated" with `report`, and "needs a person" with `require`.
- Two attempts to get a **verified** receipt with a changed test command from the pull request's own caller both ended in UNKNOWN. That is not proof that none exists. The author did this pass; an independent reviewer did not.
- The `gate_inputs` rules are tested locally. They have **not** been run on GitHub.
- **Not tested:** fork pull requests (they probably get no attestation token) and private repositories. Artifact attestations need GitHub Enterprise Cloud for private repositories, so verification is for public repositories in practice.

## Correction to the 0.5.1 notes
The 0.5.1 notes say `queue --github` was tested against a fake `gh` only. Since then it has been run against 12 real gate receipts and, through `queue.yml`, on GitHub Actions in a private test repository. Its receipts were still unauthenticated in 0.5.1; with `--verify` they can now be checked.

## Known limits
"Verified" means provenance: the pinned gate workflow, at an allowed commit, in this repository, produced these exact bytes. It does not mean the replay was right or that the configuration is the one you chose. The allowed-commit list is yours to maintain: a stale entry keeps verifying. The signer and GitHub's signing service are trusted. Verification needs network access and `gh` 2.x with `attestation verify`. The default policy still trusts any verified receipt's configuration.

Design, experiments and the adversarial pass: `docs/research/RECEIPT_AUTH_DESIGN.md`. Setup: `docs/GATE_WORKFLOW.md`.
