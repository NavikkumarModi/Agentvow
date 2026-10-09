import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "examples"))
from agentmirror import decision, report  # noqa: E402
from agentmirror.decision import Decision, Finding  # noqa: E402
from make_demo import build, git  # noqa: E402


def dec(status, findings):
    return Decision(status, "abcdef1234567890", False, ["a.py"], findings, "test scope", [])


class Report(unittest.TestCase):
    def page(self, status=decision.REVIEW, findings=None):
        findings = findings if findings is not None else [Finding("No downstream impact.", "no_downstream_impact", "CONTRADICTED", "why", ["e1"], ["u1"])]
        return report.render_html(dec(status, findings))

    def test_self_contained_no_scripts_or_external_resources(self):
        p = self.page()
        self.assertNotRegex(p, r"<script|https?://|src=|<link")

    def test_untrusted_text_is_escaped(self):
        p = self.page(findings=[Finding('<script>alert(1)</script> "x"', "unchecked", "UNKNOWN", "<img src=x onerror=1>", ["<b>e</b>"], [])])
        self.assertNotIn("<script>alert", p)
        self.assertNotIn("<img src=x", p)
        self.assertIn("&lt;script&gt;", p)

    def test_headline_for_each_status(self):
        self.assertIn("Review before approving", self.page(decision.REVIEW))
        self.assertIn("Not enough evidence to judge", self.page(decision.INSUFFICIENT, [Finding("c", "x", "UNKNOWN", "w")]))
        p = self.page(decision.NO_CONTRA, [Finding("c", "x", "NOT_CONTRADICTED", "w")])
        self.assertIn("not a safety verdict", p)

    def test_verdicts_have_text_labels_not_only_colour(self):
        for v, label in (("CONTRADICTED", "Contradicted"), ("SUPPORTED_BY_PRIOR_EVIDENCE", "Supported"),
                         ("NOT_CONTRADICTED", "Not contradicted"), ("UNKNOWN", "Unknown")):
            self.assertIn(label, self.page(findings=[Finding("c", "x", v, "w")]))

    def test_no_claims_says_nothing_was_verified(self):
        self.assertIn("nothing was verified", self.page(decision.INSUFFICIENT, []))

    def test_approval_box_never_lists_unknowns_as_verified(self):
        p = self.page(decision.INSUFFICIENT, [Finding("All tests pass.", "tests_pass", "UNKNOWN", "w")])
        self.assertRegex(p, r"It would NOT mean.*verified: All tests pass", )

    def test_json_has_schema_version(self):
        self.assertEqual(report.to_dict(dec(decision.REVIEW, []))["schema_version"], "1")

    def test_real_decision_renders_and_own_evidence_dir_is_hidden(self):
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            d = decision.check(repo, "HEAD~1", "No downstream impact. All 3 tests pass.")
            p = report.render_html(d)
            self.assertIn("payments/retry.py", p)
            self.assertNotIn("<code>.agentmirror/", p)


if __name__ == "__main__":
    unittest.main()
