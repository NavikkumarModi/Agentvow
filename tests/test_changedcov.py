import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
from agentvow import changedcov, cli


class Pure(unittest.TestCase):
    def test_added_lines_are_new_side_inserts_and_replacements(self):
        self.assertEqual(changedcov.added_lines("a\nb\nc\n", "a\nB\nc\nd\n"), {2, 4})
        self.assertEqual(changedcov.added_lines("", "x\ny\n"), {1, 2})
        self.assertEqual(changedcov.added_lines("a\nb\n", "a\n"), set())   # deletions alone cannot be measured

    def test_source_filter_skips_tests_docs_and_non_python(self):
        self.assertTrue(changedcov.is_source("pkg/mod.py"))
        for f in ("tests/test_a.py", "pkg/test_b.py", "pkg/conftest.py", "docs/x.py", "README.md", "web/app.js"):
            self.assertFalse(changedcov.is_source(f), f)

    def test_measure_counts_executable_changed_lines_and_names_the_ones_not_run(self):
        with tempfile.TemporaryDirectory() as d:
            cov = {"files": {str(Path(d) / "a.py"): {"executed_lines": [1, 2, 3], "missing_lines": [4, 5]}}}
            m = changedcov.measure({"a.py": {2, 3, 4, 9}, "b.py": {1}}, cov, Path(d))   # line 9 is not executable (comment); b.py was never loaded
            self.assertEqual((m["executed"], m["executable"], m["not_run"], m["not_loaded"]), (2, 3, {"a.py": [4]}, ["b.py"]))
            s = changedcov.sentence(m)
            self.assertIn("2 of 3 changed executable source lines were run", s)
            self.assertIn("a.py lines 4", s)
            self.assertIn("never loaded", s)

    def test_no_coverage_data_is_reported_as_unavailable_not_as_zero(self):
        self.assertFalse(changedcov.measure({"a.py": {1}}, None, Path("."))["available"])
        self.assertEqual(changedcov.sentence({"available": False}), "")

    def test_coverage_argv_only_wraps_python_dash_m_runners(self):
        self.assertEqual(changedcov.coverage_argv(["py", "-m", "pytest", "-q"], "rc", "df")[:8], ["py", "-m", "coverage", "run", "--rcfile", "rc", "--data-file", "df"])
        self.assertIsNone(changedcov.coverage_argv(["py", "script.py"], "rc", "df"))


def _online():
    try:
        import socket
        socket.create_connection(("pypi.org", 443), timeout=3).close(); return True
    except OSError:
        return False


@unittest.skipUnless(_online(), "needs network (installs coverage in a built environment)")
class EndToEnd(unittest.TestCase):
    def test_a_passing_run_reports_which_changed_lines_no_test_ran(self):
        import io
        with tempfile.TemporaryDirectory() as d:
            os.environ["AGENTVOW_HOME"] = str(Path(d) / "home")
            r = Path(d) / "r"; (r / "tests").mkdir(parents=True)
            g = lambda *x: subprocess.run(["git", "-C", str(r), *x], check=True, capture_output=True)
            g("init", "-q", "-b", "main"); g("config", "user.email", "a@b"); g("config", "user.name", "t")
            (r / "lib.py").write_text("def f():\n    return 1\n"); (r / "tests" / "__init__.py").write_text("")
            (r / "tests" / "test_a.py").write_text("import lib\n\ndef test_f():\n    assert lib.f() in (1, 2)\n")
            g("add", "."); g("commit", "-qm", "base")
            (r / "lib.py").write_text("def f():\n    return 2\n\ndef never_called():\n    return 3\n"); g("commit", "-qam", "change")
            p = Path(d) / "rec.json"; p.write_text(json.dumps({"setup": ["pip install pytest"], "test": "pytest -q tests"}))
            old = sys.stdin, sys.stdout, sys.stderr; sys.stdin = io.StringIO("All tests pass."); out = io.StringIO(); sys.stdout = out; sys.stderr = io.StringIO()
            try:
                cli.main(["check", "--repo", str(r), "--recipe", str(p), "--base", "HEAD~1", "--changed-coverage", "--json"])
            finally:
                sys.stdin, sys.stdout, sys.stderr = old
            f = [x for x in json.loads(out.getvalue())["findings"] if x["kind"] == "tests_pass"][0]
            cc = f["meta"].get("changed_line_coverage", {})
            self.assertTrue(cc.get("executable", 0) >= 2 and cc.get("not_run"), f)   # `return 3` inside never_called is not run
            self.assertIn("Changed-line coverage", f["why"])
            self.assertIn(f["verdict"], ("SUPPORTED_BY_PRIOR_EVIDENCE", "NOT_CONTRADICTED"))


if __name__ == "__main__":
    unittest.main()
