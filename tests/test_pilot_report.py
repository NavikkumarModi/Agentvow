import io, json, sys, tempfile, unittest
from contextlib import redirect_stdout
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
from agentvow import cli, pilot_report, policy  # noqa: E402
import make_example_pilot_report as ex  # noqa: E402


def rcpt(i, verdict="SUPPORTED_BY_PRIOR_EVIDENCE", repro="both", cov=(4, 4), created="2026-11-03T10:00:00+00:00", pr=None, commit=None):
    return {"schema": policy.RECEIPT, "created_at": created, "repo": "o/n", "commit": commit or f"{i:040x}", "git_tree": "b" * 40, "pr": pr, "claims": [{"kind": "tests_pass", "verdict": verdict, "capture_authenticated": True}],
            "reproducibility": repro, "coverage": {"executed": cov[0], "executable": cov[1]} if cov else None, "not_reproduced": ["environment variables"]}


class Report(unittest.TestCase):
    def test_counts_decisions_and_latest_receipt_per_commit(self):
        rs = [rcpt(1), rcpt(2, "UNKNOWN"), rcpt(3, "CONTRADICTED"), rcpt(4, created="2026-11-01T00:00:00+00:00", commit="f" * 40, verdict="UNKNOWN"),
              rcpt(5, created="2026-11-09T00:00:00+00:00", commit="f" * 40)]   # same commit as 4, later and now supported: only the later one counts
        s = pilot_report.summarize(rs)
        self.assertEqual(s["receipts"], 4)
        self.assertEqual(s["decisions"], {"allow": 2, "needs_acknowledgement": 1, "block": 1})
        self.assertEqual(s["verdicts"]["UNKNOWN"], 1)

    def test_acknowledgements_are_counted_and_policy_changes_the_picture(self):
        r = rcpt(1, "UNKNOWN")
        ack = {"schema": policy.ACK, "receipt_sha": policy.sha(r), "by": "alice", "at": "t", "note": ""}
        pol = {"schema": policy.POLICY, "acknowledgers": ["alice"]}
        s = pilot_report.summarize([r], pol, [ack])
        self.assertEqual((s["decisions"], s["acknowledged"]), ({"allow": 1}, 1))
        self.assertEqual(pilot_report.summarize([r], {"schema": policy.POLICY, "unknown": "block"})["decisions"], {"block": 1})

    def test_recommendations_are_rule_based(self):
        many_single = pilot_report.recommendations(pilot_report.summarize([rcpt(i, repro="single") for i in range(4)]))
        self.assertTrue(any("only one replay context" in x for x in many_single))
        self.assertTrue(any("No policy file" in x for x in many_single))
        clean = pilot_report.summarize([rcpt(i) for i in range(4)], {"schema": policy.POLICY})
        self.assertEqual(pilot_report.recommendations(clean), ["Nothing in the counts calls for action. Keep the gate on and review the pull requests listed below."])
        self.assertTrue(any("No receipts" in x for x in pilot_report.recommendations(pilot_report.summarize([]))))
        low = pilot_report.recommendations(pilot_report.summarize([rcpt(i, cov=(1, 4)) for i in range(4)], {"schema": policy.POLICY}))
        self.assertTrue(any("fewer than half" in x for x in low))

    def test_report_states_its_limits_and_makes_no_outcome_claims(self):
        md = pilot_report.render_markdown(pilot_report.summarize([rcpt(i) for i in range(3)]))
        self.assertIn("does not show: that any change is correct, that any defect was prevented, or that review time was saved", md)
        for banned in ("bugs caught", "defects prevented:", "time saved:", "ROI"):
            self.assertNotIn(banned, md)
        self.assertIn("Receipts counted (latest per commit): **3**", md)

    def test_empty_and_invalid_inputs(self):
        d = Path(tempfile.mkdtemp())
        (d / "a.json").write_text("not json"); (d / "b.json").write_text(json.dumps({"schema": "other"})); (d / "c.json").write_text(json.dumps(rcpt(1)))
        rs, bad = pilot_report.load(d)
        self.assertEqual((len(rs), bad), (1, 2))
        e = Path(tempfile.mkdtemp())
        self.assertIn("No receipts were found", pilot_report.render_markdown(pilot_report.summarize(pilot_report.load(e)[0])))

    def test_cli_writes_the_report_and_labels_examples(self):
        d = Path(tempfile.mkdtemp())
        for i in range(3):
            (d / f"{i}.json").write_text(json.dumps(rcpt(i, pr=10 + i)))
        out = io.StringIO()
        with redirect_stdout(out):
            code = cli.main(["pilot-report", "--receipts", str(d), "--example"])
        self.assertEqual(code, 0)
        self.assertIn("Illustrative example built from synthetic receipts", out.getvalue())
        self.assertIn("covering 3 pull request(s)", out.getvalue())
        self.assertEqual(cli.main(["pilot-report", "--receipts", str(d / "missing")]), 0)   # an empty directory is a report, not an error

    def test_the_committed_example_matches_the_generator_and_is_labelled_synthetic(self):
        committed = (ROOT / "docs" / "pilot" / "EXAMPLE_REPORT.md").read_text()
        self.assertIn("Illustrative example built from synthetic receipts. Not data from any team.", committed)
        d = Path(tempfile.mkdtemp())
        for i, r in enumerate(ex.synthetic()):
            (d / f"r{i:03d}.json").write_text(json.dumps(r))
        s = pilot_report.summarize(pilot_report.load(d)[0], {"schema": policy.POLICY, "acknowledgers": ["alice"], "min_changed_line_coverage": 0.5})
        self.assertEqual(pilot_report.render_markdown(s, "Agent pull request evidence report: example-org/example-service", example=True), committed)


if __name__ == "__main__":
    unittest.main()
