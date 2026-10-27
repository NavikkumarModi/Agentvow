# Does installing from the repository's lock file lower the inconclusive rate? (2026-10-27)

**Question.** In the detection study most replays of third-party pull requests were inconclusive, and the commonest cause was a missing dependency. A third of the repositories behind those carry a lock file (`uv.lock`, `Pipfile.lock`, ...). Does installing the locked packages first (`AGENTVOW_LOCK=1`, `envsetup.read_lock` / `_install_pins`) turn inconclusive replays into verdicts?

**Method.** `research/envsetup/lock_experiment.py 1`: one pull request from each of the 12 lock-file repositories whose replay was inconclusive in the detection study (the first listed per repository, not randomised), run through the product (`agentvow check --setup auto --run-tests`) twice on the same machine, old ladder (`AGENTVOW_LOCK=0`) and with the lock. Raw rows: local `data/checker_eval/lock_experiment.jsonl`. Small, hand-bounded, one run per cell; no confidence interval means anything at n = 12.

## Result
**Verdicts: 0 of 12 in either mode.** All 24 runs were UNKNOWN.

| repository (pull request) | old ladder | with the lock |
|---|---|---|
| FalkorDB/QueryWeaver#111 (Pipfile.lock) | missing `requests` (5 s) | **tests ran**, 4 collection errors (30 s) |
| Kiln-AI/Kiln#545 | missing `litellm` | missing `kiln_ai`, the project's own package (134 s) |
| PrefectHQ/marvin#1221 | missing `chromadb` | missing `chromadb` (478 s) |
| TracecatHQ/tracecat#1510 | missing `aioboto3` | missing `aioboto3` (421 s) |
| crewAIInc/crewAI#3446 | tests not run | tests not run (316 s) |
| google/clusterfuzz#4928 | missing `aiohttp`, `antlr4`, `flask`, ... | **tests ran**, `AttributeError: module 'pathlib' ...` (102 s) |
| onyx-dot-app/onyx#5243 | missing `bs4`, `dateutil`, ... | same (7 s) |
| oraios/serena#651 | missing `sensai` | tests not run (1315 s) |
| twschiller/open-synthesis#930 | missing `celery` | **tests ran**, Django settings not configured (197 s) |
| Zipstack/unstract#1575 | missing `django`, ... | same (265 s) |
| mlco2/codecarbon#926 | missing `dash`, ... | same (149 s) |
| linkml/linkml#2950 | **tests ran**, `AttributeError` (66 s) | tests not run (307 s) |

- **Progress:** in 3 repositories (QueryWeaver, clusterfuzz, open-synthesis) the lock got the tests to run where the old ladder stopped at a missing dependency. In Kiln it replaced a third-party miss with the project's own package.
- **No change:** 6 repositories, 3 of them because the full lock was too heavy (diagnosed on Tracecat: the 251 locked packages exceeded the 700 MB environment limit, so the code fell back to the old ladder, as designed).
- **Worse:** linkml (old ladder ran the tests; with the lock they were not run) and serena (1,315 seconds to give up).
- **Cost:** the lock run took 3 to 100 times as long (median about 8 times).
- Where the tests now ran, the next obstacle was not dependencies: a Python version the project does not support (`pathlib` in clusterfuzz), a Django settings module, a monorepo's own package import path, collection errors.

## Reading
The lock fixes the layer it targets (third-party packages) in the repositories where it fits the size limit, but that layer was not the only thing between these replays and a verdict. On this sample it lowered the inconclusive rate by zero. It is therefore **off by default** and opt-in (`AGENTVOW_LOCK=1`); the code and tests stay. I did not tune it on these results.

What would be worth trying next, each as its own experiment: the Python version (honouring `requires-python` and `.python-version` instead of whatever interpreter runs Agentvow), the project's own package on the import path for monorepos, a Django settings default for repositories that need one, and installing only what the tests import instead of the whole lock.
