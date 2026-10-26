# Agentvow control plane service (phase 1)

Receives receipts from the gate workflow, checks them against GitHub, applies the repository's policy read from its default branch (the gate workflow's local decision reads the pull request's base branch; for a pull request into the default branch they are the same file), and publishes the check run `agentvow/evidence`. It stores receipts only (verdicts, counts, category names) and never executes customer code. See `docs/CONTROLPLANE_PHASE1.md` for setup, environment variables and what is not yet verified.

Run the tests: `python -m pytest tests/test_cp_service.py`. Operator commands: `python -m controlplane.service.cli --help`.
