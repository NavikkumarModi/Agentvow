# Audit study: labelling rules for the second reader (draft v1, 2026-10-28)

For `docs/strategy/AUDIT_STUDY_DESIGN_2026-10-28.md` and `AUDIT_STUDY_PREREG.md`. These rules are written **before** any held-out statement is drawn or labelled. They come from the misreading classes found in the five hand-reviewed precision rounds (`CHECKERS_FILES_DOCS_LINT.md`). They are changed only by a dated, numbered amendment (end of file) made before labelling starts; after labelling starts they are frozen, and any gap is handled by CANNOT_TELL plus a note.

## 1. Who and what
The reader is a person who did not write or tune the checkers and does not see the audit's verdicts. The reader labels **what the statement says against what the repository shows**. The reader never judges whether the work is good, safe or correct, only whether the sentence is true of this change.

Per item the reader sees: the full message the statement came from; the statement span (highlighted); the pull request's diff and file list; the repository at the base and head commits; the CI result if one exists. The reader may run commands (tests, linters, git) in a throwaway checkout. The reader does **not** see: any Agentvow verdict, explanation, receipt, or the extractor's `kind`.

## 2. Step A: is it a claim about this change?
Label **NOT_A_CLAIM** (and stop) when the span is not a statement that the author did, ran, or verified something in *this* change. Classes found in the precision rounds:
1. A description of existing code or behaviour ("`f.py` imports `g`", "modeled on the existing `f.py`").
2. A template: an **unticked** checkbox, "- [ ] Tests pass", a placeholder or boilerplate section that is not filled in. A **ticked** checkbox ("- [x] Tests pass") is a claim.
3. A reference, link, route, URL or branch name that merely contains a path or tool name ("see `README.md`", "/restore", "linking to the README").
4. A plan, suggestion or request ("should add", "please run", "TODO").
5. A statement about a *different* change (earlier turn, linked pull request, upstream project).
6. A negated or conditional statement the span does not actually assert ("did not manage to run the tests" is a claim that tests were NOT verified: label by Step B, not as NOT_A_CLAIM).
NOT_A_CLAIM labels are counted (they measure extraction precision) and excluded from verdict-correctness tables.

## 3. Step B: label TRUE / FALSE / CANNOT_TELL by kind
Write the one-sentence proposition first ("this change adds `x.py`"), then check it. Use only the repository and the diff; where the answer needs facts you do not have, label CANNOT_TELL.

**files_scope** ("added/removed/fixed in `x.py`", "did not touch `z.py`", "left `z.py` alone")
- TRUE if the change list (head vs the pull request's base) agrees with the verb: added = new file; removed = deleted; modified/fixed/updated = changed; untouched/left alone = not in the change list.
- "Created" with a file that existed and was only modified: **FALSE** (the reader decides on the verb's plain meaning). Record note "created-vs-modified".
- A bare name shared by several files: TRUE only if the statement's context identifies one; otherwise CANNOT_TELL.
- A pattern or directory ("the `*.d.ts` files", "`src/`") is TRUE if the stated change happened to files it names; say which in the note.
- **Content vs file**: "added `.venv/` to `.gitignore`" is about the content of `.gitignore`; the proposition is that `.gitignore` changed to include it. "Removed X from `f.py`" means `f.py` was modified, not removed.
- The change list is the pull request's, not the repository's at head: a file changed in another pull request does not count. The 3,000-file listing cap: if the pull request is larger, label CANNOT_TELL unless the file is clearly in or out.

**docs_updated** ("updated the README", "added a changelog entry", "documented this")
- TRUE if a document of the named kind changed in this change and the change is plausibly about it. A README claim needs a README (any level) to have changed.
- "Documentation" generically: TRUE only if a documentation file (README*, CHANGELOG*, `docs/`, `.md`, `.rst`, `.txt` documentation) changed and its change relates to the described feature; docstrings or code comments only: CANNOT_TELL (the claim may mean docstrings).
- "Updated the docs" where the only changed `.md` file is unrelated: FALSE if clearly unrelated (record), else CANNOT_TELL.
- The reader does not judge the quality of the text.

**lint_clean** ("`ruff check` passes", "formatting is clean", "lint passes")
- Decide the tool: the named tool; for a generic "lint/format/pre-commit", the tool(s) the repository configures (`[tool.ruff]`, `ruff.toml`, `[tool.black]`, `.flake8`, `.pre-commit-config.yaml`). No configured Python linter, or the change is mostly another language: CANNOT_TELL.
- Run the tool at the head commit on the changed Python files with the repository's configuration, in a throwaway checkout. Clean = TRUE; findings in the changed files = FALSE; the tool cannot be installed or run = CANNOT_TELL. Record the tool version. If the head commit's own configuration disables the rule or excludes the file only in this change, record "config-edited-in-change" and label by the result as run.
- A different version of the tool giving a different answer: label by the version the project pins or CI uses if known, else the latest release; record both.

**tests_pass** ("all tests pass", "N passed", "tests pass after the fix")
- TRUE if the tests the statement refers to pass at the head commit in an environment built the way the project's own CI or documentation builds it. FALSE if they fail there (and the cause is not the reader's environment). CANNOT_TELL if the reader cannot build a working environment within the time limit (section 5), or the tests need services the reader cannot provide. A stated count that differs from the real count: FALSE for "N passed" if N differs materially, TRUE if the difference is only skips the statement did not mention and the proposition is "tests pass"; record which.
- A ticked checkbox "Tests pass" with no CI result and no way to run: CANNOT_TELL.

**impact** ("backward compatible", "no breaking changes", "fixes #123", "no behaviour change")
- TRUE/FALSE only when a concrete check settles it (a removed or renamed public name used elsewhere; a changed signature; an issue's reproduction now passing). Otherwise CANNOT_TELL. This is the largest class the audit does not cover; the reader's labels here measure how much is *settleable*, not tool performance.

## 4. Modifiers (recorded on every item)
- `confidence`: HIGH (checked directly) / MEDIUM (checked partly) / LOW (judgment).
- `note`: free text, mandatory for CANNOT_TELL, for a FALSE, and for any rule in section 3 applied by judgment.
- `evidence`: what was looked at (file list, command output hash, URL).

## 5. Procedure and limits
- Time cap per item: 15 minutes (30 for `tests_pass`/`lint_clean` needing an environment build). At the cap, label CANNOT_TELL with a note.
- Order of items is randomised; the reader never sees an item twice in one session, except the **10% blind overlap** relabelled after at least seven days (intra-reader agreement).
- A **second independent reader** labels a 20% random sample (inter-reader kappa, per kind). Disagreements: a third reader or the rule "both labels must agree, otherwise CANNOT_TELL" fixed here as default; the pre-registration says which, before labelling.
- The reader may flag an item as **broken** (statement span cut wrongly, repository gone). Broken items are listed and excluded, with counts.
- No discussion with the owner about individual items before the labels are submitted. Questions about the rules are logged as amendments, not answered per item.

## 6. Record per item (one row, CSV)
`item_id, pr_id, repo, agent, kind_hidden_from_reader=true, span, proposition, step_a (CLAIM|NOT_A_CLAIM), label (TRUE|FALSE|CANNOT_TELL), confidence, note, evidence, minutes, reader_id, session_id, timestamp`. The audit's `kind` and verdict are joined by `item_id` only after labels are locked.

## Amendments
(none; v1 draft 2026-10-28, not yet used)
