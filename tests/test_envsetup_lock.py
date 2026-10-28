import json
import os
import sys
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agentvow import envsetup  # noqa: E402


def repo(files):
    d = Path(tempfile.mkdtemp())
    for p, c in files.items():
        (d / p).parent.mkdir(parents=True, exist_ok=True)
        (d / p).write_text(c)
    return d


UV = '''version = 1
[[package]]
name = "requests"
version = "2.32.3"
source = { registry = "https://pypi.org/simple" }
[[package]]
name = "My_Pkg"
version = "1.0"
source = { registry = "https://pypi.org/simple" }
[[package]]
name = "gitdep"
version = "0.1"
source = { git = "https://github.com/x/y?rev=abc" }
[[package]]
name = "thisproject"
version = "0.0.1"
source = { editable = "." }
[[package]]
name = "forked"
version = "1.0"
source = { registry = "https://pypi.org/simple" }
[[package]]
name = "forked"
version = "2.0"
source = { registry = "https://pypi.org/simple" }
[[package]]
name = "--index-url=https://evil"
version = "1"
source = { registry = "https://pypi.org/simple" }
[[package]]
name = "okname"
version = "1; rm -rf"
source = { registry = "https://pypi.org/simple" }
'''


class ReadLock(unittest.TestCase):
    def test_uv_lock_keeps_only_published_single_version_packages_with_safe_names(self):
        pins, name = envsetup.read_lock(repo({"uv.lock": UV}))
        self.assertEqual(name, "uv.lock")
        self.assertEqual(pins, ["My_Pkg==1.0", "requests==2.32.3"])   # no git, editable, forked (two versions), option-like name or shell-like version

    def test_poetry_pdm_and_pipfile_locks(self):
        poetry = '[[package]]\nname = "attrs"\nversion = "23.1.0"\n[[package]]\nname = "fromgit"\nversion = "1.0"\n[package.source]\ntype = "git"\nurl = "https://x"\n'
        self.assertEqual(envsetup.read_lock(repo({"poetry.lock": poetry}))[0], ["attrs==23.1.0"])
        pdm = '[[package]]\nname = "six"\nversion = "1.16.0"\n[[package]]\nname = "loc"\nversion = "0.1"\npath = "./loc"\n'
        self.assertEqual(envsetup.read_lock(repo({"pdm.lock": pdm}))[0], ["six==1.16.0"])
        pipfile = json.dumps({"default": {"idna": {"version": "==3.4"}, "gitp": {"git": "https://x", "version": "==1"}}, "develop": {"pytest": {"version": "==7.4.0"}, "loose": {"version": ">=1"}}})
        pins, name = envsetup.read_lock(repo({"Pipfile.lock": pipfile}))
        self.assertEqual((pins, name), (["idna==3.4", "pytest==7.4.0"], "Pipfile.lock"))

    def test_no_lock_a_broken_lock_or_a_huge_one_gives_nothing(self):
        self.assertEqual(envsetup.read_lock(repo({"pyproject.toml": "[project]\nname='x'\n"})), ([], None))
        self.assertEqual(envsetup.read_lock(repo({"uv.lock": "this is [ not toml"})), ([], None))
        self.assertEqual(envsetup.read_lock(repo({"Pipfile.lock": "{"})), ([], None))
        big = repo({"uv.lock": "#" * (21 * 1024**2)})
        self.addCleanup(shutil.rmtree, big, True)
        self.assertEqual(envsetup.read_lock(big), ([], None))

    def test_at_most_max_pins_and_a_later_lock_file_is_used_when_the_first_is_unusable(self):
        many = "".join(f'[[package]]\nname = "p{i}"\nversion = "1.{i}"\nsource = {{ registry = "https://pypi.org/simple" }}\n' for i in range(envsetup.MAX_PINS + 50))
        self.assertEqual(len(envsetup.read_lock(repo({"uv.lock": many}))[0]), envsetup.MAX_PINS)
        d = repo({"uv.lock": "garbage [", "poetry.lock": '[[package]]\nname = "attrs"\nversion = "23.1.0"\n'})
        self.assertEqual(envsetup.read_lock(d), (["attrs==23.1.0"], "poetry.lock"))


