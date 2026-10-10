# Stage B2 (ambient-environment falsification run) — pre-registration, 2026-10-10 (written BEFORE any B2 run)

Origin: the adversarial review of `PAPER_FRAME.md` (section 8) named this as the cheapest experiment that could falsify the "small gap" reading of B1. B1 removed ambient state (the agent worked in an empty virtualenv) and compared contexts asymmetrically.

**Question.** When the agent works in a virtualenv that already contains a broad set of common packages (a realistic developer environment, not declared by the repositories), do (a) repository-only replay and (b) the agent's recipe replay still reproduce the agent's passing result, with every context using the **same scoped target-test command**?

**Design.** The same 32 valid B1 tasks, same prompt C1P except one added sentence ("a virtual environment is active with some common packages already installed; install anything else you need"), same S0 sandbox, same model, one run per task. Ambient set (installed before the agent starts, versions recorded): requests, numpy, pandas, pyyaml, pydantic, aiohttp, httpx, click, rich, attrs, jinja2, toml, typing-extensions, pytest, pytest-asyncio, pytest-mock, pytest-cov.
Contexts, all on the same frozen patch: E_repo (zero-config ladder), E_recipe_scoped (the agent's recipe with its test command replaced by `pytest -q <target files>`), E_recipe_own (the agent's own command, reported secondarily), E_freeze (agent's exact `pip freeze`, scoped command).
**Limitation stated in advance:** tasks are still the S1-filtered set (zero-config reproduced the PR's own head tests), so the ceiling effect is reduced but not removed for repository-only replay; the run tests whether ambient state in the agent's environment breaks it, not the prevalence of S2 situations.

**Primary outcome.** Reproduction rate of E_repo and of E_recipe_scoped among runs whose target tests pass in the agent's environment, with Wilson 95% intervals; paired counts (only-repo, only-recipe, both, neither). **Pre-registered reading:** if E_repo falls to at most 80% (at least 6 of the 32 non-reproduced) while E_recipe_scoped stays within 10 points of E_freeze, the "small gap" reading of B1 is falsified; if E_repo stays at least 90%, B1's reading survives this condition; between those, inconclusive. N = 32, so this is descriptive, not confirmatory.
**Secondary.** Hidden-state markers (undeclared packages found by the audit, ambient imports not declared by the repository or recipe), recipes rejected and why, cost.
**Budget.** $0.42 per run in B1; hard cap $18 total, $1.5 per run. Stop without recording on rate limits.
**Code.** `research/preconditions/stageb_run.py` with `AMBIENT=1` (output `stageb2_results.jsonl`, runs in `stageb2_runs/`); the instrument is the post-fix one (commit `05bd899`). Any change during the run is logged here with the affected measure recomputed.

## Deviation log
(none yet)
