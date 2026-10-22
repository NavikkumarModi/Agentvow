# Evidence, scope and limits

Moved out of the README so the front page can describe what the tool does. Nothing here has been softened or removed: read it before relying on a result.

## Evidence so far (and what it does not show)
- Agent PR claims in the wild (688 public Python PRs from five agents that claim tests pass): CI test jobs could judge 33%; of those about 27% had a failing test job (clustered in a few repositories; not an agent ranking). `docs/research/CI_CLAIM_STUDY.md`
- Local runs on unfamiliar repos with automatic setup reached a verdict for 29% of PRs; half stopped on a missing dependency. `docs/research/LOCAL_COVERAGE.md`
- Detection on real agent PRs (pre-registered v2, 140 PRs): the suite could be run locally for 19% of PRs; among the 13 CI-failing PRs that ran, 2 real regressions were flagged as contradicted (4 with the `review` policy), none was declared fine, and 1 of 14 CI-passing controls got a false alert (a dependency-version mismatch, since guarded). Small, clustered, in-sample for the follow-up rules. `docs/research/DETECTION_V2.md`
- Planted faults (authored by us, 15 real PRs): 26 of 30 test-detectable breaks attributed, no false alarms. The zero-config setup could not run most real PRs (see the line above for what the runnable ones showed). `docs/research/PLANTED_FAULTS.md`, `docs/research/DETECTION_STUDY.md`
- Novelty is **not** claimed: the closest prior work (Assay, EA-Graph, backcheck and others) and what remains open are in `docs/research/NOVELTY_BOUNDARY.md`.

## Known limits
Python only for impact and API checks; claim extraction is rule-based (three claim types); CI job classification is by name; trivialised tests are not detected; tests that start daemons can hang under the sandbox (ends at `--test-timeout`); hooks and Copilot integration are Preview features and only the Copilot CLI engine inside VS Code has been observed live; Windows has no test sandbox (tests are refused there); the chat-injection routes go through the model; one annotator behind every hand-validated number.

## Safety details
Running tests executes the project's code. It runs in a sandbox: macOS `sandbox-exec` or Linux `bubblewrap` (`apt install bubblewrap`; on Ubuntu 24.04+ unprivileged user namespaces must be allowed, e.g. `sysctl kernel.apparmor_restrict_unprivileged_userns=0`; `agentvow doctor` tells you). Network denied, file writes only inside a throwaway worktree plus a private scratch directory, signing key and credential folders unreadable, whole process group killed on timeout; on Windows, or where no working sandbox exists, Agentvow refuses to run tests (static checks and CI reading still work; `agentvow doctor` says which). The Linux sandbox makes the whole filesystem read-only; the macOS one allows OS services by default (a review showed a Mach service could still write outside it; common helpers like `open`/`defaults`/`osascript` are blocked, which is not complete containment). Results are HMAC-sealed with a key outside the repository, which stops casual forgery and files copied from elsewhere, **but test results are only as trustworthy as the repository's own test code**: a hostile `conftest.py` can print fake pass counts. Treat a "no contradiction" on an untrusted repository accordingly. Text from agents and repositories is length-bounded, stripped of control characters and escaped in reports and in plain-text output. Full model, reviews and open weaknesses: `docs/SECURITY_MODEL.md`, `docs/research/RISKS.md`.


## Status of newer parts
* Gate workflow and receipts (`docs/GATE_WORKFLOW.md`): verified once on GitHub on a pull request of this repository; the real OIDC upload path is not yet verified.
* Control plane service (`docs/CONTROLPLANE_PHASE1.md`): built, reviewed twice adversarially (findings fixed, `docs/review/CONTROLPLANE_REVIEW_2026-10-22.md`) and tested against fakes only; never run against real GitHub, not deployed.
* Capture vs repository-only reconstruction: a feasibility result on small samples (`docs/paper/SHORT_MSR2027.md`), not a general claim.
