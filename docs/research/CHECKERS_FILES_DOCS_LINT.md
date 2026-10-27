# Three new statement checkers: files, documentation, lint (2026-10-27)

**Why.** `AGENT_STATEMENT_COVERAGE.md` found that about 70% of what agents say in their final message had no verdict, and that 14% could be covered by cheap deterministic checkers. This adds those three. No LLM is in the verdict path: statements are found by rules, and the repository, git and the linter decide.

## Research gate
Nothing here is research-critical. "Which files changed" is `git`'s own change list; running a linter is what CI and pre-commit already do. The only open question (whether a ledger of confirmed / contradicted / unchecked statements changes what a reader decides) stays "Potential gap requiring further verification" in `NOVELTY_BOUNDARY.md`. No novelty is claimed for the checkers.

## Design
| kind | what the agent says | what decides |
|---|---|---|
| `files_scope` | "added `x.py`", "fixed it in `x.py`", "removed `y.py`", "did not touch `z.py`", "left `z.py` alone" | git's change list for this change (committed since the base, uncommitted, untracked) |
| `docs_updated` | "updated the README", "added a changelog entry", "documented it in the docs" | whether a documentation file (README*, CHANGELOG*, `docs/`, `.md`/`.rst`) is among the changed files |
| `lint_clean` | "`ruff check` passes", "ruff format is clean", "black and flake8 are clean" | the named linter, run in the test sandbox (repository read-only, no network) on the changed Python files |

Rules that keep false mismatches rare:
1. **Only a verb that directly governs a backticked path counts.** "Added `x` support to `f.py`" and "fixed `g` in `f.py`" do; "modeled on the existing `f.py`", "`f.py` imports `g`", "copies `a.sample` to `config.env`", routes like `/restore`, branch names and anything under `.agentvow*` do not. A negation the extractor does not understand produces no claim.
2. **Ambiguous is UNKNOWN.** A bare file name that several files share, or a path git ignores, gives UNKNOWN, never CONTRADICTED.
3. **Documentation claims are scoped.** "README" needs a README to have changed. "Documentation" with only Python files changed is UNKNOWN (the agent may mean docstrings, which this does not read). A changed documentation file is NOT_CONTRADICTED, not support: it does not show the text says what the agent described.
4. **Lint results carry the tool version.** A finding is the tool's output on this machine with the repository's own configuration, and a different version may disagree. This is the lesson of foamlib#453 (a false stop from dependency drift): the version is always stated, and a missing tool, a missing sandbox or an error is UNKNOWN.
5. **Supported tools:** `ruff check`, `ruff format`, `black`, `flake8`. Any other named tool (mypy, pylint, pre-commit, "the linter") gives UNKNOWN "no runner". Nothing is installed or vendored; a tool must already be on PATH.
6. **Safety of running a linter.** It runs in the same sandbox as tests with the repository bound read-only (a new `readonly` option in `runner.wrap`, Linux only needed) and only scratch writable; caches are redirected to scratch; file names starting with `-` are dropped; `--` precedes the file list.

**A disagreement with git's change list is a mismatch for a person, not CONTRADICTED.** For files and documentation the verdict is UNKNOWN with attention (overall status REVIEW REQUIRED; under the default policy a person must acknowledge), because on real pull-request descriptions the measured precision of such mismatches does not support blocking a merge (below). Only the lint result, which is a tool's own output, can be CONTRADICTED. Verdict mapping uses the four existing verdicts; the checks fit the existing policy, receipt and explanation without new rules. The feedback text sent back to the agent has a fixed reason per kind and never repeats repository strings.

## Tests (40, `tests/test_statement_checkers.py`)
Extraction (including the precision traps above), each file/doc/lint verdict on a real temporary git repository, a real `ruff` run in the sandbox (skipped when ruff or the sandbox is absent), the repository left untouched by the linter, the read-only bind, and the feedback text. Mutation checks: 11 deliberate breakages of the new code (the unchanged-file contradiction, the ignored-file guard, the ambiguity guard, the second-verb stop list, the README target, the docstring guard, lint CONTRADICTED, named-file scoping, option-like names, the unchecked-duplicate guard, the `.agentvow` exclusion) were all caught by at least one test after two tests were added for survivors.

