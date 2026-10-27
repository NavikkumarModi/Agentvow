import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agentvow import envsetup, pyversion  # noqa: E402

CUR = (sys.version_info[0], sys.version_info[1])


def repo(files):
    d = Path(tempfile.mkdtemp())
    for p, c in files.items():
        (d / p).parent.mkdir(parents=True, exist_ok=True)
        (d / p).write_text(c)
    return d


CANDS = [((3, 10), "/py/3.10"), ((3, 11), "/py/3.11"), ((3, 12), "/py/3.12"), ((3, 13), "/py/3.13")]


class Specs(unittest.TestCase):
    def test_requires_python_strings(self):
        ok = pyversion.parse_spec(">=3.10,<3.13")
        self.assertEqual([ok((3, m)) for m in (9, 10, 12, 13)], [False, True, True, False])
        self.assertTrue(pyversion.parse_spec(">= 3.10, <3.14")((3, 13)))
        self.assertTrue(pyversion.parse_spec("==3.12.*")((3, 12))); self.assertFalse(pyversion.parse_spec("==3.12.*")((3, 13)))
        self.assertFalse(pyversion.parse_spec("!=3.11.*")((3, 11))); self.assertTrue(pyversion.parse_spec("!=3.11.*")((3, 12)))
        self.assertTrue(pyversion.parse_spec("~=3.10")((3, 12))); self.assertFalse(pyversion.parse_spec("~=3.10")((3, 9)))
        self.assertTrue(pyversion.parse_spec("'>=3.9'")((3, 9)))
        for bad in ("", None, "junk", ">=three", ">=3", ">=3.10,junk"):
            self.assertIsNone(pyversion.parse_spec(bad), bad)


class Declared(unittest.TestCase):
    def test_every_source_is_read_as_text(self):
        r = repo({"pyproject.toml": '[project]\nrequires-python = ">=3.10,<3.13"\n', ".python-version": "3.12.9\n",
                  ".github/workflows/ci.yml": "jobs:\n  t:\n    strategy:\n      matrix:\n        python-version: ['3.10', '3.11']\n    steps:\n      - uses: actions/setup-python@v5\n        with:\n          python-version: ${{ matrix.python-version }}\n"})
        d = pyversion.declared(r)
        self.assertEqual(d, {"requires": ">=3.10,<3.13", "pinned": [(3, 12)], "ci": [(3, 10), (3, 11)]})

    def test_setup_cfg_setup_py_and_a_matrix_written_as_a_list(self):
        self.assertEqual(pyversion.declared(repo({"setup.cfg": "[options]\npython_requires = >=3.8\n"}))["requires"], ">=3.8")
        self.assertEqual(pyversion.declared(repo({"setup.py": "setup(python_requires='>=3.9')\n"}))["requires"], ">=3.9")
        r = repo({".github/workflows/t.yml": "matrix:\n  python-version:\n    - '3.11'\n    - \"3.12\"\n    - 3.13\n"})
        self.assertEqual(pyversion.declared(r)["ci"], [(3, 11), (3, 12), (3, 13)])

    def test_nothing_declared_is_nothing(self):
        self.assertEqual(pyversion.declared(repo({"README.md": "x"})), {"requires": None, "pinned": [], "ci": []})
        self.assertIsNone(pyversion.declared(repo({"pyproject.toml": 'requires-python = "junk"\n'}))["requires"])


