# AgentMirror security model (2026-10-07)

AgentMirror reads a repository that an agent (or anyone) controls and, optionally, runs that repository's test code. This page states what is protected, what is not, and what was found by adversarial review (`research/RISKS.md`). Prototype: treat as unaudited.

## What runs, and where
| Action | Executes repository code? | Protection |
|---|---|---|
| Static checks (claims, import graph, API diff, CI read) | No | `git` calls neutralise hooks/fsmonitor/ext protocols (`-c core.fsmonitor=false -c core.hooksPath=/dev/null`); text from the repo/agent is length-bounded, depth-bounded and escaped on output |
| `--run-tests` | **Yes** (the project's tests, conftest, plugins) | macOS `sandbox-exec`: network denied; writes only inside the throwaway worktree (HOME and TMPDIR live there); reads of the signing key and common credential stores denied; **all other reads allowed** |
| `--setup auto` | **Yes** (dependency installs run build scripts) | Installs from a throwaway copy (the real repo is never written to, no editable link back); network allowed; writes limited to the throwaway environment; reads of the key/credentials denied; size/disk/time guards |
| Hook (`--hook`) | Only if `--run-tests` is added | Writes only under `<repo>/.agentmirror/` and refuses symlinks (no write-through to other files) |

On a platform without `sandbox-exec` (Linux, Windows) the tool **refuses** to run repository code; there is no unsandboxed fallback. The GitHub Action therefore only reads CI results (it does not run tests).

## Integrity of results
- Evidence AgentMirror records (`.agentmirror/evidence/*.json`) is HMAC-signed with a per-user key stored **outside** the repository (`~/.agentmirror/key`, or `$AGENTMIRROR_HOME`). Unsigned records are never treated as independent evidence. The sandboxed test process cannot read the key or write outside its worktree.
- The hook's result files (`report.html`, `decision.json`) are sealed with `decision.sig` (HMAC over both). The VS Code extension displays a hook result only if the seal verifies.
- **Limit:** the key is readable by any process running as you that is not sandboxed. A fully privileged local agent can read it and forge evidence or seals. These measures stop a repository, a cloned/malicious project, or sandboxed test code from forging a result; they do not stop a compromised or malicious agent that runs with your permissions outside the sandbox.

## Known remaining weaknesses
- Test suites that start background daemons (for example gpg-agent through python-gnupg) can hang under the sandbox with a fresh `$HOME`; the run ends at `--test-timeout` (default 600 s) with an inconclusive result, and the whole process group is killed so no daemon is left behind. (Earlier runs of such suites only worked because a leaked daemon from an earlier run was being reused.)
- Reads are unrestricted apart from the denied locations (project secrets elsewhere on disk, environment of other processes' files, etc. can be read by test code, though it cannot send them over the network).
- Test code can still exhaust CPU/memory (a timeout applies; no memory cap).
- `--ci` trusts the project's CI as configured; a pull request can edit its own workflows (reported as "authority unknown").
- Trivialised tests are not detected; a change that modifies existing tests cannot be reported as plainly supported.
- The VS Code extension: `command`, `python` and `testCommand` can only come from user settings; in untrusted workspaces they and `runTests` are restricted. The report webview has no scripts, network, forms or frames. Not yet exercised inside a live VS Code window.
- GitHub Action: no script injection found in review (inputs go through environment variables); the sticky comment updates only the workflow bot's own marked comment; fork PRs have a read-only token and cannot comment.

## Reporting
This is a research prototype. Findings from reviews are recorded in `docs/research/RISKS.md`.

## Known limit: replay of an old sealed result
The seal proves AgentMirror produced a result, not that it is the latest one. A process that can write `.agentmirror/last/` could put back an older genuine result and the extension would display it as sealed. The result carries `generated_at`/`run_id`; the report shows them. Not mitigated in 0.1.0.

## Transcript bounds
Hooks read at most the last 8 MB of the transcript, only regular files (fifos/devices refused), and skip lines over 2 MB; the extension reads only regular, size-bounded result files (no symlinks).
