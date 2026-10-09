import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "examples"))
from agentvow import adapters, ci, report, decision  # noqa: E402
from agentvow.reality import Snapshot  # noqa: E402
from make_demo import build  # noqa: E402

CLAUDE = json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "All 5 tests pass."}]}})
CODEX_LIKE = json.dumps({"type": "response_item", "payload": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Ran the suite: 12 passed."}]}})
GENERIC = json.dumps({"role": "assistant", "content": "No downstream impact."})


class Formats(unittest.TestCase):
    def last(self, *lines):
        return adapters.final_message_from_text("\n".join(lines))

    def test_claude_shape(self):
        self.assertEqual(self.last(CLAUDE), "All 5 tests pass.")

    def test_codex_like_shape(self):
        self.assertEqual(self.last(CODEX_LIKE), "Ran the suite: 12 passed.")

    def test_generic_role_content_string(self):
        self.assertEqual(self.last(GENERIC), "No downstream impact.")

    def test_last_assistant_wins_and_user_text_is_ignored(self):
        user = json.dumps({"role": "user", "content": "please fix it"})
        self.assertEqual(self.last(GENERIC, user, CLAUDE), "All 5 tests pass.")

    def test_tool_calls_and_thinking_are_not_messages(self):
        tool = json.dumps({"role": "assistant", "content": [{"type": "tool_use", "text": "rm -rf"}, {"type": "thinking", "text": "hmm"}]})
        self.assertIsNone(self.last(tool))

    def test_plain_text_transcript_is_used_as_is(self):
        self.assertEqual(adapters.final_message_from_text("I fixed it. All 3 tests pass."), "I fixed it. All 3 tests pass.")

    def test_unreadable_file_is_none_not_a_guess(self):
        self.assertIsNone(adapters.final_message(Path("/definitely/not/here.jsonl")))


class Payloads(unittest.TestCase):
    def test_snake_case_vscode_and_claude(self):
        i = adapters.parse_hook_payload({"cwd": "/r", "transcript_path": "/t", "session_id": "s", "stop_hook_active": True})
        self.assertEqual((i["cwd"], i["transcript"], i["session"], i["loop"]), ("/r", "/t", "s", True))

    def test_camel_case_copilot_cli(self):
        i = adapters.parse_hook_payload({"cwd": "/r", "transcriptPath": "/t", "sessionId": "s"})
        self.assertEqual((i["cwd"], i["transcript"], i["loop"]), ("/r", "/t", False))

    def test_inline_message_is_preferred_source(self):
        self.assertEqual(adapters.parse_hook_payload({"cwd": "/r", "last_assistant_message": "done"})["message"], "done")


class HookEndToEnd(unittest.TestCase):
    def run_hook(self, payload):
        return subprocess.run([sys.executable, "-m", "agentvow", "check", "--hook"], capture_output=True, text=True, cwd=ROOT,
                              input=json.dumps(payload), env={**os.environ})

    def test_copilot_style_payload_writes_report_files_and_never_blocks(self):
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            tr = Path(t) / "transcript.jsonl"
            tr.write_text(GENERIC + "\n")
            r = self.run_hook({"cwd": str(repo), "transcript_path": str(tr), "session_id": "s1"})
            out = json.loads(r.stdout)
            self.assertEqual(r.returncode, 0)
            self.assertNotIn("decision", out)
            self.assertIn("REVIEW REQUIRED", out["systemMessage"])
            last = repo / ".agentvow" / "last"
            self.assertTrue((last / "report.html").is_file())
            self.assertEqual(json.loads((last / "decision.json").read_text())["status"], decision.REVIEW)

    def test_inline_message_without_transcript(self):
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            r = self.run_hook({"cwd": str(repo), "last_assistant_message": "No downstream impact."})
            self.assertIn("REVIEW REQUIRED", json.loads(r.stdout)["systemMessage"])


class Markdown(unittest.TestCase):
    def test_markdown_summary_and_escaping(self):
        d = decision.Decision(decision.REVIEW, "abcdef1234", False, ["a.py"],
                              [decision.Finding("<b>x</b> | y", "x", "CONTRADICTED", "w <i>", ["e"], ["u"])], "s", [])
        md = report.render_markdown(d)
        self.assertIn(report.MARKER, md)
        self.assertIn("Review before approving", md)
        self.assertNotIn("<b>x</b>", md)
        self.assertIn("**Contradicted**", md)

    def test_agent_text_cannot_inject_links_images_or_html(self):
        evil = "![t](http://evil.example/p.png) [click](http://evil.example) <img src=x onerror=1> `code`"
        d = decision.Decision(decision.REVIEW, "abcdef1234", False, [],
                              [decision.Finding(evil, "x", "UNKNOWN", evil, [evil], [evil])], "s", [])
        md = report.render_markdown(d)
        self.assertNotRegex(md, r"(?<!\\)!\[|(?<!\\)\]\(|(?<!\\)<img")


class CISha(unittest.TestCase):
    def test_pr_head_sha_overrides_a_synthetic_merge_commit(self):
        seen = []
        fetch = lambda path: seen.append(path) or {"check_runs": [{"name": "tests", "status": "completed", "conclusion": "success"}], "total_count": 1}
        ev = ci.ci_evidence(Path("."), Snapshot("mergecommit", False), fetch=fetch, slug="o/r", sha="prheadsha")
        self.assertTrue(any("prheadsha" in p for p in seen))
        self.assertEqual(len(ev), 1)


if __name__ == "__main__":
    unittest.main()
