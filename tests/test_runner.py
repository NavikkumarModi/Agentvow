import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agentmirror_check import claims, decision, runner  # noqa: E402
from agentmirror_check.reality import Evidence, Snapshot  # noqa: E402

UNITTEST = ("test_a (m.C.test_a) ... ok\ntest_b (m.C.test_b) ... skipped 'x'\ntest_c (m.C.test_c) ... ok\n"
            "FAIL: test_d (m.C.test_d)\nERROR: test_e (m.C.test_e)\nRan 5 tests in 0.1s\nFAILED (failures=1, errors=1, skipped=1)")
PYTEST = "PASSED tests/a.py::t1\nFAILED tests/a.py::t2 - boom\nERROR tests/b.py::t3\n= 1 failed, 1 passed, 1 error in 0.1s ="


class Parsing(unittest.TestCase):
    def test_unittest(self):
        self.assertEqual(runner.parse_counts(UNITTEST), {"passed": 2, "failed": 1, "skipped": 1, "errors": 1})
        self.assertEqual(runner.failed_ids(UNITTEST), ["test_d (m.C.test_d)", "test_e (m.C.test_e)"])
        self.assertEqual(len(runner.passed_ids(UNITTEST)), 2)

    def test_pytest(self):
        self.assertEqual(runner.parse_counts(PYTEST), {"passed": 1, "failed": 1, "skipped": 0, "errors": 1})
        self.assertEqual(runner.failed_ids(PYTEST), ["tests/a.py::t2", "tests/b.py::t3"])

    def test_claim_counts(self):
        got = [claims.extract(t)[0].count for t in ("All 217 tests pass.", "148 tests passed, 4 skipped", "All tests pass.")]
        self.assertEqual(got, [217, 148, None])


def ev(counts, result="fail"):
    ind = {"framing": "separate", "evidence": "separate", "mechanism": "separate", "authority": "unknown"}
    return Evidence("e", "prior_verification", "runner", "abcdef123456", "h", "VALID", ind, "e.json", f"{result}: x", counts=counts)


class Differential(unittest.TestCase):
    snap = Snapshot("abcdef123456", False)
    claim = claims.Claim(claims.TESTS_PASS, "All 10 tests pass", 10)

    def verdict(self, counts, result="fail"):
        return decision._tests(self.claim, [ev(counts, result)], self.snap).verdict

    def test_regression_contradicts(self):
        self.assertEqual(self.verdict({"passed": 8, "failed": 2, "regressions": 1, "uncomparable": 0}), "CONTRADICTED")

    def test_environmental_failures_do_not_contradict_but_are_not_support(self):
        # review finding: failing tests mean "all tests pass" was not observed, even if they also fail at base
        self.assertEqual(self.verdict({"passed": 8, "failed": 2, "regressions": 0, "uncomparable": 0}), "UNKNOWN")

    def test_agent_count_equal_to_total_is_noted(self):
        f = decision._tests(claims.Claim(claims.TESTS_PASS, "All 10 tests pass", 10),
                            [ev({"passed": 8, "failed": 2, "regressions": 0, "uncomparable": 0})], self.snap)
        self.assertEqual(f.verdict, "UNKNOWN")
        self.assertIn("2 test(s) fail", f.why)

    def test_uncomparable_failures_are_unknown(self):
        self.assertEqual(self.verdict({"passed": 8, "failed": 2, "regressions": 0, "uncomparable": 2}), "UNKNOWN")

    def test_no_baseline_is_unknown(self):
        self.assertEqual(self.verdict({"passed": 8, "failed": 2}), "UNKNOWN")

    def test_count_match_supports_and_mismatch_is_unknown(self):
        self.assertEqual(self.verdict({"passed": 10, "failed": 0}, "pass"), "SUPPORTED_BY_PRIOR_EVIDENCE")
        self.assertEqual(self.verdict({"passed": 12, "failed": 0}, "pass"), "UNKNOWN")

    def test_inconclusive_run_is_unknown(self):
        self.assertEqual(self.verdict({"passed": 0, "failed": 0}, "inconclusive"), "UNKNOWN")


if __name__ == "__main__":
    unittest.main()


