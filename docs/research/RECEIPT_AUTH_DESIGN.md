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

## 9. Results of experiments 1 to 3 (2026-11-03, public throwaway repository `NavikkumarModi/agentvow-attest-test`, `gh` 2.98.0, `actions/attest-build-provenance@v2.4.0`)
The throwaway used its own reusable `signer.yml` as the stand-in for `gate.yml`; the gate itself was not changed. Same-repository pull requests only.
| Case | Result |
|---|---|
| 1. Honest receipt, caller pinned to the signer sha | Verifies with `--signer-workflow` and `--signer-digest`. Certificate: signer `signer.yml@<pinned sha>`, `buildSignerDigest` = the pinned sha, `sourceRepositoryRef` = `refs/pull/N/merge`, `sourceRepositoryDigest` = the **merge commit** (as predicted in section 3), github-hosted runner |
| A. Forged receipt, no attestation step | Fails: no attestation found (HTTP 404) |
| B. Forged receipt attested by another workflow file in the same repository | Fails `--signer-workflow` (error text only partly captured: "verifying with issuer sigstore.dev") |
| C. Pull request edits the signer at the **same path** and calls it | **Passes with `--signer-workflow` alone (exit 0)**; fails with `--signer-digest` (got the merge commit, expected the pinned sha) |
Conclusion: the signer path alone is not enough. A pull request can change the file at that path and the check still passes; **`--signer-digest` against an allowed list is required**, not optional. With it, the three forgeries fail and the honest receipt passes. The stop rule (a forgery that verifies) does not fire once the digest is enforced.
Not yet tested: experiment 4 (fork pull request) and 5 (private repository); a forged receipt whose signer is a **fork repository** with the same path (not tested; `--signer-workflow` includes owner/repo so it should fail); the real `gate.yml`.

## 10. Result with the real gate (2026-11-03, `gate-attest.yml` at `d5de816`, public throwaway `agentvow-attest-test`, `agentvow queue --github --verify`)
- **Honest pull request #3** (caller pinned to `d5de816`, same-repository): replay, decide and attest all succeeded; `queue --verify report` shows it `[verified]`. With a signer commit that is not on the allowed list the same receipt is reported as not authenticated ("attested by the pinned signer workflow, but at a commit that is not on the allowed list"). With no allowed list the command refuses (exit 3).
- **Forged pull request #4** (deletes the gate caller and uploads its own `agentvow-gate` artifact: a valid clean receipt naming its own head commit): `--verify off` ranks it **"no flag raised"** (the attack works against the unauthenticated queue); `--verify report` shows it as **"receipt not authenticated: its result is not trusted"** and counts it apart from "no flag raised"; `--verify require` puts it under **"needs a person"**.
- Still untested: fork pull requests, private repositories, and a forger who obtains a real attestation from the allowed workflow for a different file (the check binds the signature to the file's bytes, but the receipt's own fields are only as good as the gate that wrote them).

## 11. Adversarial pass on the feature (2026-11-03; done by the author, not by an independent reviewer: the `adversarial-reviewer` agent named in CLAUDE.md is not available in this session, so this does not satisfy that rule)
Question: can a pull request get a **verified** receipt that says more than the truth?
1. **The pull request controls the gate's inputs.** It edits its own caller workflow, which stays pinned to an allowed `gate-attest.yml` commit but can set `test-command`, `agentvow-version` (any older release on PyPI), `fail-on` and `test-timeout`. The attestation binds the signed file and the signer workflow and commit; it does **not** bind these inputs, and the receipt records `tool_version` but **not the test command**. So "verified" means "the pinned gate workflow produced this file", not "with a configuration the maintainers chose".
   Live attempts (public throwaway, pull request with broken code and an edited caller): `test-command: "{py} -c pass"` and `test-command: "{py} -c \"print('2 passed in 0.01s')\""`. Both produced a **verified** receipt and both came out **UNKNOWN / needs a person**, not allowed. The two tries did not get a clean result; this is not proof that none exists.
   Mitigation not built: record the effective inputs (test command, version, timeout) in the receipt, and add a policy rule that asks a person when the test command is not the project's default or the version is older than a floor.
2. Merge commit versus head commit: the attestation names the merge commit; the receipt's `commit` is matched to the pull request's head by `ghreceipts`, not by the attestation. A receipt attested for one pull request's run could be re-uploaded by another? The check binds the file's bytes to **some** attested run of the signer in this repository, not to this pull request. A pull request could copy the verified `receipt.json` of an earlier run, but `ghreceipts` also requires `repo` and `commit` in the receipt to match the pull request's head, so the copy fails unless the commit is the same. Same-commit replays are the same evidence. Not tested live.
3. Allowed-list staleness: an old allowed commit with a known flaw keeps verifying until it is removed; the list is the user's to maintain.
4. Scope: public repositories only; fork pull requests, private repositories, and a compromised signer repository are out of scope.
Verdict: the feature does what it claims (forged artifacts fail) and no more. The input-binding gap in point 1 should be stated wherever "verified" is shown; building the mitigation is the next step if this is shipped.

Follow-up (same day): the mitigation in point 1 was built as opt-in policy keys (`gate_inputs` in the receipt; `allowed_test_commands`, `min_tool_version`, `require_gate_inputs`). It only helps a project that sets them; the default policy still trusts any verified receipt's configuration. Run on GitHub in section 12.

## 12. Released 0.5.2 run on GitHub (2026-11-04, public throwaway `agentvow-attest-test`, pull request #5)
The pull request's caller was pinned to `gate-attest.yml` at `88f20b7` with `agentvow-version: "0.5.2"` (from PyPI) and an edited test command (`{py} -c "print('2 passed in 0.01s')"`). Replay, decide and attest all succeeded. `agentvow queue --github --verify` (0.5.2 from PyPI, signer commit on the allowed list):
- Default policy, `--verify report`: the receipt is `[verified]` and needs a person only because `tests_pass` is UNKNOWN. The edited test command is not mentioned.
- Policy with `allowed_test_commands`, `min_tool_version` and `require_gate_inputs` set, `--verify require`: still `[verified]`, and now also lists the reason that the gate ran a test command set in the workflow file which the policy does not list.
Limits: this pull request was already UNKNOWN, so the new rule added a reason but did not change the outcome; one case, same-repository, public repository. Fork pull requests and private repositories remain untested.

## 13. Experiment 5, the private repository (2026-11-04, private user-owned `agentvow-live-test2`, `gate-attest.yml` at `88f20b7`)
Replay and decide succeeded; the `attest` job failed at `actions/attest-build-provenance` with: "Failed to persist attestation: Feature not available for user-owned private repositories. To enable this feature, please make this repository public." So no attestation exists for a user-owned private repository, as the design expected, and the job (and the workflow run) is marked failed even though the decision is unaffected (`decide` does not depend on `attest`). Consequence: `queue --verify` cannot authenticate receipts there; in `report` they show as not authenticated and in `require` they need a person. Not tested: an organisation-owned private repository on GitHub Enterprise Cloud (the documented route), where attestations should work.
