# Review items and evidence coverage on the B1/B2 agent patches (post-hoc, 2026-10-10)

Question (owner, 2026-10-10): between "see only the outcome" and "read every line", how many things does a high-level human actually face, and how much of an agent's change does independent evidence exercise? Post-hoc descriptive analysis on data we already had; not registered; not a measure of human effort (that needs a human study). Scripts: `research/preconditions/count_review_items.py`, `coverage_of_changes.py`. Raw per-patch results stay local.

## 1. Items at each level (32 B1 patches; B2 is nearly identical)
| level | median | mean | max |
|---|---|---|---|
| lines changed | 17.5 | 23.0 | 83 |
| hunks | 2 | 3.2 | 13 |
| files | 1 | 1.4 | 4 |
| changed symbols (from diff context, approximate) | 1 | 2.3 | 10 |
| decision-relevant items (changed public symbol in a non-test source file; manifest/CI/config change; deleted or renamed file; new non-test file) | 1 | 2.2 | 10 |
Total 737 lines -> 70 decision-relevant items (about 10 per 100 lines). 22 patches have 1-2 items, 10 have 3 or more, none has 0. B2: 723 lines -> 71 items, same shape. **These patches are small enough (median 18 lines) that a human can read each one; the burden the owner describes would arise from the number of such changes in a stream, not from any single patch.**

## 2. How much of each change the independent tests exercise
Method: rebuild each task (base, target tests, saved patch), build the zero-config environment, run the target tests under coverage inside the sandbox, and check which **added** source lines (non-test, non-docs `.py`) are executed. 31 of 32 rebuilt (haliax#206: environment too heavy); untracked files the agent created are not in the saved patches and are not measured.
- **24 patches** had measurable added source lines: pooled **191/231 = 83%** executed; per-patch median 100%, **14 fully exercised**, 19 at 80% or more, 2 below 50% (pocket-pick#4 5/16, ComfyUI-Lora-Manager#487 7/18).
- **7 patches** had nothing measurable: 2 (sshpilot#105, #108) changed only non-executable lines (comments, annotations); **5 changed a source file the target tests never loaded** (open-webui-developer-toolkit#401 and #214, scoringengine#1045, b2500-meter#135, jaseci#1897; for the jaseci monorepo path a path-mapping artefact cannot be excluded).
- So: **16 of 31 patches have nothing left unexercised** (14 fully executed, 2 with no executable change); **15 of 31 (48%) contain changed source lines that the independent tests did not run** (10 partly, 5 not at all).

## 3. Reading
- A "tests pass" verdict, even when independently reproduced (31/32 here), says nothing about those 15 patches' unexercised lines. This is the part a middle layer should surface: not "30 files changed" and not "done", but "this change's lines in `X` were not run by any test I could execute".
- About half the patches can be left alone on this single measure and about half need attention, from data where every claim was true and every agent honest. At agent scale and with real defects the proportion needing attention can only be higher.
- Limits: executed is not asserted (a line can run without being checked); coverage is of the target tests only, not the whole suite; the patches are small and S1-selected; line-level, not behaviour-level; one model; untracked files and deleted-only changes unmeasured; the item rule is a proxy defined by me, not validated against human judgement.
- It does not show that a middle layer helps a human. It shows that a deterministic, independent, per-change measure exists, is cheap here, and splits real agent patches roughly in half.