class Choose(unittest.TestCase):
    def pick(self, files, cands=CANDS):
        with mock.patch.object(pyversion.sys, "version_info", (3, 13, 5)), mock.patch.object(pyversion.sys, "executable", "/py/3.13"):
            return pyversion.choose(repo(files), cands)

    def test_a_pin_beats_ci_which_beats_nothing(self):
        path, ver, why = self.pick({".python-version": "3.11\n", ".github/workflows/t.yml": "python-version: ['3.12']\n"})
        self.assertEqual((path, ver), ("/py/3.11", (3, 11))); self.assertIn(".python-version pins 3.11", why)
        path, ver, why = self.pick({".github/workflows/t.yml": "python-version: ['3.11', '3.12']\n"})
        self.assertEqual((path, ver), ("/py/3.12", (3, 12))); self.assertIn("CI tests", why)

    def test_a_matrix_that_includes_the_running_version_changes_nothing_and_the_newest_is_never_preferred(self):
        self.assertEqual(self.pick({".github/workflows/t.yml": "python-version: ['3.10', '3.11', '3.12', '3.13']\n"}, cands=CANDS + [((3, 14), "/py/3.14")])[:2], ("/py/3.13", (3, 13)))
        path, ver, _ = self.pick({".github/workflows/t.yml": "python-version: ['3.11', '3.14']\n"}, cands=CANDS + [((3, 14), "/py/3.14")])
        self.assertEqual(ver, (3, 11))   # the highest tested version below the running one, not the newest

    def test_the_constraint_always_wins_over_ci_and_pins(self):
        path, ver, _ = self.pick({"pyproject.toml": 'requires-python = ">=3.10,<3.12"\n', ".github/workflows/t.yml": "python-version: ['3.13']\n"})
        self.assertEqual(ver, (3, 11))   # 3.13 is what CI tests but the constraint excludes it; the highest allowed version is not what CI tests either, so the closest is used
        path, ver, _ = self.pick({"pyproject.toml": 'requires-python = ">=3.10,<3.13"\n', ".python-version": "3.13\n"})
        self.assertNotEqual(ver, (3, 13))

    def test_the_closest_installed_version_is_used_when_ci_tests_one_that_is_not_installed(self):
        path, ver, why = self.pick({".github/workflows/t.yml": "python-version: ['3.9']\n"})
        self.assertEqual(ver, (3, 10)); self.assertIn("closest installed version is 3.10", why)

    def test_nothing_declared_or_the_running_version_is_fine_keeps_the_running_interpreter(self):
        self.assertEqual(self.pick({"README.md": "x"}), ("/py/3.13", (3, 13), ""))
        self.assertEqual(self.pick({"pyproject.toml": 'requires-python = ">=3.10"\n'}), ("/py/3.13", (3, 13), ""))
        self.assertEqual(self.pick({".github/workflows/t.yml": "python-version: ['3.13']\n"})[:2], ("/py/3.13", (3, 13)))

    def test_a_newer_installed_interpreter_is_not_preferred_when_the_running_one_is_allowed(self):
        self.assertEqual(self.pick({"pyproject.toml": 'requires-python = ">=3.10"\n'}, cands=CANDS + [((3, 14), "/py/3.14")]), ("/py/3.13", (3, 13), ""))

    def test_a_running_interpreter_the_constraint_excludes_is_replaced_by_the_highest_allowed(self):
        path, ver, why = self.pick({"pyproject.toml": 'requires-python = ">=3.10,<3.13"\n'})
        self.assertEqual((path, ver), ("/py/3.12", (3, 12))); self.assertIn("excludes 3.13", why)

    def test_when_no_installed_version_satisfies_the_running_one_is_kept_and_it_is_said(self):
        path, ver, why = self.pick({"pyproject.toml": 'requires-python = ">=3.12,<3.13"\n'}, cands=[((3, 10), "/py/3.10"), ((3, 13), "/py/3.13")])
        self.assertEqual((path, ver), ("/py/3.13", (3, 13))); self.assertIn("no installed Python satisfies", why)


class MakeVenv(unittest.TestCase):
    def fake_run(self, results):
        calls = []

        def run(argv, **kw):
            calls.append(argv)
            return results(argv)
        return run, calls

    def ok(self, argv):
        return mock.Mock(returncode=0, stdout="", stderr="")

    def test_the_chosen_interpreter_makes_the_venv_and_it_is_noted(self):
        run, calls = self.fake_run(self.ok)
        notes = []
        with mock.patch.object(envsetup.pyversion, "choose", return_value=("/py/3.11", (3, 11), "CI tests 3.11")), mock.patch.object(envsetup.subprocess, "run", run), \
                mock.patch.dict(os.environ, {"AGENTVOW_PYVERSION": "1"}):
            envsetup.make_venv(Path("/v"), Path("/r"), notes)
        self.assertEqual(calls[0][:4], ["/py/3.11", "-I", "-m", "venv"])
        self.assertIn("CI tests 3.11", notes); self.assertIn("environment built with Python 3.11", notes)

    def test_a_chosen_interpreter_that_cannot_make_a_venv_falls_back_to_the_running_one(self):
        run, calls = self.fake_run(lambda argv: mock.Mock(returncode=1, stdout="", stderr="no venv module") if argv[0] == "/py/3.11" else self.ok(argv))
        notes = []
        with mock.patch.object(envsetup.pyversion, "choose", return_value=("/py/3.11", (3, 11), "x")), mock.patch.object(envsetup.subprocess, "run", run), mock.patch.object(envsetup.shutil, "rmtree"), \
                mock.patch.dict(os.environ, {"AGENTVOW_PYVERSION": "1"}):
            r = envsetup.make_venv(Path("/v"), Path("/r"), notes)
        self.assertEqual(r.returncode, 0); self.assertEqual(calls[-1][0], sys.executable)
        self.assertTrue(any("could not be made with /py/3.11" in n for n in notes))

    def test_it_is_off_unless_asked_for_and_a_failing_choice_never_stops_the_build(self):
        run, calls = self.fake_run(self.ok)
        env = {k: v for k, v in os.environ.items() if k != "AGENTVOW_PYVERSION"}
        with mock.patch.object(envsetup.pyversion, "choose", return_value=("/py/3.11", (3, 11), "x")), mock.patch.object(envsetup.subprocess, "run", run), mock.patch.dict(os.environ, env, clear=True):
            envsetup.make_venv(Path("/v"), Path("/r"), [])
        self.assertEqual(calls[0][0], sys.executable)
        run, calls = self.fake_run(self.ok)
        with mock.patch.object(envsetup.pyversion, "choose", side_effect=RuntimeError("boom")), mock.patch.object(envsetup.subprocess, "run", run), mock.patch.dict(os.environ, {"AGENTVOW_PYVERSION": "1"}):
            envsetup.make_venv(Path("/v"), Path("/r"), [])
        self.assertEqual(calls[0][0], sys.executable)


if __name__ == "__main__":
    unittest.main()
