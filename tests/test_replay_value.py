"""The pure helpers of scripts/replay_value_run.py (rules: docs/research/REPLAY_VALUE_PREREG.md and its Amendment 1). No network, no sandbox."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
import replay_value_run as rv  # noqa: E402


class Eligibility(unittest.TestCase):
    def test_a_plain_pip_repository_is_eligible(self):
        self.assertEqual(rv.eligibility(["requirements.txt", "app.py"], "", 10), (True, ""))
        self.assertEqual(rv.eligibility(["pyproject.toml"], "[project]\nname='x'\n", 10), (True, ""))
        self.assertEqual(rv.eligibility(["setup.py"], "", 10), (True, ""))

    def test_markers_size_and_missing_install_files_exclude(self):
        self.assertEqual(rv.eligibility(["poetry.lock", "requirements.txt"], "", 10), (False, "marker:poetry.lock"))
        self.assertEqual(rv.eligibility(["Pipfile", "setup.py"], "", 10), (False, "marker:pipfile"))
        self.assertEqual(rv.eligibility(["pyproject.toml"], "[tool.poetry]\n", 10), (False, "marker:[tool.poetry"))
        self.assertEqual(rv.eligibility(["pyproject.toml"], "[dependency-groups]\ndev=[]\n", 10), (False, "marker:dependency-groups"))
        self.assertEqual(rv.eligibility(["requirements.txt"], "", 300), (False, "size"))
        self.assertEqual(rv.eligibility(["requirements.txt"], "", None), (False, "size"))
        self.assertEqual(rv.eligibility(["README.md"], "", 10), (False, "no_install_files"))


class Wilson(unittest.TestCase):
    def test_interval(self):
        self.assertIsNone(rv.wilson(0, 0))
        lo, hi = rv.wilson(5, 10)
        self.assertTrue(0.23 < lo < 0.24 and 0.76 < hi < 0.77)
        self.assertEqual(rv.wilson(0, 10)[0], 0.0)


class Imports(unittest.TestCase):
    def test_absolute_relative_and_src_imports(self):
        self.assertTrue(rv.imports_changed("from pkg import mod\n", "tests/test_a.py", {"pkg/mod.py"}))
        self.assertTrue(rv.imports_changed("import pkg.mod\n", "tests/test_a.py", {"src/pkg/mod.py"}))
        self.assertTrue(rv.imports_changed("from .helpers import x\n", "tests/test_a.py", {"tests/helpers.py"}))
        self.assertTrue(rv.imports_changed("from pkg import sub\n", "t/test_a.py", {"pkg/sub/__init__.py"}))
        self.assertFalse(rv.imports_changed("import other\n", "tests/test_a.py", {"pkg/mod.py"}))
        self.assertFalse(rv.imports_changed("def (:\n", "tests/test_a.py", {"pkg/mod.py"}))


class Adjudication(unittest.TestCase):
    CH = {"pkg/mod.py"}

    def test_confirmed_needs_a_stable_regression_in_a_test_that_touches_a_changed_file(self):
        t = "tests/test_a.py::test_x"
        src = {"tests/test_a.py": "import pkg.mod\n"}
        self.assertEqual(rv.adjudicate([[t], [t], [t]], src, self.CH), {"class": "confirmed", "test": t})
        self.assertEqual(rv.adjudicate([[t], [t], [t]], {}, {"tests/test_a.py"}), {"class": "confirmed", "test": t})

    def test_unstable_or_unrelated_is_not_confirmed(self):
        t = "tests/test_a.py::test_x"
        self.assertEqual(rv.adjudicate([[t], [], [t]], {"tests/test_a.py": "import pkg.mod\n"}, self.CH)["class"], "not_confirmed")
        r = rv.adjudicate([[t], [t], [t]], {"tests/test_a.py": "import other\n"}, self.CH)
        self.assertEqual(r["class"], "not_confirmed"); self.assertIn("import no changed file", r["why"])

    def test_no_regression_in_any_run_cannot_be_decided(self):
        self.assertEqual(rv.adjudicate([[], [], []], {}, self.CH)["class"], "cannot_decide")
        self.assertEqual(rv.adjudicate([["noid"], ["noid"], ["noid"]], {}, self.CH)["class"], "cannot_decide")


def row(repo, pr, verdict, stage="done", faults=None, adj=None):
    r = {"repo": repo, "pr": pr, "stage": stage, "verdict": verdict}
    if faults is not None:
        r["faults"] = faults
    if adj:
        r["adjudication"] = {"class": adj}
    return r


def fault(detected, oracle=True):
    return {"detected": detected, "oracle_break": oracle}


class Summary(unittest.TestCase):
    def test_the_frozen_rule_needs_all_three_thresholds(self):
        rows = [row("a/b", i, "SUPPORTED", faults=[fault(True), fault(True), fault(False)]) for i in range(4)] + \
               [row("c/d", i, "CONTRADICTED", adj="confirmed") for i in range(4)] + [row("e/f", i, "UNKNOWN") for i in range(2)]
        s = rv.summarize(rows)
        self.assertEqual(s["q1_yield"]["k"], 8); self.assertEqual(s["q1_yield"]["n"], 10)
        self.assertEqual(s["q2_detection"]["rate"], round(8 / 12, 3))
        self.assertTrue(s["q3_determined"]); self.assertEqual(s["q3_confirmed"]["rate"], 1.0)
        self.assertTrue(s["rule"]["keep_as_headline"])

    def test_low_yield_or_detection_fails_the_rule_and_harness_failures_are_not_counted(self):
        rows = [row("a/b", 1, "SUPPORTED", faults=[fault(False)]), row("a/b", 2, "UNKNOWN"), row("a/b", 3, "UNKNOWN"), row("c/d", 1, None, stage="harness_low_disk")]
        s = rv.summarize(rows)
        self.assertEqual((s["harness_failures"], s["evaluated"]), (1, 3))
        self.assertFalse(s["rule"]["yield_ok"]); self.assertFalse(s["rule"]["detection_ok"]); self.assertFalse(s["rule"]["keep_as_headline"])

    def test_the_shipped_supported_name_counts_as_supported(self):
        rows = [row("a/b", i, "SUPPORTED_BY_PRIOR_EVIDENCE", faults=[fault(True)]) for i in range(3)] + [row("c/d", 1, "UNKNOWN")]
        s = rv.summarize(rows)
        self.assertEqual((s["q1_yield"]["k"], s["q2_detection"]["n"]), (3, 3))

    def test_precision_is_undetermined_below_four_decided_results(self):
        rows = [row("a/b", i, "SUPPORTED", faults=[fault(True)]) for i in range(5)] + [row("c/d", 1, "CONTRADICTED", adj="confirmed")]
        s = rv.summarize(rows)
        self.assertFalse(s["q3_determined"]); self.assertFalse(s["rule"]["confirmed_ok"]); self.assertFalse(s["rule"]["keep_as_headline"])


if __name__ == "__main__":
    unittest.main()
