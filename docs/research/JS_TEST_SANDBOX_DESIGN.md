# Design: running JavaScript/TypeScript tests for a claim audit (2026-11-02, draft, nothing implemented)

Purpose: let Agentvow replay "tests pass" / "lint clean" claims for Node repositories (187 of the 360 non-Python pull requests are TS/JS and all such claims are UNKNOWN today). This page is the security design that must exist before any code. It extends the existing sandbox (`agentvow/runner.py` `wrap`, `envsetup.py` guards, `docs/SECURITY_MODEL.md`); it does not replace it. No novelty claim: this is reuse of existing mechanisms. Source labels: `[snippet]` = seen only in a search summary.

## 1. Threat model
Attacker: the pull-request author or a compromised agent, controlling every file in the repository and, through the lockfile, which registry packages run. Goal: read credentials/the signing key, write outside the worktree, reach the network or local services, persist on the host, or forge a passing result.
Protected: `~/.agentvow` key, home credentials (`.ssh`, `.npmrc`, `.aws`, ...), other projects, the host outside the throwaway directories, the integrity of the verdict.
Out of scope: a hostile process already running as the user outside the sandbox (same limit as today).

## 2. What executes repository-controlled code in a Node project
| Vector | Runs when | Control |
|---|---|---|
| `preinstall`/`install`/`postinstall`/`prepare` of the root and every dependency | install | `npm ci --ignore-scripts`. Never run by default |
| `.npmrc` in the repository (registry, `script-shell`, `ignore-scripts=false`) | install, test | Never read: run npm with `--userconfig`/`--globalconfig` pointing at an empty file and `NPM_CONFIG_*` set by Agentvow only |
| Yarn Berry `yarnPath` / `.yarnrc.yml`, `.pnp.cjs`, Corepack `packageManager` download | install | Refused (UNKNOWN: "package manager would run repository code"). npm first; pnpm and Yarn Classic later |
| Non-registry dependencies (git, tarball URL, `file:`, `link:`) | install | Lockfile is read as data before anything runs; any `resolved` outside the fixed registry host => refuse. (A pnpm advisory reports git dependencies can run prepare-type scripts even with scripts disabled [snippet], so they are refused, not "scripts off") |
| `scripts.test` in package.json (a shell string; `pretest`/`posttest` hooks) | test | Not run through `npm test`. The command is parsed and must be a known runner (jest, vitest, mocha, `node --test`) with plain arguments; shell metacharacters, `&&`, `;`, backticks, `$()` => refuse. Runner binary is started directly |
| Runner config and setup files (`jest.config.js`, `vitest.config.ts`, babel/ts plugins, `setupFiles`) | test | Repository code by nature: runs in the test sandbox, same as Python's `conftest.py` |
| Dependency code loaded by the tests | test | Same sandbox |
| `NODE_OPTIONS`, `--require`, `--import` | test | Environment is built from scratch; `NODE_OPTIONS` never inherited and rejected in recipes (already in the Python list) |

## 3. Phases
0. Static (no execution): detect package manager and lockfile, read lockfile as data, parse the test command, choose Node version (`engines`/`.nvmrc` read as data; use the installed Node and record the mismatch). Any refusal here is UNKNOWN with the reason, never a verdict.
1. Install: throwaway copy of the repository (existing approach), `npm ci --ignore-scripts --no-audit --no-fund --ignore-engines`-equivalent, registry fixed, network allowed, writes limited to the environment directory and its own temp/cache (fresh cache directory, no shared npm cache, so one run cannot poison another). Guards reused from `envsetup`: size watchdog (default node_modules budget higher than the 700 MB venv; to be set from measurement), free-disk floor, per-step timeout, overall build budget.
2. Tests: network denied, writes only to the worktree and a private scratch (HOME, TMPDIR), reads of the key and credential folders denied, process group killed on timeout. Machine-readable reporter chosen by Agentvow (`jest --json --outputFile`, `vitest --reporter=json`, `mocha --reporter json`, `node --test` reporter), not the repository's reporter configuration.
3. Compare base and head only when the lockfile differs; otherwise reuse the environment (keyed by lockfile hash + Node version) for both and for later runs. Environment directory is read-only to the test phase if it can be (open question 1).

## 4. Why not Node's permission model as the boundary
Node's `--permission` flags restrict fs, child processes, workers and (in newer versions) network, but the docs say it does not protect against malicious code, it is not inherited by worker threads, and network permission is still marked experimental [snippet: nodejs.org/api/permissions.html and a third-party guide that reports `--allow-net=host` being ignored, unverified]. Jest and Vitest need child processes and workers, so the flags would have to be widened until little is left. Decision: the OS sandbox (`sandbox-exec`, bubblewrap) is the boundary; the permission model is not used.

