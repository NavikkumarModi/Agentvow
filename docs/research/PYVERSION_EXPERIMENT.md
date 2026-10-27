# Does building with the repository's Python version lower the inconclusive rate? (2026-10-27)

**Question.** Several replays of third-party pull requests were inconclusive in ways that smelled like a Python version problem (`pathlib` attributes, removed stdlib behaviour). Does `AGENTVOW_PYVERSION=1` (`agentvow/pyversion.py`: `.python-version`, the versions the repository's CI tests, `requires-python`, among installed interpreters) lower the inconclusive rate?

**Method.** `research/envsetup/pyversion_experiment.py`, run on the 5 repositories where the choice is plainly 3.13 to 3.11 on the machine used (clusterfuzz, marvin, hud-python, llamafarm, cryodrgn): one pull request each that was inconclusive in the detection study, run through the product (`agentvow check --setup auto --run-tests`) with the feature off and on, same machine. I confirmed afterwards, on fresh shallow clones, that the choice is 3.11 for all five and that the environment is built with 3.11 (`environment built with Python 3.11`). Five repositories, one run each, chosen by the plain-swap criterion, not randomised: a diagnostic, not a rate.

## Result
**0 verdicts of 5 in either mode; the outcome was identical with the feature on and off.**
| repository | off | on |
|---|---|---|
| google/clusterfuzz | missing `aiohttp`, `antlr4`, `flask`, ... (11 s) | same (10 s) |
| PrefectHQ/marvin | missing `chromadb` | same |
| ml-struct-bio/cryodrgn | missing `yaml` | same |
| llama-farm/llamafarm | missing `atomic_agents`, `core`, `dotenv`, `pydantic` | same |
| hud-evals/hud-python | tests not run: `project install: environment too heavy` | same |

## Reading
The interpreter was not what stood between these replays and a verdict. In four of the five the zero-config ladder installed none of the project's dependencies at all (the run takes about ten seconds and the first import fails), so which Python ran the import did not matter; the fifth hits the 700 MB environment limit. The earlier lock-file experiment showed the other side: once dependencies were installed (clusterfuzz with the lock), the next error *was* a Python-version one (`pathlib`). So the version choice can only matter after dependency installation works; on its own it moved nothing. It stays **opt-in** (`AGENTVOW_PYVERSION=1`), unchanged.

What stands in front of a verdict for these repositories, in order: the ladder does not find where the dependencies are declared (monorepo sub-packages, `src/requirements.txt`, optional extras), then the size limit, then project-specific setup (a Django settings module, the project's own package on the import path), then the Python version. The next experiment should classify, for the 36 inconclusive repositories, which of these each one needs, before building another fix.
