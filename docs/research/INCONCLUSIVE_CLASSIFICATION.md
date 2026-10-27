# Why do replays of third-party pull requests end inconclusive? Classification of 36 repositories (2026-10-27)

**Question.** After the lock-file and Python-version experiments moved nothing, which obstacle actually stands between these replays and a verdict? **Method** (`research/envsetup/classify_inconclusive.py`): for the 36 repositories whose replay was inconclusive in the detection study, read their files through the GitHub API (default branch today, so an approximation of the state at the pull request; nothing executed), find where each declares its dependencies, and compare with the modules the replays reported missing (the first four per run; 60 module mentions) and with what the zero-config ladder (`envsetup.build_env`) reads: the root `pyproject.toml` / `setup.py` with the extras `test`, `tests`, `testing`, `dev`, `develop`, PEP 735 groups of those names, and eight fixed requirements-file names at the root. The rules are mine and approximate (module names are matched to package names by normalisation plus a short alias table), so read the counts as ±3 repositories.

## By repository (36)
| class | repositories | what it means |
|---|---|---|
| **No root project to install** | 9 | no root `pyproject.toml`/`setup.py`; dependencies are in requirements files elsewhere (clusterfuzz: `src/requirements.txt`), sub-packages of a monorepo (llamafarm, rhesis, agent-framework, langchain-google) or not declared (dbt-data-reliability, exospherehost, jaseci, vscode-mypy) |
| **Declared in a place the ladder does not read** | 8 | root project exists, but the missing modules are declared in sub-projects (unstract, crewAI), non-test extras or groups (QueryWeaver, onyx, pytensor), or other requirements files (hud-python, AzureTRE, arcade-mcp) |
| **Declared where the ladder looks, yet missing** | 7 | install failed, hit the size limit, or the module is the project's own package that is not importable (Kiln `kiln_ai`, tracecat `tracecat_registry`, serena, quay, scoringengine, vision-parse, cryodrgn) |
| **Declared nowhere the files show** | 3 | transitive, local or system (foamlib `multidict` = the dependency-drift case, starfish `pkg_resources`, Fast-LLM `xdist`) |
| **No missing module named** | 9 | the replay failed another way (a Django settings module, collection errors, an unsupported Python, no tests found) |

**17 of 36 (47%) declare their dependencies somewhere the ladder does not read** (9 with no root project plus 8 with a root project whose test dependencies sit elsewhere).

## By missing module (60 mentions)
| where it is declared | mentions | share |
|---|---|---|
| in a sub-project | 17 | 28% |
| in another requirements, Pipfile or conda file | 8 | 13% |
| in a non-test extra or a dependency group | 4 | 7% |
| **in total, in a place the ladder does not read** | **29** | **48%** |
| installed by the ladder, still missing | 13 | 22% |
| declared nowhere the files show | 18 | 30% (own packages and local modules such as `core`, `app`, `config`, truncated names, transitive or system packages) |

## Reading
- The largest actionable cause is **dependency discovery**: the ladder installs from a fixed set of places, and about half of what the replays missed was declared somewhere else in the repository. This is also why the lock file and the Python version did nothing: neither addresses it (a lock file helps only when one exists and fits the size limit, and a version is irrelevant before dependencies exist).
- The second cause is the project's **own package not importable** (monorepos with a `src/` or workspace layout): `kiln_ai`, `tracecat_registry`, `agent_framework`, `rhesis`.
- A third part is **not dependencies at all**: settings modules, services, system libraries (9 repositories).
- The dependency-drift case (foamlib) is a different class again (pins), already documented.

## What would be worth building, and how to know
Discover declared dependencies beyond the root: install the root project as now, and additionally the sub-projects (`pyproject.toml` / `setup.py` up to a small depth) and requirements files (`requirements*.txt`, `*/requirements*.txt`) found by reading the repository, within the existing size, time and sandbox limits, and put the project's own packages on the import path. Measure it as the lock-file experiment was measured: the 17 repositories above, old ladder against the new one, same machine. Success is not "more dependencies installed" but more replays that reach a verdict; the two earlier experiments are the reason not to assume it.
