"""Regression: tests that write to $HOME (caches, config) must not fail merely because of the sandbox."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "examples"))
from agentmirror import runner  # noqa: E402
from make_demo import build  # noqa: E402


class HomeIsWritable(unittest.TestCase):
    def test_writing_to_home_inside_the_sandbox_works(self):
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            rec = runner.run_tests(repo, ["sh", "-c", "mkdir -p $HOME/.cache/x && echo ok > $HOME/.cache/x/f && echo '1 passed in 0.01s'"], write=False)
            self.assertEqual(rec["counts"].get("passed"), 1, rec["summary"])

    def test_writing_outside_the_allowed_paths_is_still_blocked(self):
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            target = Path.home() / "agentmirror_should_not_exist.txt"
            rec = runner.run_tests(repo, ["sh", "-c", f"echo x > {target} 2>/dev/null && echo '1 passed in 0.01s' || echo '1 failed in 0.01s'"], write=False)
            self.assertFalse(target.exists())
            self.assertEqual(rec["counts"].get("failed"), 1)

    def test_home_is_excluded_from_the_tree_hash(self):
        from agentmirror import reality
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            before = reality.snapshot(repo)
            runner.run_tests(repo, ["sh", "-c", "echo hi > $HOME/f; echo '1 passed in 0.01s'"], write=False)
            after = reality.snapshot(repo)
            self.assertEqual((before.dirty, after.dirty), (False, False))


if __name__ == "__main__":
    unittest.main()
