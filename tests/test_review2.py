import json, os, subprocess, tempfile, unittest
from pathlib import Path
from agentvow import api_diff, cli, reality


def mkrepo(d):
    r = Path(d) / "r"; r.mkdir()
    g = lambda *x: subprocess.run(["git", "-C", str(r), *x], check=True, capture_output=True)
    g("init", "-q", "-b", "main"); g("config", "user.email", "a@b"); g("config", "user.name", "t")
    (r / "a.py").write_text("def f():\n    return 1\n"); g("add", "."); g("commit", "-qm", "i")
    return r


class Review2(unittest.TestCase):
    def test_symlink_not_copied_into_worktree(self):
        with tempfile.TemporaryDirectory() as d:
            r = mkrepo(d); secret = Path(d) / "secret"; secret.write_text("TOPSECRET")
            os.symlink(secret, r / "link")
            seen = Path(d) / "seen.txt"
            cli.collect_test_evidence(r, "HEAD", [("t", ["/bin/sh", "-c", f"cat link > {seen} 2>/dev/null; true"], "")], timeout=30)
            self.assertFalse(seen.exists() and "TOPSECRET" in seen.read_text())

    def test_tree_hash_does_not_read_symlink_target(self):
        with tempfile.TemporaryDirectory() as d:
            r = mkrepo(d); big = Path(d) / "t"; big.write_text("x")
            os.symlink(big, r / "l"); h1 = reality._tree_hash(r, "c"); big.write_text("changed")
            self.assertEqual(h1, reality._tree_hash(r, "c"))

    def test_recursion_error_is_a_gap_not_a_crash(self):
        with tempfile.TemporaryDirectory() as d:
            r = mkrepo(d); (r / "deep.py").write_text("x = " + "+".join(["1"] * 60000) + "\n")
            g = reality.build_graph(r)
            self.assertTrue(any("deep.py" in x for x in g.gaps))

    def test_hook_crash_replaces_stale_result_with_sealed_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["AGENTVOW_HOME"] = str(Path(d) / "home")
            r = mkrepo(d)
            cli.main_hook = None
            from agentvow import decision
            orig = decision.check
            def boom(*a, **k): raise RecursionError("x")
            cli.check = boom
            try:
                import io, sys
                sys.stdin = io.StringIO(json.dumps({"cwd": str(r), "last_assistant_message": "No downstream impact."}))
                out = io.StringIO(); so = sys.stdout; sys.stdout = out
                try:
                    cli.main(["check", "--hook"])
                finally:
                    sys.stdout = so; sys.stdin = sys.__stdin__
            finally:
                cli.check = orig
            dec = json.loads((r / ".agentvow/last/decision.json").read_text())
            self.assertTrue(dec["status"].startswith("INSUFF"))
            self.assertEqual(dec["repo"], os.path.realpath(r))

    def test_option_like_base_rejected(self):
        with self.assertRaises(SystemExit):
            cli.main(["check", "--base", "--output=x", "--repo", "."])


if __name__ == "__main__":
    unittest.main()
