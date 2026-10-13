import io, json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
from agentvow import cli, pack


def ctx(name, result, summary="", basis="native"):
    return {"name": name, "basis": basis, "available": True, "result": result, "counts": {"passed": 1, "failed": 0} if result == "pass" else {}, "summary": summary}


class Explain(unittest.TestCase):
    def test_every_combination_has_a_distinct_plain_reading(self):
        cap, nat = ctx("captured environment", "pass", basis="capsule"), ctx("project-native setup", "pass")
        self.assertEqual(pack.explain(cap, nat)[0], "both")
        self.assertEqual(pack.explain(cap, ctx("project-native setup", "inconclusive", "missing dependency: six"))[0], "captured_only")
        self.assertIn("NOT from the project's own setup", pack.explain(cap, ctx("project-native setup", "inconclusive", "missing dependency: six"))[1])
        self.assertIn("missing dependency: six", pack.explain(cap, ctx("project-native setup", "inconclusive", "missing dependency: six"))[1])
        self.assertEqual(pack.explain(ctx("captured environment", "fail", "1 failed", "capsule"), nat)[0], "native_only")
        self.assertEqual(pack.explain(ctx("captured environment", "fail", "", "capsule"), ctx("project-native setup", "fail"))[0], "neither")
        self.assertEqual(pack.explain(None, nat)[0], "single")
        self.assertIn("agentvow capture", pack.explain(None, nat)[1])
        self.assertEqual(pack.explain(None, None)[0], "none")


class Render(unittest.TestCase):
    def sample(self):
        return {"version": 1, "receipt": {"commit": "a" * 40, "dirty": True, "base": "HEAD~1", "command": "python -m pytest -q", "replay_python": "3.13.5", "created": "x", "valid_for": "this exact commit"},
                "contexts": [ctx("captured environment", "pass", basis="capsule"), ctx("project-native setup", "inconclusive", "missing dependency: six\x1b[31m")],
                "reproducibility": {"code": "captured_only", "text": "Reproduces from the captured packages but NOT from the project's own setup"},
                "coverage": {"available": True, "executed": 2, "executable": 3, "not_run": [{"file": "lib.py", "lines": "5", "snippets": ["5: return 3"]}], "not_loaded": ["other.py"]}, "limits": pack.LIMITS}

    def test_text_markdown_and_html_carry_the_three_dimensions_and_strip_control_characters(self):
        p = self.sample()
        txt = "\n".join(pack.render_text(p))
        self.assertIn("1. Execution receipt", txt); self.assertIn("2. Reproducibility", txt); self.assertIn("3. Changed-line coverage: 2 of 3", txt)
        self.assertIn("never loaded by the tests: other.py", txt)
        md = "\n".join(pack.render_markdown(p, lambda x, n=200: str(x)[:n]))
        self.assertIn("### Evidence pack", md); self.assertIn("2 of 3 changed executable", md)
        import html
        h = pack.render_html(p, lambda x: html.escape(str(x)))
        self.assertIn("Evidence pack", h); self.assertIn("never loaded by the tests", h)
        self.assertNotIn("\x1b", pack._t("a\x1b[31mb"))

    def test_unavailable_coverage_is_said_not_hidden(self):
        p = self.sample(); p["coverage"] = {"available": False, "reason": "coverage is not installed in the test environment"}
        self.assertIn("not available (coverage is not installed", "\n".join(pack.render_text(p)))


def _online():
    try:
        import socket
        socket.create_connection(("pypi.org", 443), timeout=3).close(); return True
    except OSError:
        return False


@unittest.skipUnless(_online(), "needs network (virtualenv with pytest and an undeclared dependency)")
class Disagreement(unittest.TestCase):
    def test_a_result_that_reproduces_from_the_capture_but_not_from_the_project_setup_is_called_out(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["AGENTVOW_HOME"] = str(Path(d) / "home")
            r = Path(d) / "r"; (r / "tests").mkdir(parents=True)
            g = lambda *x: subprocess.run(["git", "-C", str(r), *x], check=True, capture_output=True)
            g("init", "-q", "-b", "main"); g("config", "user.email", "a@b"); g("config", "user.name", "t")
            (r / ".gitignore").write_text(".venv/\n.agentvow/\n")
            (r / "lib.py").write_text("import six\n\ndef f():\n    return six.PY3\n"); (r / "tests" / "__init__.py").write_text("")   # `six` is used but not declared anywhere
            (r / "tests" / "test_a.py").write_text("import lib\n\ndef test_f():\n    assert lib.f() in (True, False)\n")
            g("add", "."); g("commit", "-qm", "base")
            (r / "lib.py").write_text("import six\n\ndef f():\n    return bool(six.PY3)\n"); g("commit", "-qam", "change")
            subprocess.run([sys.executable, "-m", "venv", str(r / ".venv")], check=True, capture_output=True)
            subprocess.run([str(r / ".venv" / "bin" / "pip"), "install", "-q", "pytest", "six"], check=True, capture_output=True)
            from agentvow import capsule
            self.assertIsNotNone(capsule.capture(r)[0])
            old = sys.stdin, sys.stdout, sys.stderr; sys.stdin = io.StringIO("All tests pass."); out = io.StringIO(); sys.stdout = out; sys.stderr = io.StringIO()
            try:
                cli.main(["check", "--repo", str(r), "--base", "HEAD~1", "--evidence-pack", "--json"])
            finally:
                sys.stdin, sys.stdout, sys.stderr = old
            o = json.loads(out.getvalue())
            p = o["pack"]
            self.assertEqual(p["reproducibility"]["code"], "captured_only", p)
            names = {c["name"]: c["result"] for c in p["contexts"]}
            self.assertEqual(names["captured environment"], "pass")
            self.assertNotEqual(names["project-native setup"], "pass")
            self.assertTrue(p["coverage"]["available"])


if __name__ == "__main__":
    unittest.main()
