# Agentvow 0.4.0

Agentvow checks what a coding agent says it did against what it can independently observe. It informs you; it never approves, rejects or merges, and no language model decides a verdict. Still a prototype, not a safety verdict.

## New
- **A portable capture and a key-less verifier.** `agentvow capture --export bundle.json` writes an unsigned bundle of the agent's pinned Python packages, bound to the git tree hash of the exact files; `agentvow check --from-capture bundle.json` replays it and **refuses if the files differ in any way**. It needs no signing key (the local key never leaves the machine). The result is labelled "supplied, not authenticated": whoever made the bundle chose the packages installed, so the default policy asks a person to acknowledge it.
- **Receipts and a policy engine.** `agentvow receipt` writes a minimal record (verdicts, counts, category names; no source, free text, paths or environment values). `agentvow policy evaluate` turns it into allow, block or needs-acknowledgement under a policy file (`agentvow policy init` prints the default). A contradiction always blocks and cannot be acknowledged; an acknowledgement counts only from a listed person for exactly that receipt; malformed receipts and unknown verdicts block.
- **The gate workflow** `.github/workflows/gate.yml` (three jobs; no job that runs pull-request code holds a credential; policy read from the base branch; fail closed). See `docs/GATE_WORKFLOW.md`.
- **`agentvow pilot-report`**: a mechanical evidence report over a directory of receipts, with a limits section that claims no defects prevented and no time saved.
- Security fixes found by an adversarial review of this release before publication (planted `json.py` / `pip` in a checkout, fail-open policy cases, git-config-dependent hashes, markdown injection in reports) are described in the changelog.

## Known limits
Python repositories only; capture covers Python packages, not system packages, services, generated files or secrets; running tests needs macOS or Linux; the hook shapes are verified for Claude Code 2.1.263 and (earlier) Copilot in VS Code only; the three-job gate workflow has not yet run on GitHub and its OIDC path and the hosted control plane do not exist yet (the repository contains only a mock, not shipped in the package); results behind the product claims are feasibility-scale and reproduction is not correctness.
