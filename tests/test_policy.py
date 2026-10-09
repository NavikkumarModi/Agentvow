import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "examples"))
os.environ.setdefault("AGENTVOW_HOME", tempfile.mkdtemp(prefix="am_home_"))
from agentvow import claims, decision, reality  # noqa: E402
from make_demo import build, git  # noqa: E402


def repo_with_failing_new_tests(t):
    repo = build(Path(t) / "r")
    head = git(repo, "rev-parse", "HEAD")
    ev = repo / ".agentvow" / "evidence"
    ev.mkdir(parents=True, exist_ok=True)
    (ev / "run.json").write_text(json.dumps(reality.sign_record({
        "commit": head, "tree": "", "result": "fail", "produced_by": "agentvow-runner", "summary": "x",
        "counts": {"passed": 60, "failed": 3, "skipped": 0, "errors": 0, "regressions": 0, "uncomparable": 3, "missing": 0}})))
    return repo


class NewTestFailuresPolicy(unittest.TestCase):
    def test_default_keeps_unresolved_failures_as_unknown(self):
        with tempfile.TemporaryDirectory() as t:
            repo = repo_with_failing_new_tests(t)
            d = decision.check(repo, "HEAD~1", "All tests pass.")
            f = next(x for x in d.findings if x.kind == claims.TESTS_PASS)
            self.assertEqual((f.verdict, f.attention, d.status), ("UNKNOWN", False, decision.INSUFFICIENT))
            self.assertEqual(f.meta.get("new_test_failures"), 3)

    def test_review_policy_raises_review_required_but_keeps_the_verdict_unknown(self):
        with tempfile.TemporaryDirectory() as t:
            repo = repo_with_failing_new_tests(t)
            d = decision.check(repo, "HEAD~1", "All tests pass.", new_test_failures="review")
            f = next(x for x in d.findings if x.kind == claims.TESTS_PASS)
            self.assertEqual((f.verdict, f.attention, d.status), ("UNKNOWN", True, decision.REVIEW))
            self.assertIn("added or changed by this change", f.why)

    def test_review_policy_does_not_affect_clean_runs(self):
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            head = git(repo, "rev-parse", "HEAD")
            (repo / ".agentvow" / "evidence").mkdir(parents=True, exist_ok=True)
            (repo / ".agentvow" / "evidence" / "run.json").write_text(json.dumps(reality.sign_record({
                "commit": head, "tree": "", "result": "pass", "produced_by": "agentvow-runner", "summary": "x",
                "counts": {"passed": 5, "failed": 0, "skipped": 0, "errors": 0, "regressions": 0, "uncomparable": 0, "missing": 0}})))
            d = decision.check(repo, "HEAD~1", "All 5 tests pass.", new_test_failures="review")
            self.assertFalse(any(f.attention for f in d.findings))


if __name__ == "__main__":
    unittest.main()


class NoBaseline(unittest.TestCase):
    def test_failures_are_not_new_test_failures_when_the_suite_did_not_run_at_base(self):
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            head = git(repo, "rev-parse", "HEAD")
            (repo / ".agentvow" / "evidence").mkdir(parents=True, exist_ok=True)
            (repo / ".agentvow" / "evidence" / "run.json").write_text(json.dumps(reality.sign_record({
                "commit": head, "tree": "", "result": "fail", "produced_by": "agentvow-runner", "summary": "x",
                "counts": {"passed": 0, "failed": 0, "skipped": 0, "errors": 6, "regressions": 0, "uncomparable": 6, "missing": 0, "no_baseline": 1}})))
            d = decision.check(repo, "HEAD~1", "All tests pass.", new_test_failures="review")
            self.assertFalse(any(f.attention for f in d.findings))
            self.assertNotEqual(d.status, decision.REVIEW)

    def test_runner_flags_no_baseline_when_base_had_no_passing_tests(self):
        from agentvow import runner
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            rec = runner.run_tests(repo, ["sh", "-c", "echo 'PASSED tests/a.py::t1'; echo '1 passed in 0.01s'"], write=False,
                                   baseline_failed=[], baseline_passed=[])
            self.assertEqual(rec["counts"].get("no_baseline"), 1)
