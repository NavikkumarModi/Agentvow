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
        self.assertEqual(setup[:3], ["pip install .", "pip install .[dev]", "pip install -r requirements.txt"])   # base install first, so a failing extra cannot leave the project uninstalled
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


CI_ONE_LINER = """jobs:
  t:
    steps:
      - run: pip install -e .[test] && pytest -q
      - run: pip install winonly
        if: runner.os == 'Windows'
      - run: pip install neverrun
        if: false
      - name: quoted
        "run": pip install quotedkey
      - run: pip install linuxonly
        if: runner.os == 'Linux'
"""


class Hardening(unittest.TestCase):
    def mk(self, files):
        d = Path(tempfile.mkdtemp())
        for n, t in files.items():
            p = d / n
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(t)
        return d

    def test_compound_line_conditions_and_quoted_keys(self):
        setup, env, notes = baseline.ci_setup({"ci.yml": CI_ONE_LINER}, {})
        self.assertEqual(setup, ["pip install -e '.[test]'", "pip install quotedkey", "pip install linuxonly"])   # `a && pytest` split; Windows-only and `if: false` steps skipped

    def test_flow_style_is_refused_not_silently_dropped(self):
        for text in ("jobs:\n  t:\n    steps:\n      - {run: pip install x}\n", "jobs:\n  t:\n    env: {A: b}\n    steps: []\n"):
            with self.assertRaises(ValueError):
                baseline.parse_workflow(text)
        setup, env, notes = baseline.ci_setup({"f.yml": "jobs:\n  t:\n    steps:\n      - {run: pip install x}\n"}, {})
        self.assertEqual(setup, [])
        self.assertTrue(any("not read" in n for n in notes))

    def test_proxy_and_certificate_env_values_are_dropped(self):
        wf = "env:\n  HTTPS_PROXY: http://evil\n  SSL_CERT_FILE: /x\n  GOOD: 1\njobs:\n  t:\n    steps:\n      - run: pytest -q\n"
        setup, env, notes = baseline.ci_setup({"f.yml": wf}, {})
        self.assertEqual(env, {"GOOD": "1"})

    def test_requirements_files_with_index_urls_vcs_or_outside_includes_are_not_installed(self):
        d = self.mk({"requirements.txt": "six==1.16.0\n--index-url http://evil/simple\n", "requirements-extra.txt": "-e git+https://x/y.git#egg=y\n",
                     "requirements-dev.txt": "-r ../outside.txt\n", "requirements-test.txt": "-r requirements-base.txt\n", "requirements-base.txt": "evil @ https://x/e.whl\n",
                     "requirements-ok.txt": "six==1.16.0\n"})
        setup, env, notes = baseline.derive(d)
        self.assertEqual(setup, ["pip install -r requirements-ok.txt"])
        self.assertEqual(sum("left out" in n for n in notes), 5)
        self.assertEqual(baseline.requirements_problem(d, "requirements-ok.txt"), None)

    def test_symlinked_requirements_file_is_refused(self):
        d = self.mk({"real.txt": "six\n"})
        (d / "requirements-link.txt").symlink_to(d / "real.txt")
        self.assertIn("symbolic link", baseline.requirements_problem(d, "requirements-link.txt"))
        self.assertEqual(baseline.derive(d)[0], [])

    def test_line_installing_the_projects_own_name_is_left_out_with_pep503_folding(self):
        d = self.mk({"pyproject.toml": "[project]\nname = 'my.pkg'\n", "Dockerfile": "RUN pip install my-pkg==1.0 && pip install six\n"})
        setup, env, notes = baseline.derive(d)
        self.assertNotIn("pip install my-pkg==1.0", setup)
        self.assertIn("pip install six", setup)
        self.assertTrue(any("project's own name" in n for n in notes))

    def test_input_files_lists_what_was_read(self):
        d = self.mk({"pyproject.toml": "[project]\nname='x'\n", ".github/workflows/ci.yml": "jobs: {}\n", "Dockerfile": "FROM x\n", "requirements-extra.txt": "a"})
        self.assertEqual(set(baseline.input_files(d)), {"pyproject.toml", ".github/workflows/ci.yml", "Dockerfile", "requirements-extra.txt"})


class HookSafety(unittest.TestCase):
    def test_collect_native_never_raises_out_of_the_hook_worker(self):
        from unittest import mock
        from agentvow import cli
        with mock.patch.object(baseline, "prepare", side_effect=OSError("disk")):
            why = cli._collect_native(Path(tempfile.mkdtemp()), "HEAD", 5, False)
        self.assertIn("could not be built", why)
        self.assertIn("OSError", why)

    def test_project_name_comes_from_poetry_setup_cfg_or_setup_py(self):
        from agentvow import envsetup
        for files, want in (({"pyproject.toml": "[tool.poetry]\nname = 'pp'\n"}, "pp"), ({"setup.cfg": "[metadata]\nname = sc\n"}, "sc"), ({"setup.py": "setup(name='sp', version='1')"}, "sp")):
            d = Path(tempfile.mkdtemp())
            for n, t in files.items():
                (d / n).write_text(t)
            self.assertEqual(envsetup._project_name(d), want)


if __name__ == "__main__":
    unittest.main()
