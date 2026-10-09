import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "examples"))

from agentvow import claims, decision  # noqa: E402
from make_demo import build, git  # noqa: E402

CLAIM = "I raised the retry limit to 5. There is no downstream impact. All tests pass."


class Demo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = build(Path(self.tmp.name) / "r")

    def tearDown(self):
        self.tmp.cleanup()

    def run_check(self, text=CLAIM):
        return decision.check(self.repo, "HEAD~1", text)

    def test_no_impact_claim_is_contradicted_with_consumers(self):
        d = self.run_check()
        self.assertEqual(d.status, decision.REVIEW)
        f = next(x for x in d.findings if x.kind == claims.NO_IMPACT)
        self.assertEqual(f.verdict, "CONTRADICTED")
        self.assertIn("billing/invoice.py", f.why)
        self.assertIn("notifications/alerts.py", f.why)
        self.assertTrue(any("alerts.py has no test" in u for u in f.unknowns))

    def test_stale_evidence_is_unknown_not_support(self):
        d = self.run_check()
        f = next(x for x in d.findings if x.kind == claims.TESTS_PASS)
        self.assertEqual(f.verdict, "UNKNOWN")
        self.assertIn("different commit", f.why)

    def _ev(self, fresh, mech, detail="pass: x"):
        from agentvow.reality import Evidence
        ind = {"framing": "s", "evidence": "s", "mechanism": mech, "authority": "?"}
        return Evidence("e", "prior_verification", "c", "abcdef123456", "h", fresh, ind, "e.json", detail)

    def test_agent_authored_evidence_is_not_independent(self):
        from agentvow.reality import Snapshot
        c = claims.Claim(claims.TESTS_PASS, "tests pass")
        f = decision._tests(c, [self._ev("VALID", "same")], Snapshot("abcdef123456", False))
        self.assertEqual(f.verdict, "UNKNOWN")
        self.assertIn("agent itself", f.why)

    def test_independent_valid_passing_evidence_supports(self):
        from agentvow.reality import Snapshot
        c = claims.Claim(claims.TESTS_PASS, "tests pass")
        f = decision._tests(c, [self._ev("VALID", "separate")], Snapshot("abcdef123456", False))
        self.assertEqual(f.verdict, "SUPPORTED_BY_PRIOR_EVIDENCE")

    def test_independent_failing_or_unverifiable_evidence_does_not_support(self):
        from agentvow.reality import Snapshot
        c = claims.Claim(claims.TESTS_PASS, "tests pass")
        snap = Snapshot("abcdef123456", False)
        self.assertEqual(decision._tests(c, [self._ev("VALID", "separate", "fail: x")], snap).verdict, "UNKNOWN")
        self.assertEqual(decision._tests(c, [self._ev("UNVERIFIABLE", "separate")], snap).verdict, "UNKNOWN")

    def test_dirty_tree_blocks_clean_status(self):
        (self.repo / "payments/retry.py").write_text("MAX_RETRIES = 9\n")
        d = self.run_check("No downstream impact.")
        self.assertTrue(d.dirty)
        self.assertNotEqual(d.status, decision.NO_CONTRA)


class FailClosed(unittest.TestCase):
    def test_not_a_git_repo_is_insufficient_never_ok(self):
        with tempfile.TemporaryDirectory() as t:
            d = decision.check(Path(t), "HEAD~1", CLAIM)
            self.assertEqual(d.status, decision.INSUFFICIENT)
            self.assertTrue(all(f.verdict == "UNKNOWN" for f in d.findings))

    def test_no_claims_is_never_ok(self):
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            d = decision.check(repo, "HEAD~1", "Refactored a few things.")
            self.assertEqual(d.status, decision.INSUFFICIENT)

    def test_unchecked_claim_is_unknown(self):
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            d = decision.check(repo, "HEAD~1", "Safe to merge.")
            self.assertEqual(d.status, decision.INSUFFICIENT)

    def test_unsupported_language_prevents_clean_result(self):
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            # make the change touch a module nobody imports, add a JS file
            (repo / "solo.py").write_text("X = 1\n")
            (repo / "web.js").write_text("console.log(1)\n")
            git(repo, "add", "-A")
            git(repo, "commit", "-qm", "solo")
            d = decision.check(repo, "HEAD~1", "No downstream impact.")
            self.assertNotEqual(d.status, decision.NO_CONTRA)
            self.assertEqual(d.status, decision.INSUFFICIENT)

    def test_syntax_error_prevents_clean_result(self):
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            (repo / "solo.py").write_text("X = 1\n")
            (repo / "broken.py").write_text("def (:\n")
            git(repo, "add", "-A")
            git(repo, "commit", "-qm", "solo")
            d = decision.check(repo, "HEAD~1", "No downstream impact.")
            self.assertEqual(d.status, decision.INSUFFICIENT)

    def test_clean_case_is_scoped_not_safe(self):
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            (repo / "solo.py").write_text("X = 1\n")
            git(repo, "add", "-A")
            git(repo, "commit", "-qm", "solo")
            d = decision.check(repo, "HEAD~1", "No downstream impact.")
            self.assertEqual(d.status, decision.NO_CONTRA)
            self.assertNotIn("SAFE", d.status.replace("not a safety verdict", ""))