class InstallPins(unittest.TestCase):
    def run_pins(self, pins, fake):
        calls = []

        def pip(venv, proj, home, args, timeout, max_venv, min_free):
            calls.append(args)
            return fake(args)
        with mock.patch.object(envsetup, "_pip", pip):
            return envsetup._install_pins(Path("/v"), Path("/p"), Path("/h"), pins, 10, 10**9, 0), calls

    def test_pins_go_in_batches_without_dependencies_and_from_wheels_only(self):
        pins = [f"p{i}==1" for i in range(95)]
        (done, skipped, guard), calls = self.run_pins(pins, lambda a: (0, ""))
        self.assertEqual((done, skipped, guard), (95, [], None)); self.assertEqual(len(calls), 3)
        for a in calls:
            self.assertEqual(a[:4], ["install", "-q", "--no-deps", "--only-binary=:all:"])

    def test_a_failing_batch_is_retried_one_by_one_and_only_the_bad_package_is_skipped(self):
        pins = ["a==1", "b==1", "c==1"]
        (done, skipped, guard), calls = self.run_pins(pins, lambda a: (1, "no wheel") if ("b==1" in a) else (0, ""))
        self.assertEqual((done, skipped, guard), (2, ["b"], None))

    def test_a_resource_guard_stops_everything_and_is_reported(self):
        (done, skipped, guard), calls = self.run_pins([f"p{i}==1" for i in range(90)], lambda a: (125, "environment too heavy"))
        self.assertEqual(guard, "environment too heavy"); self.assertEqual(len(calls), 1)


class BuildEnvWithLock(unittest.TestCase):
    PYPROJECT = "[project]\nname = 'thing'\nversion = '0.1'\ndependencies = []\n"

    def build(self, files, fake, **env):
        r = repo(files)
        calls = []

        def pip(venv, proj, home, args, timeout, max_venv, min_free):
            calls.append(list(args))
            return fake(args)
        t = Path(tempfile.mkdtemp())
        with mock.patch.object(envsetup, "_pip", pip), mock.patch.object(envsetup, "uninstall_project_dists"), mock.patch.dict(os.environ, {"AGENTVOW_LOCK": "1", **env}):
            out = envsetup.build_env(r, t / "venv", t / "home")
        return out, calls, t

    def test_with_a_lock_the_pins_come_first_and_every_install_step_is_constrained_by_them(self):
        (py, notes, aborted), calls, t = self.build({"pyproject.toml": self.PYPROJECT, "uv.lock": UV}, lambda a: (0, ""))
        self.assertIsNone(aborted)
        self.assertEqual(calls[0][:4], ["install", "-q", "--no-deps", "--only-binary=:all:"]); self.assertIn("requests==2.32.3", calls[0])
        project = [c for c in calls if c[-1] == "."][0]
        self.assertEqual(project[:3], ["install", "-q", "-c"]); self.assertTrue(project[3].endswith("constraints.txt"))
        pytest_step = [c for c in calls if c[-1] == "pytest"][0]
        self.assertNotIn("-c", pytest_step)
        self.assertTrue(any("installed 2 of 2 pinned package(s) from uv.lock" in n for n in notes))
        self.assertIn("requests==2.32.3", (t / "home" / "constraints.txt").read_text())

    def test_without_a_lock_the_ladder_is_exactly_what_it_was(self):
        _, calls, _ = self.build({"pyproject.toml": self.PYPROJECT}, lambda a: (0, ""))
        self.assertTrue(all("-c" not in c and "--no-deps" not in c for c in calls))
        _, calls, _ = self.build({"pyproject.toml": self.PYPROJECT, "uv.lock": UV}, lambda a: (0, ""), AGENTVOW_LOCK="0")
        self.assertTrue(all("-c" not in c and "--no-deps" not in c for c in calls))

    def test_it_is_off_unless_asked_for(self):   # the experiment did not justify a default
        r = repo({"pyproject.toml": self.PYPROJECT, "uv.lock": UV})
        calls = []
        t = Path(tempfile.mkdtemp())
        env = {k: v for k, v in os.environ.items() if k != "AGENTVOW_LOCK"}
        with mock.patch.object(envsetup, "_pip", lambda *a: (calls.append(list(a[3])) or (0, ""))), mock.patch.object(envsetup, "uninstall_project_dists"), mock.patch.dict(os.environ, env, clear=True):
            envsetup.build_env(r, t / "venv", t / "home")
        self.assertTrue(calls and all("-c" not in c and "--no-deps" not in c for c in calls))

    def test_a_step_that_conflicts_with_the_pins_is_installed_without_them(self):
        def fake(a):
            return (1, "conflict") if "-c" in a else (0, "")
        (py, notes, aborted), calls, _ = self.build({"pyproject.toml": self.PYPROJECT, "uv.lock": UV}, fake)
        self.assertTrue(any("conflicts with the pins; installed without them" in n for n in notes))
        self.assertTrue(any(c[-1] == "." and "-c" not in c for c in calls))

    def test_a_guard_while_installing_the_pins_starts_over_without_the_lock(self):
        state = {"n": 0}

        def fake(a):
            state["n"] += 1
            return (125, "environment too heavy") if "--no-deps" in a else (0, "")
        (py, notes, aborted), calls, t = self.build({"pyproject.toml": self.PYPROJECT, "uv.lock": UV}, fake)
        self.assertIsNone(aborted); self.assertIsNotNone(py)
        self.assertTrue(any("could not be installed within the limits" in n for n in notes))
        self.assertTrue(all("-c" not in c for c in calls)); self.assertFalse((t / "home" / "constraints.txt").exists())


if __name__ == "__main__":
    unittest.main()
