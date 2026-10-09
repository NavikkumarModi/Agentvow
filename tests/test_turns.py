import io, json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
from agentmirror import cli, reality


def mk(d):
    r = Path(d) / "r"; r.mkdir()
    g = lambda *x: subprocess.run(["git", "-C", str(r), *x], check=True, capture_output=True)
    g("init", "-q", "-b", "main"); g("config", "user.email", "a@b"); g("config", "user.name", "t")
    (r / "a.py").write_text("X = 1\n"); (r / "b.py").write_text("Y = 1\n"); g("add", "."); g("commit", "-qm", "i")
    return r


def hook(r, msg="No downstream impact."):
    old = sys.stdin, sys.stdout
    sys.stdin = io.StringIO(json.dumps({"cwd": str(r), "last_assistant_message": msg})); sys.stdout = io.StringIO()
    try:
        cli.main(["check", "--hook"])
    finally:
        sys.stdin, sys.stdout = old
    return json.loads((r / ".agentmirror/last/decision.json").read_text())


class Turns(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory(); os.environ["AGENTMIRROR_HOME"] = str(Path(self.d.name) / "home")
        self.r = mk(self.d.name)

    def tearDown(self):
        self.d.cleanup()

    def test_only_this_turns_changes_are_counted(self):
        (self.r / "b.py").write_text("Y = 2\n")   # pre-existing uncommitted work
        first = hook(self.r)
        self.assertIn("First check", first["scope"])
        self.assertIn("b.py", first["changed"])
        (self.r / "a.py").write_text("X = 2\n")    # the agent's edit this turn
        second = hook(self.r)
        self.assertEqual(second["changed"], ["a.py"])
        self.assertIn("since the previous AgentMirror check", second["scope"])

    def test_tampered_state_is_ignored(self):
        hook(self.r)
        p = self.r / ".agentmirror" / "turn_state.json"
        rec = json.loads(p.read_text()); rec["files"] = {"x.py": "1"}; p.write_text(json.dumps(rec))
        self.assertIsNone(reality.load_turn_state(self.r))
        (self.r / "a.py").write_text("X = 3\n")
        self.assertIn("First check", hook(self.r)["scope"])

    def test_new_commit_counts_its_files(self):
        hook(self.r)
        (self.r / "a.py").write_text("X = 9\n")
        subprocess.run(["git", "-C", str(self.r), "commit", "-qam", "c"], check=True, capture_output=True)
        self.assertEqual(hook(self.r)["changed"], ["a.py"])


if __name__ == "__main__":
    unittest.main()


class Background(unittest.TestCase):
    def test_background_tests_update_the_result_after_the_hook_returns(self):
        import time
        with tempfile.TemporaryDirectory() as d:
            os.environ["AGENTMIRROR_HOME"] = str(Path(d) / "home")
            r = mk(d)
            (r / "tests").mkdir(); (r / "tests" / "test_a.py").write_text("def test_a():\n    assert True\n")
            subprocess.run(["git", "-C", str(r), "add", "."], check=True); subprocess.run(["git", "-C", str(r), "commit", "-qm", "t"], check=True, capture_output=True)
            (r / "a.py").write_text("X = 5\n")
            old = sys.stdin, sys.stdout
            sys.stdin = io.StringIO(json.dumps({"cwd": str(r), "last_assistant_message": "All 1 tests pass."})); sys.stdout = io.StringIO()
            try:
                cli.main(["check", "--hook", "--background-tests", "--python", sys.executable])
            finally:
                sys.stdin, sys.stdout = old
            first = json.loads((r / ".agentmirror/last/decision.json").read_text())
            self.assertNotIn("finished after", first["scope"])
            end = time.time() + 90
            done = None
            while time.time() < end:
                time.sleep(1)
                cur = json.loads((r / ".agentmirror/last/decision.json").read_text())
                if "finished after" in cur["scope"]:
                    done = cur; break
            self.assertIsNotNone(done, "background run never updated the result")
            self.assertNotEqual(done["run_id"], first["run_id"])
            self.assertEqual(done["findings"][0]["kind"], "tests_pass")
            self.assertNotEqual(done["findings"][0]["verdict"], "CONTRADICTED")
            self.assertTrue(reality.read_sealed_result(r / ".agentmirror/last")[0])
