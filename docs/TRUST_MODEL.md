# What each artifact proves, and what it does not

Agentvow produces several kinds of evidence that are easy to confuse. Reports and receipts keep them apart; none of them is a single "verified" flag, and none of them means the code is correct.

| Artifact | What it can establish | What it cannot establish by itself |
|---|---|---|
| **Local signed capsule** (`.agentvow/`, HMAC key outside the repository) | The local Agentvow process recorded a particular package list for a particular state and sealed it with a key that stays on that machine | That the captured environment was correct, complete or free of hidden state; anything to a third party (the key is never shared) |
| **Portable capture bundle** (`agentvow-capture/1`, unsigned) | The package pins in it can be checked against the exact files (git tree hash recomputed by the verifier) and replayed independently; a different tree is refused | That it came from the agent's real environment. **It is supplied, not authenticated**: whoever made it chose the packages |
| **Replay result** (a context's test outcome) | The scoped target tests passed, failed, did not run or were inconclusive in a clean sandbox built from the stated context | That the tests are sound, that the code under test did not influence its own output, or (when pinned packages were left out) that the complete captured environment was reproduced |
| **Receipt** (`agentvow-receipt/1`) | A minimal record (verdicts, counts, category names, provenance fields) bound to a content hash of the files | Anything about the code beyond what the replay measured; the receipt is only as honest as the job that made it |
| **Control plane check** (`agentvow/evidence`) | A trusted, commit-pinned workflow submitted a receipt for a state GitHub confirms, and the repository's policy was applied; acknowledgements are by named, permitted people | That the tested code cannot lie to the test harness; that a fork pull request was checked (it is not); anything about code the tests do not run |

## Provenance fields in a receipt claim (0.4.3 and later; kept separate on purpose)
`capture_source` (`""` none, `local`, `bundle`): where the capture came from. `capture_authenticated` (`true` local capsule, `false` supplied bundle, `null` none). `state_binding` (`capsule`, `git_tree`, or empty). `partial_replay` and `dropped_pins`: whether the replay left out pinned packages pip could not install on the runner. `basis`: the support basis the finding names (`captured_environment` or `agent_recipe`; a result from the project's own setup is reported in the evidence pack, not as a claim basis). The verdict (`CONTRADICTED`, `SUPPORTED_BY_PRIOR_EVIDENCE`, `NOT_CONTRADICTED`, `UNKNOWN`) is the replay result as the claim sees it. The policy can require acknowledgement for a supplied (unauthenticated) capture and for a partial replay; both are on by default.

## Meaning of the three outcomes
* **Contradicted:** observed evidence conflicts with the claim under the stated conditions. It cannot be acknowledged away.
* **Supported (under stated conditions):** the specified check was independently reproduced and supports that claim within its scope. Never "the code is correct".
* **Unknown:** the evidence is insufficient to confirm or contradict the claim, or the replay could not run (missing dependency, credential, network, a failed install). UNKNOWN is a valid result and is never converted to support.

## Limits that govern the product language
A hostile `conftest.py` or test harness can print or return a passing result (pinned by `tests/test_hostile_harness.py`: fake summaries and forced exit codes are caught or give UNKNOWN; a fully deceptive harness is believed. The finding says so only when the change modified an existing test file or touched a file that runs when tests start (`conftest.py`, `sitecustomize.py`, `usercustomize.py`, a `.pth` file, a test package's `__init__.py`); the same code hidden in ordinary source or in an extra test file is believed with **no** warning: `tests/test_hostile_harness.py` pins both); Agentvow's replay is independent of the agent's *claim*, not of the repository's own test code. The sandbox limits what the code can touch; it does not make a passing result true. See `docs/SECURITY_MODEL.md` and `docs/EVIDENCE_AND_LIMITS.md`.

## Who produces the receipt
The sha pin fixes which *workflow* the control plane trusts, not the Agentvow version it installs. The service therefore refuses receipts whose `tool_version` is below a minimum (default 0.4.3, `AGENTVOW_CP_MIN_TOOL_VERSION`), so a caller cannot choose an older, weaker version through the `agentvow-version` input; the receipt is still built by code that runs next to the pull request's code (see the residual risk in `docs/CONTROLPLANE_THREAT_MODEL.md`).
