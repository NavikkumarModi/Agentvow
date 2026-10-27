import argparse
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agentvow import cli, envsetup  # noqa: E402


def tree(files):
    d = Path(tempfile.mkdtemp())
    for p, c in files.items():
        (d / p).parent.mkdir(parents=True, exist_ok=True)
        (d / p).write_text(c)
    return d


PKG = "[project]\nname = 'x'\nversion = '0'\n"


class Discover(unittest.TestCase):
    def test_requirements_files_and_sub_projects_are_found_and_the_noise_is_not(self):
        d = tree({"pyproject.toml": PKG, "src/requirements.txt": "flask\n", "requirements/test.txt": "pytest\n", "requirements/docs.txt": "sphinx\n", "requirements-dev.txt": "x\n",
                  "requirements-windows.txt": "y\n", "packages/a/pyproject.toml": PKG + "[project.optional-dependencies]\ntests-unit = ['pytest']\ndocs = ['sphinx']\n", "packages/b/setup.py": "setup()\n",
                  "tools/lint/pyproject.toml": "[tool.black]\nline-length = 100\n", "docs/conf/pyproject.toml": PKG, "node_modules/x/pyproject.toml": PKG, ".hidden/pyproject.toml": PKG})
        got = envsetup.discover(d)
        self.assertEqual(got["requirements"], ["requirements/test.txt", "src/requirements.txt"])   # not the root file the ladder already reads, not docs or platform variants
        self.assertEqual([s["path"] for s in got["subprojects"]], ["packages/a", "packages/b"])
        self.assertEqual(got["subprojects"][0]["extras"], ["tests-unit"])   # a test-like extra by any of its words, not the docs one
        self.assertEqual(got["local_roots"], ["packages/a", "packages/b"])

    def test_it_is_bounded_in_depth_and_in_number(self):
        d = tree({f"p{i:02d}/pyproject.toml": PKG for i in range(20)} | {f"r{i}/requirements.txt": "a\n" for i in range(12)} | {"a/b/c/d/pyproject.toml": PKG, "a/b/c/d/requirements.txt": "z\n"})
        got = envsetup.discover(d)
        self.assertLessEqual(len(got["subprojects"]), envsetup.MAX_SUBPROJECTS); self.assertLessEqual(len(got["requirements"]), envsetup.MAX_REQ_FILES)
        self.assertNotIn("a/b/c/d", [s["path"] for s in got["subprojects"]])
        self.assertNotIn("a/b/c/d/requirements.txt", got["requirements"])

    def test_the_root_itself_and_an_empty_repository(self):
        self.assertEqual(envsetup.discover(tree({"pyproject.toml": PKG})), {"requirements": [], "subprojects": [], "local_roots": []})
        self.assertEqual(envsetup.discover(tree({})), {"requirements": [], "subprojects": [], "local_roots": []})

    def test_broad_extras_need_a_test_word_and_no_docs_word(self):
        self.assertEqual(envsetup._broad(["tests-unit", "dev_tools", "docs", "lint", "test-docs", "all", "ci"]), ["ci", "dev_tools", "tests-unit"])


