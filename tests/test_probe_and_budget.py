import os, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agentvow import cli, envsetup, recipe, runner  # noqa: E402


@unittest.skipIf(runner.sandbox_problem(), "no working sandbox on this machine")
class Probes(unittest.TestCase):
    def test_a_planted_coverage_py_in_the_checkout_is_not_executed(self):
        d = Path(tempfile.mkdtemp()); marker = Path(tempfile.mkdtemp()) / "pwned"
        (d / "coverage.py").write_text(f"open({str(marker)!r}, 'w').write(__import__('os').environ.get('GH_TOKEN', 'x'))\n")
        old = os.getcwd(); os.chdir(d)
        try:
            with mock.patch.dict(os.environ, {"GH_TOKEN": "secret-token"}):
                with mock.patch.object(envsetup, "_pip", return_value=(0, "")):
                    cli._ensure_coverage(sys.executable, Path(tempfile.mkdtemp()))
                self.assertNotEqual(runner.probe(sys.executable, "import coverage").returncode, 0 if not marker.exists() else 99)
        finally:
            os.chdir(old)
        self.assertFalse(marker.exists())

    def test_a_pth_file_in_the_environment_cannot_write_outside_or_see_tokens(self):
        v = Path(tempfile.mkdtemp()) / "v"
        subprocess.run([sys.executable, "-m", "venv", str(v)], check=True, capture_output=True)
        site = next((v / "lib").glob("python*/site-packages"))
        marker = Path(tempfile.mkdtemp()) / "pth"
        (site / "evil.pth").write_text(f"import os; open({str(marker)!r}, 'w').write(os.environ.get('GH_TOKEN', 'none'))\n")
        with mock.patch.dict(os.environ, {"GH_TOKEN": "secret-token"}):
            runner.probe(v / "bin" / "python", "print(1)")
            self.assertEqual(envsetup.installed_from(v, Path(tempfile.mkdtemp())), [])
        self.assertFalse(marker.exists())

    def test_probe_environment_has_no_tokens(self):
        with mock.patch.dict(os.environ, {"GH_TOKEN": "secret-token", "GITHUB_TOKEN": "t2", "AWS_SECRET_ACCESS_KEY": "k"}):
            r = runner.probe(sys.executable, "import os; print(sorted(k for k in os.environ if 'TOKEN' in k or 'SECRET' in k or 'KEY' in k))")
        self.assertEqual(r.stdout.strip(), "[]")


class Budget(unittest.TestCase):
    def test_overall_install_budget_stops_a_long_setup(self):
        rec = recipe.parse({"schema": recipe.SCHEMA, "setup": ["pip install a", "pip install b", "pip install c"], "test": "pytest -q"})
        repo = Path(tempfile.mkdtemp()); (repo / "a.py").write_text("x = 1\n")
        subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
        calls = []

        def slow(venv, proj, home, args, timeout, max_venv, min_free):
            calls.append(args)
            return 0, ""
        clock = iter([0, 0, 1000, 1000, 1000, 1000, 1000])
        with mock.patch.object(envsetup, "_pip", slow), mock.patch.object(envsetup, "BUILD_BUDGET", 900), mock.patch.object(recipe.time, "time", lambda: next(clock, 1000)):
            py, notes, aborted = recipe.build_env(repo, rec, Path(tempfile.mkdtemp()) / "v", Path(tempfile.mkdtemp()) / "h")
        self.assertEqual(aborted, "timeout")
        self.assertTrue(any("overall budget" in n for n in notes))
        self.assertLess(len(calls), 3)


class Foreground(unittest.TestCase):
    def args(self, **kw):
        import argparse
        a = argparse.Namespace(evidence_pack=True, run_tests=True, changed_coverage=False, python=None, setup="auto")
        for k, v in kw.items():
            setattr(a, k, v)
        return a

    def test_pack_path_fails_closed_when_the_environment_cannot_be_built_and_does_not_raise(self):
        from agentvow import baseline
        seen = {}
        a = self.args()
        with mock.patch.object(baseline, "prepare", side_effect=OSError("disk")), mock.patch.object(cli, "_run", side_effect=lambda a_, *r: seen.update(run_tests=a_.run_tests, env=getattr(a_, "_env_aborted", None)) or "d"):
            out = cli._run_auto(a, Path(tempfile.mkdtemp()), "HEAD", "given", "text")
        self.assertEqual(out, "d")
        self.assertFalse(seen["run_tests"])
        self.assertIn("OSError", seen["env"])

    def test_native_environment_reaches_the_suites_only_on_the_pack_path(self):
        from agentvow import baseline
        rec = recipe.parse({"schema": recipe.SCHEMA, "setup": [], "test": "pytest -q", "env": {"FOO": "bar"}})
        a = self.args()
        with mock.patch.object(baseline, "prepare", return_value=("/x/python", rec, [], None)), mock.patch.object(cli, "_run", return_value="d"):
            cli._run_auto(a, Path(tempfile.mkdtemp()), "HEAD", "given", "text")
        self.assertIs(a._native, rec)
        self.assertEqual(a._native_info["env_names"], ["FOO=bar"])
        b = self.args(evidence_pack=False)
        with mock.patch.object(cli.envsetup, "build_env", return_value=("/x/python", [], None)), mock.patch.object(cli, "_run", return_value="d"):
            cli._run_auto(b, Path(tempfile.mkdtemp()), "HEAD", "given", "text")
        self.assertIsNone(getattr(b, "_native", None))


if __name__ == "__main__":
    unittest.main()
