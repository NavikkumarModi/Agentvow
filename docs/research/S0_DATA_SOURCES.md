# S0 — Public data sources for pilot P0 (2026-10-01)

Status of facts: dataset card and one paper page read via a summarizing fetch tool; verify against primary sources before citing.

## Best candidate: AIDev (Hugging Face `hao-li/AIDev`, v4, cutoff Nov 2025)
- 2.74M agent-authored PRs (Codex, Copilot, Devin, Cursor, Claude Code) across 327k repos; **AIDev-pop** = repos with >100 stars: `pull_request` ~71.7k rows (body, merged status, agent, repo URL, timestamps), `repository` ~6.67k (language, licence), `pr_commits` ~221k, `pr_commit_details` ~1.78M rows (~1.3 GB; diffs/patches; large patches omitted), `pr_reviews`, `pr_comments`, `pr_review_comments`.
- **Why it fits a product-first pilot:** the PR body is the agent's own claim text (what AgentMirror checks); diffs and base/head commits let us rebuild repo state; reviews give human reactions.
- Licence: dataset aggregates repos under their own licences (MIT, Apache, GPL, CC…); verify per repo before redistributing anything. Citation required (arXiv 2507.15003 or 2602.09185).

## Outcome labels available from follow-on work (not raw in AIDev)
- Merged vs rejected; rejection reasons for unmerged fix PRs (2602.00164, 326 manually analysed, 12 failure reasons).
- **Follow-up fixes** for merged agent PRs (2609.26847): 6,774 merged agent PRs in 891 repos (≥500 stars), 30-day window, co-edited files; human 90% agreement (κ=0.77), LLM judge κ≈0.78, direct-fix precision 90% (27/30). Replication package: github.com/wannita901/pr-fix-authorship (labels not confirmed as released separately).
- Post-merge SonarQube issue deltas for 1,210 merged bug-fix PRs in 206 Python repos (2601.20109).
- Complement for patch-level ground truth: UTBoost (28.4% of SWE-bench Lite and 15.7% of Verified passing patches erroneous).

## Known weaknesses for our use
1. Outcome labels are noisy proxies (follow-up fix ≠ missed downstream impact); LLM-judged.
2. Selection bias: mostly merged PRs from popular repos.
3. Claims may not be of the checkable form ("no downstream impact", "tests pass"); the real rate is unknown — measuring it is the first cheap step.
4. Needs repo cloning at base/head SHAs to build graphs (network, disk, build issues); Python-only matches the current collector.
5. A follow-up fix tells us a change was wrong, not whether *our* decision rule would have flagged it: ground truth for "decision-changing" must still be defined independently (RISKS C1).

## Proposed S0 steps (cheapest first)
1. **Claim-frequency survey (no cloning):** from `pull_request` + `repository`, restrict to Python repos, run the rule-based claim extractor on PR bodies; report how often each claim type appears per agent. Stop rule: if fewer than ~5% of PR bodies contain a checkable claim, widen the extractor or choose different claim classes before anything else.
2. **Candidate pool:** join with the follow-up-fix labels from the replication package; keep merged Python PRs with a label; target ≥30 items with ≥8 failures.
3. **Feasibility sample:** clone 5 repos at base/head, run the import-graph collector, see how many build and parse cleanly.

## Download request (needs your explicit yes)
- Files: `pull_request` and `repository` tables of `hao-li/AIDev@v4` (AIDev-pop), Parquet, from huggingface.co. Exact size not stated on the card (71.7k and 6.67k rows; expect a few hundred MB at most — I will check file sizes via the API first and tell you before downloading).
- Later, only if step 1 passes: the replication package from GitHub (small) and a handful of git clones.