## 5. Verdict rules (claim audit, not a safety statement)
- SUPPORTED needs: install ok with scripts skipped, runner parsed, test count > 0, tests added or changed by the change were executed, exit code and reporter agree.
- A failure caused by a skipped build script (native binary missing, `Cannot find module '...node'`) => UNKNOWN "needs a dependency build script", never CONTRADICTED.
- CONTRADICTED needs a failure that is also absent at base (or lockfile-identical base run) and is not an environment error.
- Test output is produced by the code under test: a hostile test can forge the report and exit 0. This is the existing known miss; the pack says so.

## 6. Residual risks (carried over, not solved)
- macOS profile is `(allow default)`: reads are open except listed locations and Mach services are only partly blocked. For JS this matters more because dependency code is third-party. Proposed hardening to test: deny reads of the whole home directory and allow back only the Node install root and the environment (the Linux path already does this via `_needed_roots`).
- Network is open during install: localhost services and cloud metadata endpoints may be reachable (untested for Python too). Proposed: egress allowed only to the registry host on Linux (needs a proxy); on macOS not enforceable with `sandbox-exec` host rules reliably (to verify).
- No memory cap; timeout only.
- Registry packages named by the lockfile are executed at test time inside the sandbox. Malicious but lockfile-pinned code cannot send data out (network denied) but can read any non-denied file.

## 7. Red-team fixtures that must pass before release (asserted like `tests/test_sandbox.py`)
1. `postinstall` and root `prepare` write a canary: canary absent after install.
2. Test reads a canary in a fake `~/.ssh` and in `$AGENTVOW_HOME`: denied.
3. Test opens a socket / `fetch`: blocked. Test spawns `curl`: blocked.
4. Test writes outside the worktree (absolute path, `../`, symlink inside the repo pointing out): no effect on host.
5. Repo `.npmrc` setting `script-shell`, `registry`, `ignore-scripts=false`: ignored.
6. `scripts.test` containing `; touch X`, `&& curl`, `$(...)`: refused before execution.
7. Lockfile with git/tarball/`file:` dependency: refused before install.
8. `.yarnrc.yml` with `yarnPath`: refused.
9. `jest.config.js` that reads the key: denied.
10. Package that spawns a daemon: killed with the process group.
11. Giant dependency tree / disk fill: size watchdog aborts, result UNKNOWN.
12. Test forging reporter output: documented miss, asserted by a test (as in Python).

## 8. Open questions (answer empirically before building)
1. Can the environment be mounted read-only and still work with Jest/Vitest (symlinked vs cloned `node_modules`; APFS clone copy as fallback)?
2. How many of the 187 pull requests are even eligible (package-lock.json present, recognised runner, no non-registry dependencies, no required build scripts)? A static scan, no execution. If under about 30%, stop here.
3. Does the home-deny profile on macOS still let nvm/Homebrew Node run?
4. What node_modules size and install time distribution does the eligible set show (sets the size budget and cost)?

## 8a. Result of question 2 (2026-11-02, static scan, `research/js_sandbox/eligibility.py`, data `docs/research/js_eligibility_data.json`)
Pool: the 360 non-Python shadow-pool pull requests with a tests-pass or lint-clean claim; 227 (133 repositories) have a root package.json (the earlier "187" counted a different subset).
- Package manager by lockfile: npm 81 (+7 mixed), pnpm 79, yarn 36, bun 15, none 9.
- Root `scripts.test`: recognised plain runner 69 (jest 35, vitest 32), none 62, turbo/nx/lerna 30, shell syntax 21, `node ...` 12, indirection (`npm run`, `yarn test:unit`) 11.
- npm lockfiles with a git, file or non-registry dependency, or the old format: 26 of 88.
- **Eligible under the design as written** (npm + lockfile clean + recognised runner): **25 of 227 pull requests (11%), 19 repositories**; 23 of the 190 tests-pass claims. All 25 have a package whose install script would be skipped (24 fsevents, 16 esbuild, 5 sharp); whether that breaks the tests is untested.
- Adding pnpm and Yarn Classic would raise the recognised-runner count to at most 57 of 227 (25%), before lockfile checks.
- Limits: strict command parser (a monorepo's real tests sit in sub-packages), root files only, head commit only, no test of whether the tests would run.
Outcome against the stop rule in question 2 (< ~30%): **below it.** Not built.

## 9. Gate and next step
Per CLAUDE.md: before implementation, a short prior-art read of existing untrusted-repo test runners (CI sandboxes, gVisor/Firecracker-based runners, Deno/Bun permission flags) is still owed; only search summaries were seen here. First build step after that is question 2 (static eligibility scan), because it decides whether the whole capability is worth its cost.
