import sys, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agentvow import baseline  # noqa: E402

WF = """name: ci
on: [push]
env:
  TOP: one
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - run: pip install flake8
      - run: flake8 .
  test:
    runs-on: ubuntu-latest
    env:
      JOBV: two
    steps:
    - uses: actions/checkout@v4
    # a comment at the wrong indent
    - name: deps
      run: |
        python -m pip install --upgrade pip
        pip install -e ".[dev]"
        pip install httpx \\
          respx
    - name: folded
      run: >
        pip install
        pytest-asyncio
      env:
        STEPV: three
        SECRETY: ${{ secrets.X }}
    - run: pytest -q
"""


class Parser(unittest.TestCase):
    def test_jobs_steps_block_and_env(self):
        top, jobs = baseline.parse_workflow(WF)
        self.assertEqual(top, {"TOP": "one"})
        self.assertEqual([j[0] for j in jobs], ["lint", "test"])
        name, jenv, steps = jobs[1]
        self.assertEqual(jenv, {"JOBV": "two"})
        runs = [s["run"] for s in steps if s["run"]]
        self.assertIn('pip install -e ".[dev]"', runs[0])
        self.assertEqual(runs[1], "pip install pytest-asyncio")   # folded scalar joined
        self.assertEqual(steps[2]["env"]["STEPV"], "three")

    def test_first_test_job_only_and_env_and_secrets_skipped(self):
        setup, env, notes = baseline.ci_setup({"ci.yml": WF}, {})
        self.assertEqual(setup, ["pip install -e '.[dev]'", "pip install httpx respx", "pip install pytest-asyncio"])   # lint job's flake8 is not taken
        self.assertEqual(env, {"TOP": "one", "JOBV": "two", "STEPV": "three"})   # secrets expression left out
        self.assertFalse(any("flake8" in s for s in setup))

    def test_outside_subset_is_refused_not_guessed(self):
        with self.assertRaises(ValueError):
            baseline.parse_workflow("a: 1\n---\nb: 2\n---\nc: 3\n")

    def test_agrees_with_pyyaml_on_this_repositorys_workflows(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed")
        import re
        norm = lambda s: re.sub(r"\s+", " ", "\n".join(l for l in (s or "").splitlines() if not l.lstrip().startswith("#"))).strip()
        files = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
        self.assertTrue(files)
        for f in files:
            y = yaml.safe_load(f.read_text())
            ref = [(jn, [norm(str(s["run"])) for s in (j or {}).get("steps", []) if isinstance(s, dict) and "run" in s]) for jn, j in y["jobs"].items()]
            _, jobs = baseline.parse_workflow(f.read_text())
            self.assertEqual(ref, [(jn, [norm(s["run"]) for s in st if s["run"]]) for jn, _e, st in jobs], f.name)


class Derive(unittest.TestCase):
    def mk(self, files):
        d = Path(tempfile.mkdtemp())
        for n, t in files.items():
            p = d / n
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(t)
        return d

    def test_order_ladder_ci_docker_requirements(self):
        d = self.mk({"pyproject.toml": "[project]\nname='x'\n[project.optional-dependencies]\ndev=['q']\n", "requirements.txt": "z", ".github/workflows/ci.yml": WF,
                     "Dockerfile": "FROM python:3.11\nRUN pip install numpy==1.26.4\n", "requirements-extra.txt": "y", "requirements-docs.txt": "d"})
        setup, env, notes = baseline.derive(d)
        self.assertEqual(setup[:2], ["pip install .[dev]", "pip install -r requirements.txt"])
        self.assertIn("pip install httpx respx", setup)
        self.assertIn("pip install numpy==1.26.4", setup)
        self.assertEqual(setup[-1], "pip install -r requirements-extra.txt")   # docs requirements excluded
        self.assertEqual(env["STEPV"], "three")

    def test_nothing_found(self):
        self.assertEqual(baseline.derive(self.mk({"README.md": "x"}))[:2], ([], {}))

    def test_setup_is_capped_and_every_line_validates(self):
        from agentvow import recipe
        files = {f"requirements-{c}.txt": "a" for c in "abcdefghijklmnop"}
        setup, env, notes = baseline.derive(self.mk(files))
        self.assertLessEqual(len(setup), recipe.MAX_STEPS)
        recipe.parse({"schema": recipe.SCHEMA, "setup": setup, "test": "python -m pytest -q"})


if __name__ == "__main__":
    unittest.main()
