# Python API-diff bake-off: griffe against `agentvow/api_diff.py` (2026-11-01)

Part of `API_DIFF_TOOLS_SURVEY.md` (recommendation 3). **Exploratory; not pre-registered; one reader (me) adjudicated the disagreements; no human labels.** Raw output: `docs/research/apidiff_bakeoff_data/bakeoff.json`; script `research/apidiff_bakeoff/bakeoff.py`.

## Setup
The 149 Python shadow-pool pull requests that contain a "backward compatible" claim. For each changed `.py` file that existed at the base commit (modified, renamed or removed), both tools got the same two texts (base, head) fetched from the GitHub contents API and compared **one module at a time, with no package context, no installs and nothing imported or run** (griffe 2.4.1, ISC, static loading only). 620 files, 149 pull requests, 2 griffe failures, 0 failures for the existing check.

## Result
| | files | pull requests |
|---|---|---|
| both flag a breaking change | 54 | 27 |
| neither flags | 558 | |
| griffe only | 5 | 2 |
| existing check only | 3 | 1 |
| flagged by either tool | | 28 (existing) or 29 (griffe) of 149 |

The two agree on 612 of 620 files. Finding kinds are the same families (removed public object, removed parameter, new required parameter, moved positional parameter).

## The eight disagreements, read by hand (code fetched at base and head)
| Pull request / file | Tool that flags | What is true | Verdict |
|---|---|---|---|
| typespec 8311 `models/parameter.py` | griffe | a public method (`imports_for_multiapi`) was removed from a private base class and so from public subclasses that inherited it | **griffe right; ours misses inherited members** |
| halmos 541 `solve.py` | griffe | dataclass fields of two public classes changed, so their generated `__init__` changed | **griffe right; ours does not model dataclass fields** |
| GameSentenceMiner 169 `configuration.py` | griffe | a dataclass field (`backup_vad_model`) was removed and another added | **griffe right; same gap** |
| KToolBox 266 `posts/__init__.py` | griffe | a wildcard re-export changed; names cannot be known from the file alone | **probably right; ours ignores wildcard imports silently and should report a gap** |
| onnxscript 2384 `core.py` | griffe | a parameter's default value changed | **griffe more sensitive; whether a default change breaks a caller is a judgement; ours does not look at defaults** |
| mlflow 17008 `clint/__init__.py` | ours | `from __future__ import annotations` was removed | **ours wrong (false positive); fixed in this commit with a test** |
| typespec 8311 `serializers/__init__.py`; yutto 539 `functional/__init__.py` | ours | a name imported in a package `__init__` was removed | **definitional**: we count names imported in an `__init__` as public (users can write `from pkg import X`); griffe counts them only when listed in `__all__`. Neither is established as the right rule. |

## What this does and does not show
- On this sample griffe finds everything the existing check finds that is not a false positive, plus three clear classes the existing check misses (inherited members, dataclass fields, default values) and one it should flag as a gap (wildcard imports). That is about 4 to 5 extra pull requests of 149 (3%), plus one false positive removed.
- It says nothing about how many of these changes the agent's claim actually contradicts, or whether the claims were false: it is a comparison of two detectors against each other and against my reading of the code, not against independent ground truth.
- Single-file loading is a handicap for griffe (it normally resolves a whole package); real use would give it the package, which could change both its hits and its failures.
- The current policy makes an API change an attention flag and never a CONTRADICTED verdict, so a better detector improves recall of attention flags, not the verdict class.

## Decision (value over novelty)
Griffe is the better engine: ISC licence, maintained, static, covers the classes we would otherwise have to rebuild. Plan: keep `api_diff.py` as the dependency-free fallback and add griffe as an **optional** engine used when installed (like ruff), reported with its version in the record; no hard dependency. Not done yet: that integration, a test of griffe on whole packages, and a check on whether its extra hits correspond to false claims. The `__future__` false positive is fixed now.