class BuildWithDiscovery(unittest.TestCase):
    def build(self, files, **env):
        r = tree(files)
        calls = []
        t = Path(tempfile.mkdtemp())
        e = {k: v for k, v in os.environ.items() if k not in ("AGENTVOW_DISCOVER", "AGENTVOW_LOCK")} | env
        with mock.patch.object(envsetup, "_pip", lambda venv, proj, home, args, *a: (calls.append(list(args)) or (0, ""))), mock.patch.object(envsetup, "uninstall_project_dists"), \
                mock.patch.dict(os.environ, e, clear=True):
            out = envsetup.build_env(r, t / "venv", t / "home")
        return out, calls

    FILES = {"pyproject.toml": PKG, "src/requirements.txt": "flask\n", "packages/a/pyproject.toml": PKG + "[project.optional-dependencies]\ntests = ['pytest']\n",
             "packages/b/pyproject.toml": PKG + "[dependency-groups]\ntest-extra = ['pytest']\n"}

    def test_with_discovery_the_extra_steps_come_after_the_root_and_before_pytest(self):
        (py, notes, aborted), calls = self.build(self.FILES, AGENTVOW_DISCOVER="1")
        flat = [" ".join(c) for c in calls]
        i_root = next(i for i, c in enumerate(flat) if c.endswith(" ."))
        i_sub = next(i for i, c in enumerate(flat) if "packages/a[tests]" in c)
        i_group = next(i for i, c in enumerate(flat) if "--group packages/b/pyproject.toml:test-extra" in c)
        i_req = next(i for i, c in enumerate(flat) if c.endswith("-r src/requirements.txt"))
        i_pytest = next(i for i, c in enumerate(flat) if c.endswith(" pytest"))
        self.assertTrue(i_root < i_sub < i_pytest and i_root < i_group < i_pytest and i_root < i_req < i_pytest, flat)
        self.assertTrue(any("discovered 2 sub-project(s) and 1 requirements file(s)" in n for n in notes))

    def test_without_the_switch_nothing_beyond_the_ladder_is_installed(self):
        (py, notes, aborted), calls = self.build(self.FILES)
        flat = " | ".join(" ".join(c) for c in calls)
        self.assertNotIn("packages/a", flat); self.assertNotIn("src/requirements.txt", flat)

    def test_a_failing_discovered_step_is_recorded_and_the_rest_still_run(self):
        r = tree(self.FILES)
        calls = []
        t = Path(tempfile.mkdtemp())

        def pip(venv, proj, home, args, *a):
            calls.append(list(args))
            return (1, "boom") if "packages/a[tests]" in " ".join(args) else (0, "")
        with mock.patch.object(envsetup, "_pip", pip), mock.patch.object(envsetup, "uninstall_project_dists"), mock.patch.dict(os.environ, {"AGENTVOW_DISCOVER": "1"}):
            py, notes, aborted = envsetup.build_env(r, t / "venv", t / "home")
        self.assertIsNone(aborted); self.assertTrue(any("sub-project packages/a failed" in n for n in notes)); self.assertTrue(any(c[-1] == "pytest" for c in calls))

    def test_a_resource_guard_in_a_discovered_step_aborts_as_it_does_for_every_step(self):
        r = tree(self.FILES)
        t = Path(tempfile.mkdtemp())
        with mock.patch.object(envsetup, "_pip", lambda venv, proj, home, args, *a: (125, "environment too heavy") if "packages/a[tests]" in " ".join(args) else (0, "")), \
                mock.patch.dict(os.environ, {"AGENTVOW_DISCOVER": "1"}):
            py, notes, aborted = envsetup.build_env(r, t / "venv", t / "home")
        self.assertEqual(aborted, "environment too heavy")


class LocalRoots(unittest.TestCase):
    def args(self, **kw):
        a = argparse.Namespace(run_tests=True, python="/x/python", test_cmd=None, test_timeout=10, changed_coverage=False, ci=False, ci_sha=None, ci_wait=0, new_test_failures="unknown", evidence_pack=False)
        for k, v in kw.items():
            setattr(a, k, v)
        return a

    def suites(self, a):
        seen = {}
        fake = mock.Mock(scope="s")
        with mock.patch.object(cli, "collect_test_evidence", side_effect=lambda repo, base, suites, *r, **k: seen.update(suites=suites)), mock.patch.object(cli, "check", return_value=fake):
            try:
                cli._run(a, Path(tempfile.mkdtemp()), "HEAD", "given", "text")
            except AttributeError:   # the report options after the suites are not under test
                pass
        return seen["suites"]

    def test_discovered_sub_projects_are_put_on_the_import_path_of_the_tests(self):
        s = self.suites(self.args(_local_roots=["packages/a", "packages/b"]))
        self.assertEqual(s[0][3]["pythonpath_rel"], ["packages/a", "packages/b"])

    def test_nothing_is_added_without_them(self):
        s = self.suites(self.args())
        self.assertNotIn("pythonpath_rel", s[0][3])

    def test_run_auto_sets_them_only_with_the_switch(self):
        r = tree({"pyproject.toml": PKG, "packages/a/pyproject.toml": PKG})
        for env, want in (({"AGENTVOW_DISCOVER": "1"}, ["packages/a"]), ({}, None)):
            a = self.args(setup="auto")
            e = {k: v for k, v in os.environ.items() if k != "AGENTVOW_DISCOVER"} | env
            with mock.patch.object(cli.envsetup, "build_env", return_value=("/x/python", [], None)), mock.patch.object(cli, "_run", return_value="d"), mock.patch.dict(os.environ, e, clear=True):
                cli._run_auto(a, r, "HEAD", "given", "text")
            self.assertEqual(getattr(a, "_local_roots", None), want)


if __name__ == "__main__":
    unittest.main()