---
## Step 1 results — claim-frequency survey (run 2026-10-01; `scripts/survey_aidev.py`)
Data: `pull_request.parquet` (57.6 MB) and `repository.parquet` (0.4 MB) from `hao-li/AIDev` v4 (falls back to main if tag missing), stored in git-ignored `data/aidev/`. Python repos only: 13,128 PRs with a body, 1,108 repos. Regex-based, not hand-validated beyond the check below, so treat rates as rough.

| Agent | PRs | "no downstream impact" | "tests pass" (loose) | "no breaking / backward compatible" |
|---|---|---|---|---|
| Claude Code | 402 | 0.7% | 33.8% | 32.6% |
| Copilot | 2,693 | 1.2% | 30.3% | 35.1% |
| Devin | 1,345 | 0.1% | 27.9% | 16.6% |
| Cursor | 771 | 0.0% | 14.5% | 7.0% |
| Google Jules | 52 | 0.0% | 7.7% | 0.0% |
| OpenAI Codex | 7,865 | 0.0% | 0.5% | 0.4% |

Findings:
1. **The planned flagship claim, "no downstream impact", is almost absent from real PR bodies (≤1.2% for any agent).** Building the product around it would target a rare claim.
2. **"Tests pass" and "no breaking changes / backward compatible" are the common checkable claims** among Claude Code, Copilot and Devin (roughly 17–35%).
3. Codex PR bodies are mostly templates with almost no claims; non-Codex agents have ~28% with some checkable claim.
4. **Extractor precision bug found:** 672 of 1,487 "tests pass" hits (45%) came only from the word "verified". Strict phrase rate is 6.2% overall. "Verified" removed from the extractor (now falls to unchecked).
5. Tests-pass claim rate is higher in unmerged PRs (19.7%) than merged (8.0%), but agent mix confounds this (Codex dominates merged); do not interpret.
6. "Backward compatible" phrases may describe the change rather than assert a checked claim; precision unvalidated.

Stop rule outcome: overall checkable rate (~11%) is above the 5% threshold, but the *target claim class is wrong*. Per S0, change the claim classes before building more.

## Product implications
- Prioritise **"tests pass"** (needs a test-run collector bound to the PR head commit; evidence freshness is directly useful) and **"no breaking changes / backward compatible"** (public-API diff: removed/renamed functions, changed signatures, changed defaults), both frequent in Claude Code/Copilot/Devin output.
- Keep "no downstream impact" as one check among several, not the headline.
- Next cheap steps: hand-validate ~30 matches per claim type for extractor precision; then pick ~30 merged Python PRs with a "tests pass"/"backward compatible" claim for a feasibility clone test (S0 step 3).

## Step 1b — hand validation of extractor precision (2026-10-01; one annotator, n=30 per type, non-Codex Python PRs)
Matched sentences judged by me only; no inter-rater check, so treat as indicative.
- **"Tests pass" (strict phrases): 26/30 (87%) were real assertions that tests pass.** The 4 misses were PR-template checkboxes ("[ ] Tests passing?", "[x] added a screenshot of my new test passing") and a goal statement ("ensure that … tests pass").
  - **15 of the 26 real claims include a number** ("All 217 tests pass", "148 passed, 4 skipped"). A claimed count is directly checkable against an actual run: a high-value, concrete check.
  - Extractor fix needed: ignore markdown checkbox lines `- [ ]` / `- [x]` and "ensure that"-style goals.
- **"Backward compatible / no breaking changes": 21/30 (70%) asserted compatibility.** Misses: bare headings ("## Backward Compatibility"), design-intent explanations ("takes precedence to maintain backward compatibility"), and feature lists.
  - **Most asserted compatibility is vague** ("maintains backward compatibility"). Only a minority name something checkable ("no API changes", "same interface"). A public-API diff can contradict or support these; vague ones should render as UNCHECKABLE, not as support.
- Implication: **"tests pass" with a claimed count is the crispest first claim to verify end to end** (run tests at the PR head commit, compare pass/skip counts, bind to the commit). Compatibility claims come second and mostly need a scoped statement of what was and wasn't checked.

