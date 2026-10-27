# What agents say, and what we can check (2026-10-27)

**Question.** In the final messages of the 22 valid Stage B6 runs, how many checkable statements does an agent make, and for how many does a deterministic checker exist (so a report could say confirmed, contradicted or "nobody checked")? Scripts: `research/autonomy/b6_statements.py` (the labels), `research/autonomy/claim_coverage.py` (counts and the file checks). The final messages stay local (`data/preconditions/stageb6_results.jsonl`); the labels hold short paraphrases only.

## Method and honesty notes
- I split each message into atomic statements and gave each a class. **The labels are mine, unreviewed by a second labeller**, so counts are approximate (±10%). Notes to the user and offers are excluded.
- "Checker level" belongs to the class, not to a statement: *today* = a checker exists and runs; *partial* = part of the statement is replayed; *feasible* = deterministic and cheap but not built; *hard* = only some forms (signatures, new symbols) are checkable; *unverifiable* = explanation or process.
- **"Today" overstates the tool's output.** For these runs the tool produces one finding per message (the tests-pass claim, with the stated count). The 46 test and count statements collapse into at most 22 findings.

## Result: 152 statements, 6.9 per message
| checker level | statements | share |
|---|---|---|
| today (tests pass; stated counts) | 46 | 30% |
| partial (pre-existing failure, no regression, recipe or environment) | 32 | 21% |
| feasible, not built (files changed or left alone, docs updated, linter clean) | 22 | 14% |
| hard (what the change does) | 39 | 26% |
| unverifiable (root cause, process) | 13 | 9% |

- **Only about a third of what agents say is covered, and about half is covered even partly.** Everything else is reported as unexamined, which a reader cannot tell from "fine".
- The largest uncovered class is "what the change does" (39 statements, 26%). It is also the class where a wrong statement matters most, and it needs structural checks (signatures, new symbols, call sites) built one by one.
- The cheapest gain is the 22 feasible statements (14%): files changed or left alone, documentation updated, linter clean. Each is a few lines of deterministic code.
- 12 of 152 statements are root-cause explanations. They can only ever be UNKNOWN, and a ledger should say so rather than imply they were looked at.

## File checks run on the stored changed-file lists
42 statements carried a file expectation (a file changed or left alone). **All 42 were consistent with the stored changed-file list; none contradicted.** Limits: for "what the change does" statements this only shows the named file was modified, not that the described behaviour is right; and the list is the working-tree status, which excludes the target tests the harness supplied. So this is a demonstration that the check is trivial, not a finding about agent honesty.

## Observations worth keeping
- One message states "two places" and then lists three changes (llm-subtrans#334). A checker over the change would see this; a test run does not.
- Agents mention unverifiable process claims rarely (1 of 152). The common unverifiable content is explanation.
- Statements about pre-existing failures (7) are the ones most likely to hide an agent's own regression, and the existing base-versus-head replay can check the "before" half.

## What this does and does not show
- Shows: on 22 honest runs from one agent family, a tool that only checks tests leaves roughly 70% of the agent's statements without any verdict, and the biggest gap is statements about what the code now does.
- Does not show: that the uncovered statements are false (the 42 file checks found none), that the proportions hold for other agents or longer messages, or that a ledger changes what a reader decides. Whether it does is the human-study question already in `NOVELTY_BOUNDARY.md`.
- Prior art: a claim-checking stop-hook loop exists (listed in `NOVELTY_BOUNDARY.md`); breadth of claim classes and explicit "nobody checked" accounting remain a **potential gap requiring further verification**.