## Evaluation on the 22 valid B6 messages
- **File claims extracted: 18.** Of my 42 hand-labelled file statements, 15 were extracted; 3 further extractions were valid and unlabelled ("Added `…/input_inspector/README.md`" and similar). No extraction was wrong.
- **Recall is low by design (15 of 42).** The labelled statements the extractor skips are mostly verb-less ("`sshpilot/config.py`: imports …" or "… in `file.py` didn't handle …"), which could also be descriptions, not claims of change. Making those count would raise recall and false positives together; I did not tune against these messages.
- **Verdicts on the stored change lists: 16 NOT_CONTRADICTED, 2 CONTRADICTED.** The 2 are an artefact: the stored list (a `git status` summary) names an untracked directory instead of its files, which the real change list never does. So: no true contradiction among 18 claims, consistent with the earlier 42-of-42 manual check.
- **Documentation: 2 extracted** (both README claims, both agree). , not yet executed against the original repositories (they are not stored locally); one spurious `pre-commit` extraction in a sentence with a contraction was found and fixed (contractions count as negations).
- **Lint: 3 statements extracted** (`ruff check` x3; the `ruff format` and `pre-commit` extractions disappeared when contractions were treated as negations), not executed against the original repositories (not stored locally).
- **Coverage effect.** The tool produced 26 findings (25 `tests_pass`, 1 `backward_compatible`) in the 22 messages before and produces 49 now: 18 `files_scope`, 3 `lint_clean`, 2 `docs_updated` more; 20 of 22 messages now have at least one finding, up from the messages with a tests claim. Against the 152 labelled statements, 23 new statements get a verdict path, not the 22 "feasible" ones: the overlap is partial, because extraction is stricter than my labels. The earlier estimate of "roughly 65%" assumed full recall and is withdrawn; the realised increase is about 15 points of the 152 statements.

## Evaluation on real pull-request descriptions (2026-10-27)
Corpus: AIDev agent pull requests (71,677; Copilot, Codex, Devin, Cursor, Claude Code, Jules). `research/checkers/pr_body_precision.py` samples PRs per agent that contain such a statement, runs the extractors with the PR's own file list from the GitHub API (and the repository tree for name ambiguity), and writes every verdict; **I read every flagged mismatch by hand** against the PR's real file list. Raw API answers and rows stay local (`data/checker_eval/`).

| round | fresh PRs | flagged mismatches | judged real | false alarms and their cause |
|---|---|---|---|---|
| 1 (development) | 208 | 9 files + 37 docs | 5 of 9 files; docs 0 of 37 usable | verb after a noun ("the Dockerfile created `.env`"), "removed a test case from `x`", unticked template checkboxes (25), code documentation (XML, JSDoc), a directory named without its parent |
| 2 (held out) | 300 | 14 + 1 | 9 of 15 | content written into another file (`.venv/` into `.gitignore`), "a documentation reference", a bare name that also exists elsewhere |
| 3 (held out) | 300 | 17 + 2 | 12 of 19 | a bare extension (`.js`), "linking to the README", an included header, "references to", the 3,000-file cap of the GitHub list |
| 4 (held out) | 347 | 13 + 3 | 11 of 16 | a pattern for many files (`.module.css.d.ts` files), a name used as an adjective ("an `llms.txt` route"), "documentation publishing workflow", a docs configuration file, shorthand paths |
| 5 (held out) | 276 | 9 + 2 | **10 of 11** | markdown emphasis between a path and "to `.gitignore`" |

After each round I fixed the causes found and added a test for each; rounds 2 to 5 were drawn after the previous round's fixes and exclude every earlier PR. Read the table as: precision of flagged mismatches improved from about 60% to 91% in the last, small round (95% interval on 10 of 11: roughly 59% to 100%), and **every round still found a new kind of false alarm**. That is why a mismatch asks a person and does not block. The real mismatches are mostly the description naming a file the pull request does not touch (a wrong or invented path, a file the description says it created that is absent, `uv.lock` said to be updated while only `pyproject.toml` changed). I cannot tell from the diff whether the description or the change is wrong, only that they disagree.

Other numbers from the five rounds (about 1,300 pull requests, 1,970 extracted statements): 868 file statements, 707 documentation statements, 393 lint statements. Most documentation statements agree (NOT_CONTRADICTED) or are UNKNOWN. **Of the 393 lint statements only 41 (10%) name a tool Agentvow can run** (`ruff check` 24, `black` 12, `flake8` 5); 285 say only "lint passes" (UNKNOWN: which linter?), and the rest name mypy (15), pre-commit (43), isort (2) or another language's tool. For real pull requests the lint checker therefore covers a tenth of lint statements. Resolving a generic "lint" from the repository's own configuration (`[tool.ruff]`, `.flake8`, `.eslintrc`, `.golangci.yml`) is the obvious next step and is not built.

## Limits
Rule-based extraction misses most phrasings (it only finds explicit verbs next to backticked paths); one tool version on one machine decides lint; the file check says which files changed, not what changed in them; the base the change is measured against must be the right one (a statement about an earlier turn's work can look contradicted against a later base); the Linux sandbox path for lint is untested until CI runs it.
