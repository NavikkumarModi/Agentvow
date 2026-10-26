"""Hostile test harness: a change that makes a real test fail AND plants code in the test package (`tests/__init__.py`, which runs at discovery) to hide or fake the result. These pin what the tool says
today, including the case it cannot catch: a harness that is fully deceptive is believed (NOT_CONTRADICTED), with the finding naming that an existing test file was modified. Real `agentvow check
--run-tests` in the real sandbox; skipped where no sandbox works. docs/TRUST_MODEL.md, docs/FAULT_REGRESSION.md."""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agentvow import runner  # noqa: E402
from test_faults import BASE, LIB, build, run  # noqa: E402

FAULT = LIB.replace("return x > 0", "return x < 0")   # test_pos now fails for real


def hostile(code, where="tests/__init__.py", mode="replace"):
    """Plant `code` at `where` (replace a file, or `new` to add one, or `prepend` to put it at the top of an existing file) together with the real fault in lib.py."""
    def change(r):
        (r / "lib.py").write_text(FAULT)
        t = r / where; t.parent.mkdir(parents=True, exist_ok=True)
        t.write_text(code + (t.read_text() if mode == "prepend" and t.exists() else ""))
    return change


FAKE_OK = "\\nRan 2 tests in 0.001s\\n\\nOK"
CASES = {
    "fake_summary": "import atexit\natexit.register(lambda: print('" + FAKE_OK + "'))\n",
    "fake_summary_and_forced_exit_zero": "import atexit, os, sys\ndef _f():\n    sys.stdout.flush(); print('" + FAKE_OK + "'); sys.stdout.flush(); os._exit(0)\natexit.register(_f)\n",
    "silent_forced_exit_zero": "import atexit, os, sys\natexit.register(lambda: os._exit(0))\nsys.stdout = sys.stderr = open(os.devnull, 'w')\n",
    "fully_deceptive": ("import atexit, os, sys\n_err = sys.__stderr__\nsys.stderr = open(os.devnull, 'w'); sys.stdout = sys.stderr\n"
                        "def _f():\n    _err.write('test_add (tests.test_lib.T.test_add) ... ok\\ntest_pos (tests.test_lib.T.test_pos) ... ok\\n\\n" + "-" * 70 + "\\nRan 2 tests in 0.001s\\n\\nOK\\n'); _err.flush(); os._exit(0)\natexit.register(_f)\n"),
}


@unittest.skipIf(runner.sandbox_problem(), "no working sandbox on this machine")
class HostileHarness(unittest.TestCase):
    def verdict(self, name):
        return run(build(BASE, hostile(CASES[name])), "All tests pass.")

    def test_a_fake_summary_does_not_hide_a_real_failure(self):
        for name in ("fake_summary", "fake_summary_and_forced_exit_zero"):
            code, status, verdict, why = self.verdict(name)
            self.assertEqual((verdict, code), ("CONTRADICTED", 1), name)   # the failing test's own line is still in the output

    def test_a_harness_that_says_nothing_never_confirms_a_claim(self):
        code, status, verdict, why = self.verdict("silent_forced_exit_zero")
        self.assertEqual(verdict, "UNKNOWN"); self.assertNotEqual(code, 0)

    def test_a_harness_in_a_file_that_runs_when_tests_start_is_flagged_even_when_the_file_is_new(self):
        code, status, verdict, why = run(build(BASE, hostile(CASES["fully_deceptive"], "sitecustomize.py", "new")), "All tests pass.")
        self.assertEqual(verdict, "NOT_CONTRADICTED"); self.assertIn("run automatically when tests start", why); self.assertIn("sitecustomize.py", why)
        # (a conftest.py is only loaded by pytest, so under the unittest command used here a planted one does nothing and the real failure shows: CONTRADICTED. The tool still flags conftest.py by name.)

    def test_KNOWN_LIMIT_the_same_harness_hidden_in_ordinary_source_or_an_extra_test_file_is_believed_and_not_flagged(self):
        """The planted code has to run when tests are collected; it does not have to live in a file the tool treats as special. Both variants below give SUPPORTED_BY_PRIOR_EVIDENCE with nothing in the
        finding. This pins the limit (docs/TRUST_MODEL.md says so); a verdict change here is an improvement: update the test and the document."""
        for where, mode in (("lib.py", "prepend"), ("tests/test_zz_plant.py", "new")):
            code, status, verdict, why = run(build(BASE, hostile(CASES["fully_deceptive"], where, mode)), "All tests pass.")
            self.assertEqual(verdict, "SUPPORTED_BY_PRIOR_EVIDENCE", where); self.assertNotIn("run automatically", why); self.assertEqual(code, 0)

    def test_a_fully_deceptive_harness_is_believed_but_the_finding_names_the_modified_test_file(self):
        """KNOWN LIMIT: replay is independent of the agent's claim, not of the repository's own test code. If the harness also fakes the per-test lines and forces exit 0, the result is NOT_CONTRADICTED.
        What the tool still says: an existing test file was modified, and a green run does not show the tests still test what they did before. If this test ever fails because the verdict became
        CONTRADICTED or UNKNOWN, that is an improvement: update this test and docs/TRUST_MODEL.md."""
        code, status, verdict, why = self.verdict("fully_deceptive")
        self.assertEqual(verdict, "NOT_CONTRADICTED")
        self.assertIn("modified existing test file", why); self.assertIn("tests/__init__.py", why)


if __name__ == "__main__":
    unittest.main()