## Step 3 — collector feasibility on real PRs (2026-10-01; `scripts/feasibility.py`)
Cloned 5 small public repos (DDNS, django-dbbackup, gixy, translate, QuantEcon.py; ~66 MB, local only). Of the 30 pool PRs in them, **26 resolved to a merge commit** (the 4 gixy PRs did not match the `(#N)` / `Merge pull request #N` convention). The import-graph collector and `check` ran on all 26 with **no errors** (static parsing only; no third-party code executed).

Result: **26/26 returned INSUFFICIENT EVIDENCE**, all because the "tests pass" claim has no test result bound to the commit (AgentMirror does not run tests yet). That is the fail-closed design working, and also the product problem: a tool that always answers "insufficient" delivers no value.

Next product step: a **test-run collector** that executes the project's tests at the PR head commit in an isolated environment, produces snapshot-bound evidence (pass/fail/skip counts, command, environment), and compares claimed counts with actual counts. This executes third-party code, so it needs a sandbox and your sign-off before any run.

## Step 4 — sandboxed test-run collector on DDNS (2026-10-01; `agentmirror/runner.py`, `scripts/pilot_run.py`)
Approved by the user: run the five cloned repos' tests in a sandbox. Done so far: **NewFuture/DDNS only (10 merged Copilot PRs)**; django-dbbackup, translate and QuantEcon not yet run. Tests ran under macOS `sandbox-exec` (network denied; writes limited to repo/tmp). Self-test confirmed both blocks.

Lessons (all driven by real data, now covered by `tests/test_runner.py`):
1. **Network-dependent tests fail in a no-network sandbox** (6 of ~585 tests at the first commit: "real request" / "real integration"). Treating any failure as contradiction would be a false alarm.
2. **Failures-vs-base is not enough.** A first differential rule (failures not present at base) still flagged 2 of 10 PRs as CONTRADICTED; inspection showed the "new" failures were tests newly added or moved by the PR (no baseline exists), failing only for environmental reasons. Final rule: a regression = fails now AND passed at base; fails at base too = known-failing/environmental; fails but absent at base = uncomparable → UNKNOWN.
3. Outcome after the fix: **0 regressions in 10 PRs**; 8 NOT_CONTRADICTED (all failures also at base), 2 UNKNOWN (uncomparable). No SUPPORTED verdicts, because the sandbox environment cannot reach an all-pass state for this repo. Status stays INSUFFICIENT EVIDENCE.
4. **This is not evidence of recall.** n=10, one repo, one agent (Copilot), no ground-truth failures, so no true positives to detect. It shows only that the collector runs and that the differential rule avoids false alarms here.
5. Known limitations: no venv/dependency install yet (stdlib-only repo); pass/fail counts differ from the project's CI environment; flaky tests unhandled (two reruns of the same commit were identical); loopback is also blocked by the sandbox; pytest parsing implemented but untested on a real run.