class RealPhrasing(unittest.TestCase):
    def test_count_before_noun_with_trailing_all_green(self):
        c = claims.extract("**Tests:** 535 backend tests (17 new/updated) + 5 frontend tests, all green; lint clean.")
        self.assertEqual([(x.kind, x.count) for x in c], [("tests_pass", 535)])

    def test_unrelated_verified_is_not_a_test_claim(self):
        self.assertEqual(claims.extract("I verified the endpoint works."), [])



class MissingSubdir(unittest.TestCase):
    def test_missing_directory_is_inconclusive_not_an_error(self):
        import tempfile
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "examples"))
        from make_demo import build
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            rec = runner.run_tests(repo, ["true"], subdir="no_such_dir", write=False)
            self.assertEqual(rec["result"], "inconclusive")
            self.assertEqual(rec["counts"], {})


class FailureMatching(unittest.TestCase):
    def test_docstring_tests_count_as_passed(self):
        out = "test_a (m.C.test_a)\nChecks that a works ... ok\ntest_b (m.C.test_b) ... ok\n"
        self.assertEqual(runner.passed_ids(out), ["test_a (m.C.test_a)", "test_b (m.C.test_b)"])

    def test_module_level_import_failure_is_a_regression_if_module_had_passes(self):
        base_passed = ["test_x (test_mod.C.test_x)", "test_y (other.D.test_y)"]
        failed = ["test_mod (unittest.loader._FailedTest.test_mod)"]
        self.assertEqual(runner.classify_failures(failed, base_passed, []), (1, 0))

    def test_module_level_failure_for_a_new_module_is_uncomparable(self):
        self.assertEqual(runner.classify_failures(["new_mod (unittest.loader._FailedTest.new_mod)"], ["t (m.C.t)"], []), (0, 1))

    def test_pytest_collection_error_regression(self):
        self.assertEqual(runner.classify_failures(["tests/test_a.py"], ["tests/test_a.py::t1"], []), (1, 0))

    def test_test_level_matching_unchanged(self):
        self.assertEqual(runner.classify_failures(["t1", "t2", "t3"], ["t1"], ["t2"]), (1, 1))


class SuiteBroken(unittest.TestCase):
    def test_suite_that_cannot_run_is_a_regression(self):
        import tempfile
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "examples"))
        from make_demo import build
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            rec = runner.run_tests(repo, ["sh", "-c", "echo boom; exit 2"], write=False,
                                   baseline_failed=[], baseline_passed=["tests/a.py::t1", "tests/a.py::t2"])
            self.assertEqual(rec["result"], "fail")
            self.assertEqual(rec["counts"]["regressions"], 2)


class CIEvidence(unittest.TestCase):
    snap = Snapshot("abcdef123456", False)

    def fetch(self, runs):
        return lambda path: {"check_runs": runs}

    def verdict(self, runs, claim="All tests pass."):
        from agentmirror_check import ci
        ev = ci.ci_evidence(Path("."), self.snap, fetch=self.fetch(runs), slug="o/r")
        return decision._tests(claims.extract(claim)[0], ev, self.snap)

    def test_failing_test_job_contradicts(self):
        f = self.verdict([{"name": "tests (3.13)", "status": "completed", "conclusion": "failure"}])
        self.assertEqual(f.verdict, "CONTRADICTED")

    def test_passing_test_job_supports(self):
        f = self.verdict([{"name": "pytest", "status": "completed", "conclusion": "success"}])
        self.assertEqual(f.verdict, "SUPPORTED_BY_PRIOR_EVIDENCE")

    def test_non_test_failures_are_ignored(self):
        f = self.verdict([{"name": "SonarCloud Code Analysis", "status": "completed", "conclusion": "failure"},
                          {"name": "validate_pr_title", "status": "completed", "conclusion": "failure"}])
        self.assertEqual(f.verdict, "UNKNOWN")  # no test job at all: not a pass

    def test_dirty_tree_has_no_ci_evidence(self):
        from agentmirror_check import ci
        self.assertEqual(ci.ci_evidence(Path("."), Snapshot("a", True), fetch=self.fetch([]), slug="o/r"), [])

    def test_count_mismatch_is_unknown_even_with_environmental_failures(self):
        ind = {"framing": "s", "evidence": "s", "mechanism": "separate", "authority": "?"}
        e = Evidence("e", "prior_verification", "c", "abcdef123456", "h", "VALID", ind, "e.json", "fail: x",
                     counts={"passed": 8, "failed": 2, "regressions": 0, "uncomparable": 0})
        f = decision._tests(claims.Claim(claims.TESTS_PASS, "All 999 tests pass", 999), [e], self.snap)
        self.assertEqual(f.verdict, "UNKNOWN")


