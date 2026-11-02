import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from agentvow import cli, policy, queue  # noqa: E402
from test_pilot_report import rcpt  # noqa: E402


class Queue(unittest.TestCase):
    def test_stop_first_then_needs_a_person_then_acknowledged_then_no_flag(self):
        rs = [rcpt(1), rcpt(2, "UNKNOWN"), rcpt(3, "CONTRADICTED"), rcpt(4, "UNKNOWN")]
        ack = {"schema": policy.ACK, "receipt_sha": policy.sha(rs[3]), "by": "alice", "at": "t", "note": ""}
        items = queue.build(rs, {"schema": policy.POLICY, "acknowledgers": ["alice"]}, [ack])
        self.assertEqual([i["state"] for i in items], ["block", "needs_acknowledgement", "acknowledged", "allow"])
        self.assertTrue(items[0]["contradicted"] == 1 and items[1]["unknown"] == 1)

    def test_the_latest_receipt_per_commit_counts(self):
        rs = [rcpt(4, created="2026-11-01T00:00:00+00:00", commit="f" * 40, verdict="UNKNOWN"), rcpt(5, created="2026-11-09T00:00:00+00:00", commit="f" * 40)]
        self.assertEqual([i["state"] for i in queue.build(rs)], ["allow"])

    def test_output_never_calls_a_change_safe_and_says_what_no_flag_means(self):
        text = queue.render_text(queue.build([rcpt(1)])) + queue.render_markdown(queue.build([rcpt(1)]))
        self.assertIn("is not a statement that the change is correct or safe", text)
        self.assertNotIn("safe to merge", text.lower())

    def test_cli_exit_code_is_1_when_a_person_is_needed_and_0_otherwise(self):
        for rs, code in (([rcpt(1)], 0), ([rcpt(1), rcpt(2, "UNKNOWN")], 1)):
            d = Path(tempfile.mkdtemp())
            for i, r in enumerate(rs):
                (d / f"{i}.json").write_text(json.dumps(r))
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = cli.main(["queue", "--receipts", str(d)])
            self.assertEqual(rc, code)
            self.assertIn("receipt(s)", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
