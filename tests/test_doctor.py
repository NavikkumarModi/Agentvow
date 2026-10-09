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
os.environ.setdefault("AGENTVOW_HOME", tempfile.mkdtemp(prefix="am_home_"))
from agentvow import adapters, doctor  # noqa: E402
from make_demo import build  # noqa: E402

SECRET = "TOP-SECRET-MARKER-12345"


class Shapes(unittest.TestCase):
    def test_shape_contains_structure_never_content(self):
        obj = {"role": "assistant", "content": [{"type": "text", "text": f"{SECRET} password=hunter2"}], "path": "/Users/me/secret.txt", "n": 3, "ok": True}
        shape = json.dumps(adapters.shape_of(obj))
        self.assertNotIn(SECRET, shape)
        self.assertNotIn("hunter2", shape)
        self.assertNotIn("/Users/me", shape)
        self.assertIn("str[", shape)
        self.assertIn("content", shape)

    def test_transcript_shapes_are_bounded_and_content_free(self):
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / "t.jsonl"
            f.write_text("\n".join(json.dumps({"role": "assistant", "content": f"{SECRET} {i}"}) for i in range(500)) + "\nnot json\n")
            out = adapters.transcript_shapes(f)
            self.assertLessEqual(out["records_sampled"], 8)
            self.assertNotIn(SECRET, json.dumps(out))

    def test_missing_transcript_is_reported_not_raised(self):
        self.assertIn("error", adapters.transcript_shapes(Path("/definitely/not/here")))


class DebugMode(unittest.TestCase):
    def hook(self, payload, debug):
        env = {**os.environ}
        if debug:
            env["AGENTVOW_DEBUG"] = "1"
        return subprocess.run([sys.executable, "-m", "agentvow", "check", "--hook"], capture_output=True, text=True, cwd=ROOT,
                              input=json.dumps(payload), env=env)

    def test_debug_writes_a_content_free_shape_file(self):
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            tr = Path(t) / "tr.jsonl"
            tr.write_text(json.dumps({"role": "assistant", "content": f"{SECRET} No downstream impact."}) + "\n")
            r = self.hook({"cwd": str(repo), "transcript_path": str(tr), "session_id": "s", "extra": {"deep": SECRET}}, debug=True)
            self.assertEqual(r.returncode, 0)
            shape = (repo / ".agentvow" / "last" / "payload_shape.json").read_text()
            self.assertNotIn(SECRET, shape)
            self.assertIn("hook_payload", shape)
            self.assertIn("transcript", shape)

    def test_no_shape_file_without_the_debug_variable(self):
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            self.hook({"cwd": str(repo), "last_assistant_message": "No downstream impact."}, debug=False)
            self.assertFalse((repo / ".agentvow" / "last" / "payload_shape.json").exists())

    def test_camelcase_copilot_cli_payload_end_to_end(self):
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            tr = Path(t) / "tr.jsonl"
            tr.write_text(json.dumps({"role": "assistant", "content": "No downstream impact."}) + "\n")
            r = self.hook({"cwd": str(repo), "transcriptPath": str(tr), "sessionId": "s", "stopReason": "end_turn", "stop_hook_active": False}, debug=False)
            out = json.loads(r.stdout)
            self.assertIn("REVIEW REQUIRED", out["systemMessage"])
            self.assertNotIn("decision", out)


class Doctor(unittest.TestCase):
    def test_self_test_passes_for_both_payload_styles(self):
        for camel in (False, True):
            ok, detail = doctor.self_test(camel=camel)
            self.assertTrue(ok, detail)

    def test_doctor_reports_a_bare_command_hook_and_exits_zero_when_nothing_failed(self):
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            (repo / ".github" / "hooks").mkdir(parents=True)
            (repo / ".github" / "hooks" / "agentvow.json").write_text(json.dumps(
                {"version": 1, "hooks": {"Stop": [{"type": "command", "command": "agentvow check --hook"}]}}))
            r = subprocess.run([sys.executable, "-m", "agentvow", "doctor", "--repo", str(repo)], capture_output=True, text=True, cwd=ROOT,
                               env={**os.environ})
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("hook uses a bare command name", r.stdout)
            self.assertIn("no result yet", r.stdout)
            self.assertIn("end-to-end hook self-test (camelCase", r.stdout)

    def test_doctor_flags_a_broken_hook_file(self):
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            (repo / ".github" / "hooks").mkdir(parents=True)
            (repo / ".github" / "hooks" / "agentvow.json").write_text("{not json")
            r = subprocess.run([sys.executable, "-m", "agentvow", "doctor", "--repo", str(repo)], capture_output=True, text=True, cwd=ROOT,
                               env={**os.environ})
            self.assertEqual(r.returncode, 1)
            self.assertIn("invalid", r.stdout)


if __name__ == "__main__":
    unittest.main()
