# Does discovering dependencies beyond the repository root lower the inconclusive rate? (2026-10-27)

**Question.** The classification (`INCONCLUSIVE_CLASSIFICATION.md`) found 17 of 36 inconclusive repositories declaring their dependencies where the install ladder does not read. `AGENTVOW_DISCOVER=1` (`envsetup.discover`) installs sub-projects, requirements files in sub-folders and test-like extras or groups, and puts the sub-projects on the import path. Does it turn inconclusive replays into verdicts?

**Method.** `research/envsetup/discover_experiment.py 5`: the first 5 repositories (alphabetical) of the 17, one pull request each that was inconclusive in the detection study, run through the product (`agentvow check --setup auto --run-tests`) with the feature off and on, same machine. Five repositories, one run each: a diagnostic.

## Result
**0 verdicts of 5 in either mode.**
| repository | off | on |
|---|---|---|
| ArcadeAI/arcade-mcp#557 | tests ran, 1 failed (15 s) | missing `arcade_cli`, `arcade_evals` (60 s): **worse** |
| FalkorDB/QueryWeaver#111 | missing `requests` | same |
| crewAIInc/crewAI#3446 | tests not run (too heavy) | same |
| elementary-data/dbt-data-reliability#861 | missing `dbt` | same |
| google/clusterfuzz#4928 | missing `aiohttp`, `antlr4`, `flask`, ... | missing `aiohttp`, `antlr4`, `dateutil`, `flask` |

## Why it did nothing, checked at the pull request's own commit
- **The classification looked at the wrong state.** It read each repository's default branch *today*; the replays ran the *pull request's* commit. At the pull request's commit clusterfuzz has no `requirements.txt` under `src/`: its dependencies are in `src/Pipfile` (pipenv), which `pip` cannot install, so discovery found a sub-project (`src`, with a `setup.py`) and no requirements file. Reading today's tree overstated what was discoverable.
- **arcade-mcp** has packages that are plain folders (`libs/arcade-cli/arcade_cli`, `libs/arcade-evals/arcade_evals`) with no `pyproject.toml`, so they are not sub-projects and not on the import path, while the alphabetical limit of 8 sub-projects was spent on `contrib/` and `toolkits/`. Discovery installed and then removed packages the tests do not need, and still did not make the two the tests do need importable.
- **QueryWeaver and clusterfuzz** keep dependencies in a `Pipfile` / `Pipfile.lock`; **crewAI** is too heavy for the 700 MB limit; **dbt-data-reliability** declares nothing the files show.

## Reading
Three attempts at lowering the inconclusive rate for third-party pull requests (the repository's lock file, the Python version, discovery of dependencies beyond the root) have produced no verdicts in 22 repository runs, and one made a repository worse. The pattern is that each repository's obstacle is specific (a Pipfile in a sub-folder, a package without its own project file, a size limit, a settings module). A general reconstruction from the repository alone does not become reliable by adding places to look. **`AGENTVOW_DISCOVER` stays opt-in**; the code and its tests stay.

Two things this does not say: the product's other paths do not depend on this reconstruction (an agent's captured environment reproduced 91% of valid runs in B6; the gate workflow can use the repository's own CI install steps), and nothing here measured those CI steps on these repositories. That comparison, the same pull requests through `baseline.prepare` (the environment derived from the repository's CI workflows and Dockerfiles, used by the evidence pack and the gate) instead of the zero-config ladder, is the measurement that would say how often the pull-request gate itself ends UNKNOWN.
