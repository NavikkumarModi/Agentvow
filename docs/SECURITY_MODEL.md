# Agentvow security model (2026-10-07)

Agentvow reads a repository that an agent (or anyone) controls and, optionally, runs that repository's test code. This page states what is protected, what is not, and what was found by adversarial review (`research/RISKS.md`). Prototype: treat as unaudited.

## What runs, and where
| Action | Executes repository code? | Protection |
|---|---|---|
| Static checks (claims, import graph, API diff, CI read) | No | `git` calls neutralise hooks/fsmonitor/ext protocols (`-c core.fsmonitor=false -c core.hooksPath=/dev/null`); text from the repo/agent is length-bounded, depth-bounded and escaped on output |
| `--run-tests` | **Yes** (the project's tests, conftest, plugins) | macOS `sandbox-exec`: network denied; writes only inside the throwaway worktree (HOME and TMPDIR live there); reads of the signing key and common credential stores denied; **all other reads allowed** |
| `--setup auto` | **Yes** (dependency installs run build scripts) | Installs from a throwaway copy (the real repo is never written to, no editable link back); network allowed; writes limited to the throwaway environment; reads of the key/credentials denied; size/disk/time guards |
| Hook (`--hook`) | Only if `--run-tests` is added | Writes only under `<repo>/.agentvow/` and refuses symlinks (no write-through to other files) |

On a platform without `sandbox-exec` (Linux, Windows) the tool **refuses** to run repository code; there is no unsandboxed fallback. The GitHub Action therefore only reads CI results (it does not run tests).

## Integrity of results
- Evidence Agentvow records (`.agentvow/evidence/*.json`) is HMAC-signed with a per-user key stored **outside** the repository (`~/.agentvow/key`, or `$AGENTVOW_HOME`). Unsigned records are never treated as independent evidence. The sandboxed test process cannot read the key or write outside its worktree.
- The hook's result files (`report.html`, `decision.json`) are sealed with `decision.sig` (HMAC over both). The VS Code extension displays a hook result only if the seal verifies.
- **Limit:** the key is readable by any process running as you that is not sandboxed. A fully privileged local agent can read it and forge evidence or seals. These measures stop a repository, a cloned/malicious project, or sandboxed test code from forging a result; they do not stop a compromised or malicious agent that runs with your permissions outside the sandbox.

## Known remaining weaknesses
- Test suites that start background daemons (for example gpg-agent through python-gnupg) can hang under the sandbox with a fresh `$HOME`; the run ends at `--test-timeout` (default 600 s) with an inconclusive result, and the whole process group is killed so no daemon is left behind. (Earlier runs of such suites only worked because a leaked daemon from an earlier run was being reused.)
- Reads are unrestricted apart from the denied locations (project secrets elsewhere on disk, environment of other processes' files, etc. can be read by test code, though it cannot send them over the network).
- Test code can still exhaust CPU/memory (a timeout applies; no memory cap).
- `--ci` trusts the project's CI as configured; a pull request can edit its own workflows (reported as "authority unknown").
- Trivialised tests are not detected; a change that modifies existing tests cannot be reported as plainly supported.
- The VS Code extension: `command`, `python` and `testCommand` can only come from user settings; in untrusted workspaces they and `runTests` are restricted. The report webview has no scripts, network, forms or frames. Exercised in a live VS Code window (see LIVE_TESTING.md).
- GitHub Action: no script injection found in review (inputs go through environment variables); the sticky comment updates only the workflow bot's own marked comment; fork PRs have a read-only token and cannot comment.

## Reporting
This is a research prototype. Findings from reviews are recorded in `docs/research/RISKS.md`.

## Known limit: replay of an old sealed result
The seal proves Agentvow produced a result, not that it is the latest one. A process that can write `.agentvow/last/` could put back an older genuine result and the extension would display it as sealed. The result carries `generated_at`/`run_id`; the report shows them. Not mitigated in 0.1.0.

## Transcript bounds
Hooks read at most the last 8 MB of the transcript, only regular files (fifos/devices refused), and skip lines over 2 MB; the extension reads only regular, size-bounded result files (no symlinks).

## Final review findings (0.1.0, second independent review)
Fixed: uncommitted-work overlay and tree hash followed symlinks (could copy the signing key into the test worktree) — links are now skipped; a crash on pathological source (RecursionError) left a stale sealed all-clear — parse errors are now gaps and a hook crash writes a sealed INSUFFICIENT result; "all tests pass" with failing tests (also failing at base) was reported as not contradicted — now UNKNOWN; hook results omitted the comparison base — now in the scope text; results are bound to the repository path (extension rejects a copied result); `--base` option injection; stale git worktrees pruned; unused destructive `run_pair` removed.
Mitigated, not solved: sandbox `(allow default)` lets Mach services act outside it (`defaults write` persisted a value in the review); common helpers are denied, but this is not containment.
Open: test output is parsed from text the repository's own code prints, so a hostile repo can fake counts (an injected machine-readable reporter would be the fix); the comparison base is a heuristic (HEAD~1 / merge-base / HEAD when dirty) and can hide regressions already committed this session (recording HEAD at session start would fix it); replay of an old genuine result into the same repository; `SKIP_DIRS` (venv, node_modules) are not analysed and not reported as a gap.

## Third review (pre-release) — fixed and open
Fixed: non-ASCII file names were silently dropped from the change list (false all-clear) — git now runs with `core.quotepath=false` and any changed `.py` file missing from the graph becomes a gap; a hostile repo's own `agentvow/__main__.py` could run unsandboxed through `python -m` in the background/doctor child — children now run with `-I` and an explicit package path; repository-defined git clean/smudge/process filters and textconv/external diff drivers (written by an agent with `git config`) ran outside the sandbox — they are neutralised per repository; terminal escape sequences in a claim could overwrite the STATUS line in plain-text output — control characters are stripped and newlines collapsed in plain text and in the extension; the background-run lock was a repository-writable pid file (stalling or denial) and newer turns were dropped — it is now an OS file lock in `~/.agentvow/locks`, newer turns wait for older ones; result files are written atomically (temp + rename); the extension verified and then re-read result files (check-then-use gap) — it now verifies the very buffers it displays; the second pass after a feedback block is still checked and reported (never blocks twice); the signing key is created with mode 0600 from the first byte; the Linux sandbox now also drops capabilities, unshares IPC/UTS and hides `/run`.
Fixed afterwards: the Linux sandbox now shows an EMPTY home, /tmp and /run (no credentials, browser profiles, shell history, other projects or ssh-agent/docker/D-Bus sockets) and mounts back only the interpreter/venv the command needs and the writable paths; a green CI result is only "not contradicted" when the same change edits CI/test configuration; the prompt hook's delivery mark is keyed; GitHub Actions are pinned by commit SHA; when no change is counted although files are uncommitted, the report says the turn baseline may have been reset.
Open: any process running as you can write a sealed turn baseline (it can only hide changes from the count; the report flags the case above, and an empty change list never produces a clean verdict, only UNKNOWN) — the real fix is a baseline recorded when a prompt is submitted, which needs a prompt-time hook that has not been proven safe; CI evidence still comes from any check named like a test job; the macOS sandbox allows OS services by default (Mach services; common helpers blocked).

## Recipes (agent-declared preconditions)
Recipes are untrusted input. Only a validated subset is executable: `pip install` of plain requirements/files inside the repository (no index/URL/VCS options), `python <script inside the repository>` preparation steps, a pytest/unittest command, plain environment variables (no PATH/PYTHON*/secrets). Setup steps need network and run in the install sandbox with size/disk guards on a throwaway environment; preparation and tests run in the network-denied test sandbox. A preparation step that modifies an existing file is refused as evidence. Open: a repository script run by `prepare` is repository code (like the tests) and could try to influence its own replay in ways file hashing does not see (for example time or ordering); installs execute third-party build code on the verifier's machine inside the sandbox.
