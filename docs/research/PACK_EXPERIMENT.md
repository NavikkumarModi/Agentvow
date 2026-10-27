# The pull-request gate's environment path against the zero-config ladder (2026-10-27)

**Question.** The three earlier fixes tried to improve the zero-config ladder (`envsetup.build_env`) and moved nothing. The pull-request gate and the evidence pack do not use the ladder: they derive the environment from the repository's CI workflows, Dockerfiles and setup files (`baseline.prepare`). Does that path reach a verdict where the ladder did not?

**Method.** `research/envsetup/pack_experiment.py 5`: the five pull requests of the discovery experiment (arcade-mcp#557, QueryWeaver#111, crewAI#3446, dbt-data-reliability#861, clusterfuzz#4928), each through `agentvow check --run-tests --setup auto` (ladder) and the same with `--evidence-pack` (CI-derived environment), same machine, one run each. A diagnostic of five, not a rate.

## Result
**0 verdicts of 5 in either mode; the outcome was identical for all five.**
| repository | ladder | CI-derived environment |
|---|---|---|
| ArcadeAI/arcade-mcp#557 | tests ran, 1 failed (15 s) | same (18 s) |
| FalkorDB/QueryWeaver#111 | missing `requests` | same |
| crewAIInc/crewAI#3446 | tests not run (too heavy) | same; the notes say the CI step `uv sync --dev` was "translated to `pip install -e .` (lockfile not honoured, groups not installed)" |
| elementary-data/dbt-data-reliability#861 | missing `dbt` | same |
| google/clusterfuzz#4928 | missing `aiohttp`, `antlr4`, `flask`, ... | same |

## Reading
For these five the CI install steps are not plain `pip install`: `pipenv` (QueryWeaver, clusterfuzz), `uv sync` with a lock and groups (crewAI), a multi-adapter dbt matrix (dbt-data-reliability), a monorepo layout (arcade-mcp). Agentvow translates only what pip can express, so the derived environment came out the same as the ladder's. The pack's own static scan lists what the replay cannot supply (`pipenv` as an external program, example environment files, Docker services, required environment variables).

## What the four experiments say together
The lock file, the Python version, dependency discovery and the CI-derived environment: **4 experiments, 27 repository runs, 0 verdicts gained**, one repository made worse. The repositories in this population (inconclusive in the detection study) are exactly those whose environment cannot be rebuilt from their files by pip. So:
- **For a third-party pull request in a repository whose environment is not plain pip, UNKNOWN is the stable, honest outcome**, and more heuristics did not change it. That is a property to state in the product's claims, not a defect to keep patching.
- **Where it can work:** repositories whose CI is plain `pip install` plus `pytest` (the detection study's conclusive cases, 3 of 83), and agents whose environment is captured (B6: 91% of valid runs reproduced from the captured packages).
- **For a pilot or a sales claim,** choose repositories by this property first (pip-installable, tests runnable offline) and report the share of pull requests that end UNKNOWN beside the share that end SUPPORTED, instead of promising coverage of arbitrary repositories.
- **Not measured here:** how many repositories in the wild are of the working kind (the detection study's 83 pull requests came from AIDev, which is dominated by large multi-language projects), and the gate on repositories whose CI is plain pip.
