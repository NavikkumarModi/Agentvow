import json, os, subprocess, sys, tempfile, time, unittest
from pathlib import Path
from agentvow import reality


def _online():
    try:
        import socket
        socket.create_connection(("pypi.org", 443), timeout=3).close(); return True
    except OSError:
        return False


@unittest.skipUnless(_online(), "needs network (builds a virtualenv and a replay environment)")
class HookCapsuleBackground(unittest.TestCase):
    def test_the_stop_hook_captures_then_the_background_run_replays_from_the_capsule_with_coverage(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d) / "home"; os.environ["AGENTVOW_HOME"] = str(home)
            r = Path(d) / "r"; (r / "tests").mkdir(parents=True)
            g = lambda *x: subprocess.run(["git", "-C", str(r), *x], check=True, capture_output=True)
            g("init", "-q", "-b", "main"); g("config", "user.email", "a@b"); g("config", "user.name", "t")
            (r / ".gitignore").write_text(".venv/\n.agentvow/\n")
            (r / "lib.py").write_text("def f():\n    return 1\n"); (r / "tests" / "__init__.py").write_text("")
            (r / "tests" / "test_a.py").write_text("import lib\n\ndef test_f():\n    assert lib.f() in (1, 2)\n")
            g("add", "."); g("commit", "-qm", "base")
            (r / "lib.py").write_text("def f():\n    return 2\n\ndef unused():\n    return 3\n"); g("commit", "-qam", "change")
            subprocess.run([sys.executable, "-m", "venv", str(r / ".venv")], check=True, capture_output=True)
            subprocess.run([str(r / ".venv" / "bin" / "pip"), "install", "-q", "pytest"], check=True, capture_output=True)
            tr = Path(d) / "t.jsonl"
            tr.write_text(json.dumps({"role": "assistant", "content": "I changed lib.f. All tests pass."}) + "\n")
            payload = {"cwd": str(r), "transcript_path": str(tr), "session_id": "s", "hook_event_name": "Stop"}
            env = {**os.environ, "AGENTVOW_HOME": str(home)}
            p = subprocess.run(reality.isolated_argv(sys.executable, "check", "--hook", "--background-tests", "--capture", "--changed-coverage"),
                               cwd=d, input=json.dumps(payload), capture_output=True, text=True, timeout=120, env=env)
            self.assertEqual(p.returncode, 0, p.stderr[-300:])
            out = json.loads(p.stdout)
            self.assertNotIn("decision", out)   # never blocks
            self.assertTrue(list((r / ".agentvow" / "capsules").glob("*.json")), "the hook did not write a capsule")
            dec = r / ".agentvow" / "last" / "decision.json"
            deadline, text = time.time() + 240, ""
            while time.time() < deadline:
                text = dec.read_text() if dec.is_file() else ""
                if "built from the packages captured" in text or "capture-based test run was not made" in text:
                    break
                time.sleep(3)
            self.assertIn("built from the packages captured", text, text[-600:])
            self.assertIn("Changed-line coverage", text)
            self.assertIn("captured_environment", text)