class PytestSummary(unittest.TestCase):
    def test_collection_error_banner_is_not_double_counted(self):
        out = "ERROR tests/a.py\n!!!! Interrupted: 1 error during collection !!!!\n310 tests collected, 1 error in 3.41s\n"
        self.assertEqual(runner.parse_counts(out)["errors"], 1)


class RealWorldPhrasing(unittest.TestCase):
    def test_ratio_phrase_with_count(self):
        c = claims.extract("Full suite: 374/374 passing (was 372).")
        self.assertEqual([(x.kind, x.count) for x in c], [("tests_pass", 374)])

    def test_failure_report_is_not_a_pass_claim(self):
        self.assertEqual([x.kind for x in claims.extract("373 passed, 1 failed")], ["unchecked"])

    def test_zero_failed_is_still_a_pass_claim(self):
        self.assertEqual([x.kind for x in claims.extract("374 passed, 0 failed")], ["tests_pass"])


class JobClassifier(unittest.TestCase):
    def test_v2_recognises_real_world_test_job_names(self):
        from agentmirror_check.ci import TEST_JOB
        for n in ("tests (3.10)", "test_typings_docker", "test1 (langchain / autologging)", "pytester (ubuntu-22.04)", "Python 3.8",
                  "Python Tests (3.11, macos-latest)", "integration-app-harness (redis)", "Frontend Unit Tests"):
            self.assertTrue(TEST_JOB.search(n), n)

    def test_v2_rejects_non_test_jobs(self):
        from agentmirror_check.ci import TEST_JOB
        for n in ("Security Scan", "SonarCloud Code Analysis", "validate_pr_title", "Publish release build to test.pypi", "latest", "contest",
                  "Codacy Diff Coverage", "Type Checking", "labeling"):
            self.assertFalse(TEST_JOB.search(n), n)


class EnvironmentLimits(unittest.TestCase):
    def run_cmd(self, shell):
        import tempfile
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "examples"))
        from make_demo import build
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            return runner.run_tests(repo, ["sh", "-c", shell], write=False, baseline_failed=[], baseline_passed=["tests/a.py::t1"])

    def test_missing_third_party_module_is_an_environment_limit_not_a_regression(self):
        rec = self.run_cmd("echo \"ModuleNotFoundError: No module named 'requests'\"; exit 2")
        self.assertEqual(rec["result"], "inconclusive")
        self.assertIn("requests", rec["summary"])
        self.assertFalse(rec["counts"].get("regressions"))

    def test_missing_module_that_belongs_to_the_repo_is_still_a_regression(self):
        rec = self.run_cmd("echo \"ERROR tests/a.py\"; echo \"ModuleNotFoundError: No module named 'payments'\"; exit 2")
        self.assertNotIn("missing dependency", rec["summary"])  # 'payments' is the repo's own package
        self.assertTrue(rec["counts"].get("regressions"))

    def test_first_error_line_is_recorded_as_a_hint(self):
        rec = self.run_cmd("echo 'E   ImportError: cannot import name x'; exit 2")
        self.assertIn("ImportError", rec["hint"])


class QuietPytest(unittest.TestCase):
    def test_counts_fall_back_to_per_test_lines_without_a_summary(self):
        import tempfile
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "examples"))
        from make_demo import build
        out = "PASSED tests/a.py::t1\\nPASSED tests/a.py::t2\\nFAILED tests/a.py::t3 - AssertionError"
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            rec = runner.run_tests(repo, ["sh", "-c", f"printf '{out}\\\\n'; exit 1"], write=False,
                                   baseline_failed=[], baseline_passed=["tests/a.py::t1", "tests/a.py::t2", "tests/a.py::t3"])
            self.assertEqual((rec["counts"]["passed"], rec["counts"]["failed"]), (2, 1))
            self.assertEqual(rec["counts"]["regressions"], 1)   # t3 passed at base, fails now: a real regression, not 'suite cannot run'
            self.assertNotIn("cannot run", rec["summary"])