class CLI(unittest.TestCase):
    def test_cli_output_and_exit_code(self):
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            r = subprocess.run([sys.executable, "-m", "agentvow", "check", "--repo", str(repo)],
                               input=CLAIM, capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(r.returncode, 1, r.stderr)
            self.assertIn("REVIEW REQUIRED", r.stdout)
            self.assertIn("does not approve, reject or merge", r.stdout)


if __name__ == "__main__":
    unittest.main()


class Compat(unittest.TestCase):
    def run_with(self, new_src, claim="This is backward compatible."):
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            (repo / "payments/retry.py").write_text(new_src)
            git(repo, "add", "-A")
            git(repo, "commit", "-qm", "change")
            d = decision.check(repo, "HEAD~1", claim)
            return next(f for f in d.findings if f.kind == claims.BACKCOMPAT)

    def test_removed_function_contradicts(self):
        self.assertEqual(self.run_with("MAX_RETRIES = 3\n").verdict, "CONTRADICTED")

    def test_new_required_param_contradicts(self):
        f = self.run_with("MAX_RETRIES = 3\n\ndef should_retry(attempt, policy):\n    return True\n")
        self.assertEqual(f.verdict, "CONTRADICTED")
        self.assertIn("new required", " ".join(f.evidence))

    def test_added_optional_param_is_not_contradicted(self):
        f = self.run_with("MAX_RETRIES = 3\n\ndef should_retry(attempt, policy=None):\n    return True\n")
        self.assertEqual(f.verdict, "NOT_CONTRADICTED")

    def test_syntax_error_is_unknown(self):
        self.assertEqual(self.run_with("def (:\n").verdict, "UNKNOWN")


class CompatTests(unittest.TestCase):
    def test_test_file_changes_are_not_public_api(self):
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            (repo / "tests/test_retry.py").write_text("X = 1\n")
            git(repo, "add", "-A")
            git(repo, "commit", "-qm", "t")
            f = next(x for x in decision.check(repo, "HEAD~1", "Backward compatible.").findings if x.kind == claims.BACKCOMPAT)
            self.assertEqual(f.verdict, "UNKNOWN")


class Session(unittest.TestCase):
    def test_final_message_takes_last_assistant_text(self):
        from agentvow.cli import final_message
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / "s.jsonl"
            rows = [{"type": "assistant", "message": {"content": [{"type": "text", "text": "first"}]}},
                    {"type": "user", "message": {"content": "hi"}},
                    {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "x"}]}},
                    {"type": "assistant", "message": {"content": [{"type": "text", "text": "All 5 tests pass."}]}}]
            f.write_text("\n".join(json.dumps(r) for r in rows) + "\nnot json\n")
            self.assertEqual(final_message(f), "All 5 tests pass.")


class WorkingTree(unittest.TestCase):
    def test_evidence_bound_to_working_tree_hash(self):
        from agentvow import reality
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            (repo / "solo.py").write_text("X = 1\n")  # uncommitted, untracked
            snap = reality.snapshot(repo)
            self.assertTrue(snap.dirty and snap.tree)
            ev = repo / ".agentvow/evidence"
            (ev / "now.json").write_text(json.dumps({"commit": snap.commit, "tree": snap.tree, "result": "pass", "produced_by": "ci",
                                                     "counts": {"passed": 2}, "summary": "ok"}))
            fresh = {e.evidence_id: e.freshness for e in reality.load_prior_evidence(repo, snap)}
            self.assertEqual(fresh["now"], "VALID")
            (repo / "solo.py").write_text("X = 2\n")  # work changes after the evidence was recorded
            fresh = {e.evidence_id: e.freshness for e in reality.load_prior_evidence(repo, reality.snapshot(repo))}
            self.assertEqual(fresh["now"], "STALE")

    def test_untracked_files_count_as_changed(self):
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            (repo / "new_mod.py").write_text("Y = 1\n")
            self.assertIn("new_mod.py", __import__("agentvow.reality", fromlist=["x"]).changed_files(repo, "HEAD"))


class SingularForms(unittest.TestCase):
    def test_singular_and_suite_forms_are_claims(self):
        from agentvow import claims
        for text in ("The test passes.", "Tests pass. I changed foo.", "The test suite passes now.", "pytest passed after the change.", "The tests now pass."):
            self.assertTrue(any(c.kind == claims.TESTS_PASS for c in claims.extract(text)), text)

    def test_negations_and_unrelated_text_are_not_claims(self):
        from agentvow import claims
        for text in ("The test does not pass.", "I could not verify that the tests pass.", "The password passes through the proxy.", "This passes the buck."):
            self.assertFalse(any(c.kind == claims.TESTS_PASS for c in claims.extract(text)), text)
