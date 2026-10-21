"""Fault regression suite: known-false (and known-true) claims "All tests pass." on tiny repositories, run through the real `agentvow check --run-tests` in the real sandbox, with the verdict and exit
code pinned. It records what the tool says TODAY, including the cases where it is deliberately silent or unknown (E, F, G, H below): a change in any of these is a behaviour change that must be
decided, not discovered. Offline (unittest only). docs/FAULT_REGRESSION.md explains each scenario."""
import io, json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agentvow import cli, runner  # noqa: E402

LIB = "def add(a, b):\n    return a + b\n\ndef is_pos(x):\n    return x > 0\n"
TESTS = "import unittest\nfrom lib import add, is_pos\n\nclass T(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(1, 2), 3)\n    def test_pos(self):\n        self.assertTrue(is_pos(1))\n"
NEG_TEST = "import unittest\nfrom lib import neg\nclass N(unittest.TestCase):\n    def test_neg(self):\n        self.assertEqual(neg(1), -1)\n"
BASE = {"lib.py": LIB, "tests/__init__.py": "", "tests/test_lib.py": TESTS}
CMD = "{py} -m unittest discover -s tests -t . -v"


def build(files, change):
    r = Path(tempfile.mkdtemp(prefix="fr_"))
    g = lambda *x: subprocess.run(["git", "-C", str(r), *x], check=True, capture_output=True)
    g("init", "-q", "-b", "main"); g("config", "user.email", "a@b"); g("config", "user.name", "t")
    for n, t in files.items():
        (r / n).parent.mkdir(parents=True, exist_ok=True); (r / n).write_text(t)
    g("add", "."); g("commit", "-qm", "base")
    change(r)
    g("add", "."); g("commit", "-qm", "change")
    return r


def run(r, claim, *extra):
    os.environ["AGENTVOW_HOME"] = tempfile.mkdtemp(prefix="fh_")   # outside the repository, or the working tree would change under the evidence
    old = sys.stdin, sys.stdout, sys.stderr
    sys.stdin, out, sys.stderr = io.StringIO(claim), io.StringIO(), io.StringIO()
    sys.stdout = out
    try:
        code = cli.main(["check", "--repo", str(r), "--base", "HEAD~1", "--run-tests", "--python", sys.executable, "--test-cmd", CMD, "--json", *extra])
    finally:
        sys.stdin, sys.stdout, sys.stderr = old
    o = json.loads(out.getvalue())
    f = next(x for x in o["findings"] if x["kind"] == "tests_pass")
    return code, o["status"], f["verdict"], f["why"]


def add_neg(r, body="    return -x\n", with_test=True):
    (r / "lib.py").write_text((r / "lib.py").read_text() + "\ndef neg(x):\n" + body)
    if with_test:
        (r / "tests" / "test_neg.py").write_text(NEG_TEST)


@unittest.skipIf(runner.sandbox_problem(), "no working sandbox on this machine")
class FaultRegression(unittest.TestCase):
    def test_A_clean_change_is_supported_no_false_alarm(self):
        code, status, verdict, why = run(build(BASE, add_neg), "All 3 tests pass.")
        self.assertEqual((code, verdict), (0, "SUPPORTED_BY_PRIOR_EVIDENCE"))
        self.assertIn("matches the agent's count of 3", why)

    def test_B_a_break_in_code_an_existing_test_covers_is_contradicted(self):
        def change(r):
            (r / "lib.py").write_text(LIB.replace("a + b", "a - b"))
            add_neg(r)
        code, status, verdict, why = run(build(BASE, change), "All 3 tests pass.")
        self.assertEqual((code, status, verdict), (1, "REVIEW REQUIRED", "CONTRADICTED"))
        self.assertIn("passed before the change now fail", why)

    def test_C_a_syntax_error_that_stops_the_suite_is_contradicted(self):
        code, status, verdict, why = run(build(BASE, lambda r: (r / "lib.py").write_text(LIB + "\ndef broken(:\n")), "All 2 tests pass.")
        self.assertEqual((code, verdict), (1, "CONTRADICTED"))

    def test_D_a_fault_only_a_NEW_test_catches_is_unknown_by_default_and_review_when_asked(self):
        r = build(BASE, lambda r: add_neg(r, "    return x\n"))
        code, status, verdict, why = run(r, "All 3 tests pass.")
        self.assertEqual((code, status, verdict), (2, "INSUFFICIENT EVIDENCE", "UNKNOWN"))
        self.assertIn("did not exist before the change", why)
        code, status, verdict, why = run(r, "All 3 tests pass.", "--new-test-failures", "review")
        self.assertEqual((code, status), (1, "REVIEW REQUIRED"))   # a person is asked to look; the verdict itself stays UNKNOWN

    def test_E_a_fault_in_code_no_test_runs_is_NOT_flagged(self):
        """Known limit, pinned on purpose: passing tests say nothing about code they do not run (the evidence pack's changed-line coverage is what names it)."""
        code, status, verdict, why = run(build(BASE, lambda r: add_neg(r, "    return x\n", with_test=False)), "All 2 tests pass.")
        self.assertEqual((code, verdict), (0, "SUPPORTED_BY_PRIOR_EVIDENCE"))

    def test_F_an_inflated_test_count_is_unknown_not_contradicted(self):
        code, status, verdict, why = run(build(BASE, add_neg), "All 9 tests pass.")
        self.assertEqual((code, verdict), (2, "UNKNOWN"))
        self.assertIn("reported 9 passing tests", why)

    def test_G_a_test_that_fails_at_base_and_head_is_unknown_not_blamed_on_the_change(self):
        base = {**BASE, "tests/test_net.py": "import unittest\nclass N(unittest.TestCase):\n    def test_net(self):\n        raise OSError('network unreachable')\n"}
        code, status, verdict, why = run(build(base, add_neg), "All 4 tests pass.")
        self.assertEqual((code, verdict), (2, "UNKNOWN"))
        self.assertIn("also fail without the change", why)

    def test_H_when_everything_is_skipped_nothing_is_confirmed(self):
        def change(r):
            (r / "tests" / "test_lib.py").write_text("import unittest\n@unittest.skip('x')\nclass T(unittest.TestCase):\n    def test_a(self): pass\n")
        code, status, verdict, why = run(build(BASE, change), "All tests pass.")
        self.assertEqual((code, verdict), (2, "UNKNOWN"))
        self.assertIn("No test passed", why)


if __name__ == "__main__":
    unittest.main()
