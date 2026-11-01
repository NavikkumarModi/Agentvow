# TypeScript API diff: documentation read and no-build prototype (2026-11-01)

Step 1 of `API_DIFF_TOOLS_SURVEY.md`. **Exploratory; not pre-registered; precision not measured against independent ground truth; not integrated into the package.** Prototype `research/ts_apidiff/exports.js` and `run.py`; raw output `docs/research/apidiff_bakeoff_data/ts_bakeoff.json`.

## What the primary documentation says `[read]`
Pages read: api-extractor.com landing, overview, "invoking", "configure API report", the `api-extractor.json` reference, and the README of `@clerk/break-check`. Not read: break-check's source, the `run` command page, the message reference.
- `@microsoft/api-extractor` 7.60.1 is **MIT** (checked in the repository's `LICENSE` and `package.json`); `typescript` is Apache-2.0.
- **It needs a built `.d.ts` entry point, not source** ("TypeScript source files are not directly analyzed"), so the project must be compiled first with `declaration: true`. A missing or broken `.d.ts` is not described on the pages read.
- **It does not classify breaking changes.** It writes an API report (`.api.md`) and fails a production build when the regenerated report differs from the committed one; breaking changes are found by diffing that report in git.
- Whether it runs project code (plugins, scripts) is **not stated** on the pages read; building the project with `tsc` does run the project's toolchain.
- `@clerk/break-check` (MIT, 3 stars) wraps it: snapshots the public `.d.ts` surface of a baseline and the current state (it needs both built, via git worktrees or a stored snapshot) and classifies changes by documented rules (removed export or member, required parameter added, optional made required, parameter or property type changed, modifier changes: breaking; optional additions: non-breaking). Limits it states: generics are compared as text, any type change counts as breaking, subpaths it cannot process are skipped with a warning.

## Consequence for Agentvow
The full-fidelity route needs the pull request's project to **build** in the sandbox (dependencies installed, `tsc` run), which is the same hard step that leaves a third of Python pull requests unscorable, and which executes repository tooling. A no-build route can still catch the clearest breaks syntactically, as the Python check does.

## The prototype
`exports.js` parses one TypeScript file at two versions with the TypeScript parser alone (no type checking, no resolution, nothing installed from or run from the repository) and reports **breaking** (removed export or member, parameter removed, required parameter added, optional made required, rest-ness changed, property made required or readonly; rules taken from break-check's documentation) and **changed** (declared type text differs, reported separately because only text is compared), with wildcard re-exports and parse errors listed as gaps.

## Measurement (same method as the Python bake-off)
The 360 pull requests with a backward-compatibility claim that change no Python file; 135 have non-test `.ts`/`.tsx` files that existed at the base commit (576 files; the rest change only tests, `.d.ts`, JavaScript or non-code). **19 of 135 (14%) have a breaking finding**, 18 more only a type-text change, 12 have gaps (wildcard re-exports or parse errors). For comparison the Python tools flag 19% (28 of 149).
Findings: 79 removed names, 14 removed files, 5 parameter changes, 2 properties made required, 1 kind change.

**Is a flagged file a public API?** The main weakness. For the 19 flagged pull requests I looked up the nearest `package.json` at the head commit: **8 are in packages marked `private`** (applications, not libraries: no public API exists), 1 in a package with no entry field, and 11 in packages that declare an entry (`main`, `types`, `exports` or `module`). A declared entry does not mean the changed module is reachable from it: for example a removed helper in a rulesync utility file or in an Obsidian plugin's internals is internal, and the plugin `main` is a bundle, not an API. So at most about 11 of 19, probably fewer, concern a public surface; the true count is not established. I read file lists, not the code of each case, so I make **no precision claim**.

## Decision
- The syntactic diff finds removals and signature changes without a build, but **without entry-point resolution it cannot say which names are public**, so used as-is it would over-flag application code and internal modules.
- Needed before integration: (1) a package filter: a change confined to `private` packages gets UNKNOWN ("no public API declared"), not a finding; (2) reachability from the declared entry through the entry file's re-exports, syntactically; (3) a second look at the remaining flagged pull requests by reading the code, with the result reported as agreement with my reading, not as independent verification.
- Keep the break-check/api-extractor route as the higher-fidelity option for packages that build in the sandbox; do not depend on break-check (3 stars, young).
- Nothing was added to the Agentvow package; no release is needed.
