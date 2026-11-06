# Agentvow 0.5.3

Agentvow checks what a coding agent says it did against what it can independently observe. It informs you; it never approves, rejects or merges, and no language model decides a verdict. Still a prototype, not a safety verdict.

## What changed
**Nothing in the code.** The package and the VS Code extension behave exactly as in 0.5.2 (same checks, same receipts, same policy keys). This release only changes the README, the version number and the changelog, so that the PyPI and Marketplace pages state the project honestly.

## The narrowed headline
A pre-registered study measured whether the sandbox replay earns its place as a headline capability. On 60 agent pull requests with no CI verdict, in 51 repositories set up with no configuration:
- the replay reached SUPPORTED or CONTRADICTED for **4 of 60 (6.7%)** (the threshold set in advance was 40%); 39 stayed UNKNOWN, mostly because the environment could not be rebuilt;
- it stopped **0 of 4** planted single-line faults (threshold 60%; too few to conclude);
- precision of its contradictions is **undetermined** (2 decided results, 4 needed).

By the pre-registered rule, the README now presents the evidence record, UNKNOWN as an outcome and receipt authentication as the core, and the replay as an optional extra most useful where the agent's own environment was captured. Details, including two classification errors found during the study and corrected before the final numbers: `docs/research/REPLAY_VALUE_RESULTS.md`.

## Not claimed
No novelty is claimed for the replay. The author reviewed the study; an independent reviewer has not.

## Known limits
Unchanged from 0.5.2 (`docs/RELEASE_NOTES_0.5.2.md`): verification of receipts needs the public-repository attestation setup, fork pull requests and organisation-owned private repositories are untested.
