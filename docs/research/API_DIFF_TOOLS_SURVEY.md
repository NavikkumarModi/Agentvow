# Existing API-compatibility tools: survey for wrapping (2026-10-31)

Purpose (value over novelty, `CLAUDE.md`): decide which mature tools Agentvow could run to check "backward compatible" claims beyond Python, instead of writing its own analysers. **Source status:** licences, push dates and stars are from the GitHub API on 2026-10-31 (verified metadata); capability descriptions are from search-result summaries and are `[snippet]` until the primary documentation is read. No novelty or differentiation claim is made.

## Why language coverage is the lever
Of 1,003 observable shadow-pool pull requests, 509 contain a "backward compatible" claim (the largest false-statement kind). **360 of them (71%) change no Python file**, so the current Python-only check (`agentvow/api_diff.py`) says nothing about them. What those 360 touch (a pull request can touch several languages; the one with an unreadable file list is excluded): TypeScript 147, JavaScript 40, Go 38, C or C++ 17, C# 14, Rust 14, Java 10, Swift 6, Dart 6, Ruby 6, PHP 4, Julia 3, Kotlin 3, and **90 with no code at all** (documentation, configuration or other; UNKNOWN is the honest result there). Measured with `gh api` file lists; script inline in the session, numbers reproducible from `data/shadow2/cheap.jsonl`.

## Candidates
| Tool | Language | Licence (verified) | Activity | Notes `[snippet]` |
|---|---|---|---|---|
| griffe (`griffe check`) | Python | ISC | pushed 2026-10-23, 703 stars | compares two versions or git refs; docs warn there is no agreed definition of "public Python API" |
| japicmp | Java | Apache-2.0 | pushed 2026-10-16, 781 stars | maven plugin and CLI |
| cargo-semver-checks | Rust | Apache-2.0 (docs also mention MIT) | pushed 2026-10-31, 1,703 stars | built on rustdoc JSON, which is unstable across toolchain versions; needs a build |
| apidiff / gorelease (`golang.org/x/exp`) | Go | BSD-3-Clause (repo) | pushed 2026-10-14 | "experimental" Go-team tools; catches compile-breaking changes, not behaviour changes |
| `@microsoft/api-extractor` | TypeScript | GitHub reports NOASSERTION for the monorepo (rushstack); **licence of this package not yet read** | very active | extracts the public `.d.ts` surface; the diffing is done by wrappers |
| `@clerk/break-check` | TypeScript | MIT | pushed 2026-10-10, **3 stars** | wraps api-extractor, classifies breaking changes; very young; also has an optional AI reviewer (would have to be off) |
| sigdiff, tsdiff, semver-check | TypeScript | **no licence declared** (sigdiff); others unread | 1 star or prototype | not suitable as a dependency |
| mutmut | Python | BSD-3-Clause | pushed 2026-10-28, 1,519 stars | mutation testing; a third-party page says no native "changed lines only" mode `[snippet]` |

## What wrapping would and would not give
- All of them check the **declared interface surface** (signatures, exports, types). A "backward compatible" claim about **behaviour** stays UNKNOWN, as with the current check. The Go source notes the same limit for apidiff.
- Most need a **build or type-check of the pull request's code** (rustdoc JSON, compiled classes, `.d.ts` output, Go modules). That means running a repository's build scripts, so it belongs in the same sandbox as test replay and needs the same care (`docs/SECURITY_MODEL.md`), and many pull requests will not build in a clean environment (UNKNOWN, as with the 35% unscorable result).
- Pull requests in JavaScript without types have no declared surface for these tools.

## Recommendation (order by measured need, not by tool quality)
1. **TypeScript first** (147 of the 360). Read the api-extractor primary documentation and licence; prototype a thin wrapper that reports removed or changed exports for the changed packages, with UNKNOWN when the package has no built `.d.ts` or the build fails. Do not depend on `break-check` (3 stars, young); borrow its approach only after reading it.
2. **Go second** (38): `apidiff` between base and head module versions; needs a Go toolchain on the runner.
3. **Python**: run a small bake-off of `griffe check` against the existing `api_diff.py` on the Python pull requests that have backward-compatibility claims, and keep whichever misses less, without adding griffe as a hard dependency (invoke it like ruff, optional).
4. Java, Rust, C#: after 1 and 2, by demand.
Each step needs a prior-art note and a measured result on pool pull requests before it is called a capability; a deterministic result is evidence about the interface, not about behaviour.

## Not done
No tool was installed or run; nothing in the package changed. Primary documentation has not been read for any entry above.
