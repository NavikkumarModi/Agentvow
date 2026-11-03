# Design: authenticating the gate's receipts for `queue --github` (2026-11-03, draft, nothing implemented)

Purpose: `agentvow queue --github` reads receipts from workflow artifacts, which a pull request can forge by editing its own workflow (documented limit in 0.5.1). This page decides whether GitHub's artifact attestations can close that gap without Agentvow signing anything itself. No novelty claim: this reuses GitHub's mechanism and the `gh` command. Source labels: `[snippet]` = seen only in a search summary, `[read]` = full source read; all web sources below are `[snippet]` and must be read before any claim in a paper. The local `gh attestation verify --help` text was read.

## 1. Threat model
Attacker: the pull-request author or a compromised agent, who controls the pull request's files, including its caller workflow, and can upload an artifact named `agentvow-gate` with any `receipt.json`.
Goal: make the queue show "no flag raised" (or hide a stop) for a change the gate did not check, or checked differently.
Protected: the meaning of "this receipt was produced by the pinned gate workflow, from this repository, for this commit".
Out of scope: a compromise of the gate repository itself, of GitHub's signing service, or of the runner; a gate that runs the pull request's tests and trusts what they print (the existing known miss, not changed by this).

## 2. Mechanism (reuse, nothing new)
1. The gate's `decide` job (the one that never runs pull-request code) attests `receipt.json` with `actions/attest` (or its wrapper `attest-build-provenance`) [snippet]. Needs `id-token: write`, `attestations: write`, `contents: read` in the caller's permissions.
2. `queue --github` downloads the artifact as today, then runs `gh attestation verify receipt.json --repo OWNER/NAME --signer-workflow NavikkumarModi/Agentvow/.github/workflows/gate.yml --signer-digest <allowed sha> --deny-self-hosted-runners --format json`. Flags confirmed in the local help: `--signer-workflow`, `--signer-digest`, `--signer-repo`, `--source-digest`, `--source-ref`, `--cert-identity`, `--deny-self-hosted-runners`.
3. The signer identity comes from the signing certificate, not from the workflow text in the pull request. A pull request cannot make a different workflow claim to be `Agentvow/.github/workflows/gate.yml`: a fork's copy has another repository path and fails `--signer-workflow` [snippet: GitHub's SLSA Build L3 guide describes pinning a reusable workflow this way].

## 3. What verification does and does not establish
Establishes: this exact `receipt.json` was attested by a run of the named workflow at an allowed commit, in this repository.
Does not establish: that the replay was right (same limits as today), that the receipt's `commit` is the pull request's current head (still checked by `ghreceipts` against the pull request), or anything about the repository's other workflows.
Open point to verify: for a `pull_request` run the attestation's source digest is the merge commit, while the receipt names the head commit. The check must compare the receipt's own fields with the pull request, and use the attestation only for "who produced this file".

## 4. New states in the queue
- **verified**: attestation passes with the pinned signer and allowed digest. Ranked as today.
- **unverified**: a receipt exists, but there is no attestation or it fails. Shown as unverified, with the reason, and never ranked as "no flag raised". This is the fail-closed rule: missing evidence does not become support.
- **no receipt**: unchanged.
Policy chooses the mode: `off` (today's behaviour), `report` (show the state), `require` (unverified receipts count as needing a person). The default stays `off`, to avoid a surprise in existing setups.

## 5. Known limits (to state in the docs, not hide)
- **Private repositories**: artifact attestations need GitHub Enterprise Cloud on a private or internal repository; on Free, Pro and Team plans they exist for public repositories only [snippet: GitHub docs and the action's README]. So verification would not work for most private repositories. Needs a check on the `agentvow-live-test2` private repo, which should fail to attest.
- **Fork pull requests**: a `pull_request` run from a fork gets a read-only token and no `id-token`, so no attestation can be made [unverified; the search found nothing]. Fork receipts stay "unverified"; `docs/FORK_PRS.md` covers the separate fork path.
- **Allowed digests**: without `--signer-digest` an old, vulnerable commit of the gate still verifies. The allowed list must be maintained and shipped with the release (an exact list or a minimum, to decide).
- **Dependency**: `gh` 2.x with `attestation verify` and network access to GitHub's attestation API; the first verification online. Offline bundle verification exists (`--bundle`) but is not planned.
- **Authority**: verification says who produced a file. The control plane's `agentvow/evidence` check stays the authenticated path for merging; this is a read-only audit aid.

## 6. Experiments before building
1. On a **public** throwaway repository: add the attest step to `gate.yml`, run on a same-repository pull request, run `gh attestation verify` with `--signer-workflow` and `--signer-digest`. Expected: passes. Record the output fields (source digest and ref).
2. Edit the caller in a second pull request to point at a fork's `gate.yml` copy and forge `receipt.json`: expected: verification fails on the signer. This is the attack the feature exists for.
3. Same attack by dropping the attest step or removing `id-token`: expected: "unverified".
4. A fork pull request (from a second account): expected: no attestation. If that account is not available, mark this as not tested.
5. The private repository: expected: attestation not available or not verifiable.
Stop rule: if experiment 2 does not fail, stop and do not ship the feature.

## 7. Build plan if the experiments pass
`ghreceipts.fetch` gains an optional `verify` argument. A small `_verify(path, repo, signer, digests, run)` wraps `gh attestation verify` and returns (ok, reason). `queue` gets `--verify off|report|require`, a signer workflow option and an allowed digest list in the policy file. `gate.yml` gets the attest step in `decide`, behind an input. Tests use a fake `gh`, as `ghreceipts` does; the five experiments become a live-test section in `docs/LIVE_TESTING.md`.

## 8. Gate
Prior-art read still owed (attestations for CI results, SLSA/in-toto test-result attestations, commercial PR-gate products): only search summaries were seen. Per CLAUDE.md, no sentence in the docs may call this novel; it is a reuse of GitHub's own mechanism.
