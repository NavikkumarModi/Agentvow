# Agentvow 0.2.0

Agentvow checks what a coding agent says it did (tests pass, backward compatible, no downstream impact) against what it can independently observe in your repository. It informs you; it never approves, rejects or merges anything, and no language model decides a verdict. This is still a prototype, not a safety verdict.

## New
- **Capture at claim time** (`agentvow capture`, `check --from-capsule`, hook `--capture`): records the Python packages of the agent's environment (signed, bound to the exact commit and working tree; never environment values) and replays the tests in a clean sandbox built from them. Fails closed when no capsule matches the state. See `docs/CAPSULES.md`. In a pre-registered feasibility study (40 random agent-PR tasks, 22 valid runs, one model, Python packages only) capture reproduced 20 of 22 passing results against 12 of 22 for rebuilding the environment from the repository; reproducibility is not correctness.
- **Changed-line coverage** (`--changed-coverage`): says how many of the changed executable source lines the tests actually ran and names the lines and files no test reached; informational, never changes a verdict.
- **Claims with preconditions** (`--recipe`): an agent declares its setup and test command in a small validated file; Agentvow replays only that in a sandbox. Includes a `prepare` step, test-selection guards, monorepo sub-package support, and a session audit (`audit-env`).
- Clearer failure messages: a resource guard that stops an install is reported as such (not as a missing dependency); `AGENTVOW_MAX_ENV_MB` raises the 700 MB environment limit; a declared `HOME` is rejected with the reason; an omitted `pytest` is supplied and stated.

## Fixed
- A flattened `pip install -e <dir>` that installed an unrelated PyPI package in monorepo replays; Linux sandbox DNS (`/run` hidden); a plain folder named like an installed package tripped the isolation check.

## Known limits
Python repositories only; capture covers Python packages, not system packages, services, generated files or secrets; running tests needs macOS or Linux; hooks are a Preview feature in some agents; the studies behind these features are small and Claude-only (`docs/research/`).