## Step 5 — django-dbbackup with a real dependency install (2026-10-01)
User-approved: throwaway venv (`data/venvs/dbbackup`) with, from PyPI: Django 5.2.17, django-storages 1.14.6, psycopg2-binary 2.9.13, python-dotenv, python-gnupg 0.5.7, testfixtures 12.3.0, coverage, pytest 9.1.1, pytest-mock 3.16.0, pytz (plus transitive: asgiref, sqlparse, pluggy, packaging, iniconfig, pygments). `pytest-django` was installed by mistake, caused an INTERNALERROR, and was removed (the repo's own hatch config does not use it). The missing test-only dependency `pytz` (not declared by the repo) produced a collection error that the tool correctly reported as **inconclusive**, not as a failure.

Results (5 merged Copilot PRs, pytest path): 14 tests fail identically at base and head (environmental: sandbox without network/services), **0 regressions**; 4 PRs → NOT_CONTRADICTED (status NO CONTRADICTION FOUND, scoped), 1 → UNKNOWN (17 failing tests did not exist at base).

**Claimed vs observed counts** (agent's count vs passed+failed found by AgentMirror):
- dbbackup: 242 vs 228+14, 212 vs 198+14, 270 vs 256+14 → agent count = total tests found, i.e. the 14 environmental failures presumably pass in the agent's fuller environment (supports the environmental interpretation); 217 vs 205+14=219 (differs by 2).
- DDNS: 384 vs 379+5 matches (PR 501); others differ (24 vs 574, 606 vs 579, 819 vs 803, 827 vs 815, 524 vs 531, 636 vs 642, 218 vs 809) — a mix of subset claims and unexplained differences. Not interpreted further; one annotator, tiny sample.
Overall across 15 PRs: **0 regressions found, 0 confirmed all-pass**. Still no recall evidence (no known-bad PRs in the sample).

Product implications: (1) an installable-environment step is the main cost and failure mode (undeclared test deps, services); (2) the claimed count is a useful, cheap consistency signal; (3) to learn anything about detection we need PRs with *known* failures (follow-up-fix labels, rejected PRs, or CI-failing PRs), not just merged PRs with passing claims.

## Step 6 — backward-compatibility check via public-API diff (`agentmirror/api_diff.py`)
Static Python diff of public names/signatures between base and head (removed names, removed/renamed params, new required params, positional-order change; test files excluded; parse failures = UNKNOWN). Sanity run on all merged agent PRs with a compat claim in the 5 cloned repos: 31 PRs → 25 NOT_CONTRADICTED, 5 CONTRADICTED, 1 UNKNOWN. Of the 5, 2 were false alarms from test files (now excluded); the other 3 look like genuine API changes (removed `proxy` param, removed module/`VERSION`) but are **not hand-verified and not ground-truth**; whether the change was actually breaking to users is unknown. Limits: no semantic/behaviour changes, no non-Python, private-vs-public judged by leading underscore only.

## Step 7 — first run on real own-sessions (user-directed, 2026-10-01)
Ran `agentmirror check --session` on 3 of the user's Claude Code sessions (2 `attrition`, 1 `AgentIQ`; no `--run-tests`). Findings:
- `attrition` sessions: LaTeX paper work, no checkable claims → "nothing was verified" (correct fail-closed behaviour; a non-code session is out of scope).
- `AgentIQ`: the final message contains a real, checkable claim ("535 backend tests … 5 frontend tests, all green") that the extractor **missed** (count precedes the noun; "all green" follows a parenthetical). Fixed; PR-body templates and real agent reports differ, so extractor patterns must be tuned on real final messages, not only on AIDev PR bodies.
- All three repos had uncommitted changes (AgentIQ: 163 files) and, for `attrition`, a last commit that predates the sessions: the tool cannot bind evidence to one commit. Real agent work is often uncommitted at report time, so **a "snapshot of the working tree" mode (hash of tracked + untracked files) is a needed product feature**, not an edge case.
- Also: the AgentIQ claim spans backend + frontend suites; a single test command cannot verify it (multi-suite claims need per-suite runs).

## Step 8 — follow-up-fix labels as ground truth: NOT enough (2026-10-05)
Downloaded `rq1_survival_frame.csv` (463 KB) and README from github.com/wannita901/pr-fix-authorship (local only; licence unspecified; the 30 MB judge files were not fetched). Frame: 9,440 PRs (4,396 agent, 5,044 human); agent verified-fix rate 4.3% vs human 2.4%. Joined to AIDev: 4,394 agent PRs, 687 in Python repos, 676 with a body.
Python agent PRs with a checkable claim and a label: **"tests pass": 40 PRs, 1 verified fix; "backward compatible": 42 PRs, 0; "no downstream impact": 1 PR, 0.**
Conclusion: follow-up-fix labels give almost no positives for our claim classes, so they **cannot** measure detection recall. Options for ground truth: (a) independent CI check-run conclusions on the PR head commit versus the "tests pass" claim; (b) planted/mutated faults in real PRs with known truth (research-plan benchmark idea); (c) agent patches that pass tests but are wrong (UTBoost/SWE-bench).

## Step 9 — independent CI as ground truth (2026-10-05; `scripts/ci_labels.py`, output `data/ci_labels.csv`)
150 non-Codex Python AIDev PRs with a strict-ish "tests pass" claim (75 merged, 75 unmerged, random sample), CI state on the PR head commit via read-only `gh api` (check-runs + legacy status):
| | failure | success | none (no CI) | error |
|---|---|---|---|---|
| unmerged (75) | 17 | 14 | 41 | 3 |
| merged (75) | 10 | 35 | 28 | 2 |
**27 PRs claim "tests pass" while *any* CI check fails on the head commit** (many of those are non-test checks, see Step 10; follow-up-fix labels gave 1). This is a weak, noisy label, not ground truth. 69 PRs have no CI at all (the claim is then uncheckable by CI; AgentMirror's own run is the only evidence). Caveats: the PR body may have been written before later commits; a CI failure can be lint/build, not tests; the sample is not weighted to the AIDev population. CI failure is evidence about the claim, not proof the claim was false when made.

## Step 10 — what the 27 CI failures actually are (2026-10-05)
Failing check names on the 27 PR head commits (by name heuristics, not hand-verified): ~17 tests/matrix-type jobs, 6 "other" (security scans, SonarCloud, GitGuardian, PR-title validators, Windows nuitka builds, release automation), 3 status-only, 1 lint. **A failing CI check is not a failing test**: many failures are unrelated to the "tests pass" claim. Of the test-type failures, most are in huge repos (litellm 1.9 GB, azure-cli, mlflow, crewAI, prefect) or depend on external API keys (instructor), old Python versions (chardet 3.6/3.8/pypy3), or other OSes (starfish macOS/Windows). In the 7 small repos cloned (~230 MB), exactly **one** PR (blarify #266, merged) has a test-job failure that might reproduce locally.
Conclusion: natural data yields ~1–3 reproducible positives per ~150 PRs. **A recall measurement from natural PRs is not feasible at this budget.** Honest route: a planted-fault benchmark (inject a known regression into a real PR's change in repos where tests run, keep the agent's "tests pass" claim, check whether AgentMirror reports CONTRADICTED with regressions>0). This measures pipeline sensitivity only; faults are authored by us, so it is not evidence of real-world detection (RISKS C1). Report it as such.
Product-relevant side finding: CI is a free, independent second source. Ingesting GitHub check-runs for the head commit (when it exists) would give "tests pass" evidence without running anything, and 69/150 sampled PRs had no CI at all (where only a local run can help).

## Step 11 — CI as independent evidence (`agentmirror/ci.py`, `--ci`; 2026-10-06)
For a clean, pushed HEAD, read the project's check-runs through `gh` (read-only). Only test-named jobs (`test|pytest|unit|integration|tox|nox|spec`) count for a "tests pass" claim; lint/security/title/release jobs are ignored. Dirty trees get no CI evidence (CI never saw them). No CI → no evidence (never a pass). Applied to the 145 usable PRs of the CI sample: **13 CONTRADICTED, 34 SUPPORTED, 98 UNKNOWN** (69 had no CI at all; 29 had CI but no test-named job). 6 of the 27 raw-CI-failure PRs came out SUPPORTED because their failing jobs were not test jobs (e.g., SonarCloud). Caveats: job-name heuristics misclassify (e.g. chardet's "build (3.8)" is a test job under another name); a green CI does not confirm the agent's stated count; PR bodies may predate later commits. Product decision taken the same day: a claimed test count that matches none of AgentMirror's totals is UNKNOWN even when failures are environmental (fail-closed).
