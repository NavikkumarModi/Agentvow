import json, os, tempfile, unittest
from pathlib import Path
from agentmirror import adapters


class Bounds(unittest.TestCase):
    def test_huge_transcript_only_tail_read_and_answer_found(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.jsonl"
            line = json.dumps({"type": "assistant.message", "data": {"content": "work " + "x" * 200, "phase": "commentary"}}) + "\n"
            with p.open("w") as f:
                f.write(json.dumps({"type": "user.message", "data": {"content": "hi"}}) + "\n")
                for _ in range(60000):   # ~14 MB > 8 MB limit
                    f.write(line)
                f.write(json.dumps({"type": "assistant.message", "data": {"content": "All 3 tests pass.", "phase": "final_answer"}}) + "\n")
            self.assertGreater(p.stat().st_size, adapters.MAX_TRANSCRIPT_BYTES)
            self.assertEqual(adapters.final_message_info_file(p)[0], "All 3 tests pass.")

    def test_fifo_is_refused_not_hung(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "fifo"; os.mkfifo(f)
            self.assertEqual(adapters.final_message_info_file(f), (None, False, False))

    def test_deeply_nested_or_huge_line_skipped(self):
        self.assertLessEqual(len(adapters.final_message_info("[" * 3_000_000 + "\n")[0] or ""), 6100)   # no crash, bounded

    def test_missing_file(self):
        self.assertEqual(adapters.final_message_info_file(Path("/nonexistent/x")), (None, False, False))


if __name__ == "__main__":
    unittest.main()
