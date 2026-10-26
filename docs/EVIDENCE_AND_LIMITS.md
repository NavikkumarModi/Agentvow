# Evidence, scope and limits

Moved out of the README so the front page can describe what the tool does. Nothing here has been softened or removed: read it before relying on a result.

## The capture studies (the replayability evidence; feasibility scale; details in `docs/paper/SHORT_MSR2027.md` and `docs/strategy/PRODUCT_EXPLORATION_2026-10.md`)
These measure whether a result can be **replayed**, not whether code is correct, and not whether replay finds more real defects. One model family (Claude Code), Python only, small repositories, authored by the same person who built the tool.
| Study | Result | Caveat |
|---|---|---|
| B6 (pre-registered): 22 valid agent runs of 40 | Replaying the agent's captured packages reproduced **20 of 22** passing results; a repository-only zero-config reconstruction reproduced **12 of 22** (capture only 8, reconstruction only 0) | the comparator is weak by design; the rule was met at the minimum power (22 valid runs against a floor of 20); 21 of 22 from one PR-author family |
| E3: a stronger reconstruction baseline (CI files, Dockerfile, requirements) on the 18 re-runnable runs | capture **16 of 18**, strong baseline **9**, zero-config ladder 10; capture only 7, baseline only 0 | the baseline reader was frozen before the run but the author had seen B6; it is one reasonable strong baseline, not the only one |
| E1: the same captures replayed 8 days later | **16 of 16** testable captures still passed; the pre-registered threshold (18 of 20) could not be met because 4 runs are not re-runnable from the saved patch | stability over weeks and the +30-day point are not shown |
| E2: the captures replayed on Linux (aarch64 container, same Python minor) | **15 of 16** passed; the one flip was a platform-specific pin with no Linux distribution (`pymsalruntime`), which the product now leaves out and reports as a partial replay | one Linux flavour, not x86-64, bubblewrap inside a privileged container |
| E5: planted faults under the captured and the project-native context | 9 faults ran (7 had no plantable line, 4 runs not re-runnable); 3 flagged by at least one context: 2 by both, **1 by captured only**; pre-registered reading **weak** | faults are authored by us, operator flips on added lines only; capture's contribution here was "the context could run at all", not "it sees more faults when both can run"; faults that only a newly added test catches stay UNKNOWN by design |

What these support, and no more: the agent's recorded Python packages usually let a clean sandbox replay its passing test result, and the repository alone often does not say how. They do **not** support: that captured replay detects more real defects, that agents are dishonest, that a reproduced test result proves correctness, or any claim about other languages, agents or system-level dependencies.

## Earlier detection and coverage studies
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
* Control plane service (`docs/CONTROLPLANE_PHASE1.md`): built, reviewed three times adversarially (findings fixed, `docs/review/CONTROLPLANE_REVIEW_2026-10-22.md`) tested against fakes and run once against real GitHub through a throwaway App (`docs/LIVE_TESTING.md`); not deployed, no fork test.
* Capture vs repository-only reconstruction: a feasibility result on small samples (`docs/paper/SHORT_MSR2027.md`), not a general claim.
