"""The Agentvow control plane, phase 1: a small service that never executes customer code. It receives receipts that a customer's own runner produced, authenticates the sender with a GitHub Actions OIDC token,
binds the receipt to the commit as GitHub reports it, reads the repository's policy from the BASE branch through GitHub's API, evaluates it with the open policy engine (agentvow.policy) and sets the required
check run. See docs/CONTROLPLANE_PHASE1.md. Dependencies (separate from the CLI package): cryptography, starlette, uvicorn."""
