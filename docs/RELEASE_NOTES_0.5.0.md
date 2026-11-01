# Agentvow 0.5.0

Agentvow checks what a coding agent says it did against what it can independently observe. It informs you; it never approves, rejects or merges, and no language model decides a verdict. Still a prototype, not a safety verdict.

## New: the "backward compatible" check reaches TypeScript (optional)
When a description says a change is backward compatible and `.ts`/`.tsx` files changed, Agentvow compares each file with its base-commit text using the TypeScript **parser only**. Nothing is built, type-checked, installed or run from the repository. It reports removed exports or members, removed or newly required parameters and optional-to-required changes, and **counts only files that are public API**: in a non-private package and re-exported from the package's source entry. A private package, a missing entry, a file not re-exported from the entry, a file that does not parse and a removed file are reported as UNKNOWN or as a gap, never as a pass. Members moved to a base type are not reported as removed.
- Needs Node and the `typescript` npm package from the directory named by `AGENTVOW_TYPESCRIPT` (a `node_modules` directory) or the global npm root. **The repository's own `node_modules` is never used.** Without them the result for TypeScript files is UNKNOWN and says why.
- Like the Python check it raises attention and never decides by itself.
- **How well it works is not established.** On 135 real pull requests with a backward-compatibility claim it flagged 15; 3 were public API and 2 were clear public breaks. That is too few to estimate precision, and it has not been compared with tools that need a build (`docs/research/API_DIFF_TS_PROTOTYPE.md`).

## New: an optional second engine for Python (`pip install agentvow[api]`)
The static tool griffe (ISC licence) is run on the same files; its findings are added for files the built-in check found nothing in, marked `griffe, ...`. In a comparison on 620 files from 149 real pull requests it found three kinds of change the built-in check misses (members inherited from a removed base, dataclass fields, default values), about 3% more pull requests flagged (`docs/research/API_DIFF_BAKEOFF_PYTHON.md`). Without griffe nothing changes. The finding records which engines and versions ran (`api_engines`).

## Fixed
- `from __future__ import annotations` removed from a package `__init__` was reported as a removed public name.
- A changed `from x import *` in a package `__init__` was ignored silently; it is now reported as a gap (the names cannot be known from one file).
- A "files changed" statement about a change with an **empty change list** was reported as contradicted; it is now UNKNOWN with a note (found by an experiment on 278 labelled pull requests, `docs/research/SHADOW_EXPERIMENT_RESULTS.md`, which did not show Agentvow beating CI at a fixed review budget).

## Known limits
Python and, optionally, TypeScript only; other languages are not compared. The check sees declared interfaces, not behaviour, so a behaviour change stays unchecked. The TypeScript engine's numbers are feasibility-scale. Optional engines are tested in CI with both installed.
