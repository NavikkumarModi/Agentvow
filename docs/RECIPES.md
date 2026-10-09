# Recipes: claims with preconditions

A statement like "all tests pass" is true only under conditions the agent's own environment satisfies and the reader cannot see: installed packages, environment variables, a Python version. A **recipe** is a small JSON file in which the agent declares those conditions. Agentvow builds a clean environment from the declared steps **only** (nothing is added on the agent's behalf), runs the declared test command at the base and head commits in the sandbox, and uses that independently executed result as evidence. If the replay cannot reproduce the result, the declaration was insufficient, and the report says so.

```json
{
  "schema": "agentvow-recipe/1",
  "python": "3.12",
  "setup": ["pip install -e .[dev]", "pip install pytest-asyncio"],
  "prepare": ["python scripts/make_fixture.py"],
  "test": "pytest -q tests/test_parser.py",
  "env": {"APP_MODE": "test"},
  "notes": "free text, not executed"
}
```

```bash
agentvow check --repo . --transcript final_message.txt --recipe recipe.json
```

## What is executable (and nothing else)
- `setup`: up to 12 steps, each `pip install ...` with plain requirements, `-r`/`-c` files or `.`/paths **inside the repository**. Index/URL/VCS options, absolute paths, `..`, shell syntax are rejected.
- `test`: `pytest ...`, `python -m pytest ...` or `python -m unittest ...`; paths inside the repository; pytest plugin loading (`-p`), `--rootdir` and similar are rejected.
- `env`: plain `NAME=value` pairs; names for `PATH`, `HOME`, `PYTHON*`, `PIP_*`, `GIT_*`, `LD_*`, secrets (`*KEY*`, `*TOKEN*`, …) are rejected.
- A rejected recipe runs **nothing**; the claim stays UNKNOWN and the report says the recipe was rejected and why.
- The agent proposes; deterministic, sandboxed execution decides. No language model is in the verdict path. Setup steps run with network access (they must) inside the install sandbox with the usual size/disk guards, on a throwaway environment.

## Instruction to give an agent
> Before you finish, write `.agentvow-recipe.json` (schema `agentvow-recipe/1`) declaring exactly what is needed to reproduce the test run your claim relies on from a clean checkout: the `pip install` steps, the test command, and any environment variables. Do not claim anything your recipe does not reproduce.

## What the result means
- **Supported / not contradicted** under the declared preconditions: the agent's own recipe reproduced the result independently. It does not show the tests are good, or that the recipe is minimal.
- **Unknown, "the declared preconditions were insufficient"**: the replay could not run (missing dependency, import error). The agent's success depended on something it did not declare.
- This is a research instrument as well as a feature: the fraction of recipes that replay, and why they fail, is the measurement (`docs/research/forecast_grounding/DIRECTION.md`).

## `prepare`: generated fixtures
If the tests need files that a repository script generates and that are not committed (the pilot's "generated file" tasks), declare the script:

```json
{"schema": "agentvow-recipe/1", "setup": ["pip install pytest"], "prepare": ["python scripts/make_fixture.py"], "test": "pytest -q"}
```
Each `prepare` entry must be `python <script.py inside the repository> [plain args]` (at most 3). It runs inside the same sandbox as the tests (network denied, writes only inside the worktree), before the tests, at the base and head commits. It is repository code, exactly like the tests themselves; it is not a shell line.
