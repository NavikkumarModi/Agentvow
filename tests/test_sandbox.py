"""The sandbox guarantees, asserted directly on whichever platform runs the tests (macOS sandbox-exec, Linux bubblewrap)."""
import os, subprocess, sys, tempfile, unittest
from pathlib import Path
from agentvow import runner


def sandboxed(code, repo, scratch, **kw):
    return subprocess.run(runner.wrap([sys.executable, "-c", code], repo, scratch, **kw), capture_output=True, text=True, timeout=60, cwd=repo)


@unittest.skipIf(runner.sandbox_problem(), "no working sandbox on this machine")
class Guarantees(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory(dir=runner.scratch_base())
        self.repo = Path(self.t.name, "repo").resolve(); self.repo.mkdir()
        self.scratch = Path(self.t.name, "s").resolve(); self.scratch.mkdir()

    def tearDown(self):
        self.t.cleanup()

    def test_can_write_inside_worktree_and_scratch_only(self):
        ok = sandboxed(f"open(r'{self.repo}/a','w').write('x'); open(r'{self.scratch}/b','w').write('x'); print('ok')", self.repo, self.scratch)
        self.assertEqual(ok.stdout.strip(), "ok", ok.stderr)
        outside = Path.home() / "agentvow_sandbox_probe.txt"
        try:
            bad = sandboxed(f"open(r'{outside}','w').write('x')", self.repo, self.scratch)
            self.assertNotEqual(bad.returncode, 0)
            self.assertFalse(outside.exists())
        finally:
            outside.unlink(missing_ok=True)

    def test_network_is_denied(self):
        code = "import socket\ns=socket.socket(); s.settimeout(5)\ntry:\n    s.connect(('1.1.1.1',53)); print('CONNECTED')\nexcept OSError as e:\n    print('blocked')\n"
        r = sandboxed(code, self.repo, self.scratch)
        self.assertEqual(r.stdout.strip(), "blocked", r.stdout + r.stderr)

    def test_signing_key_directory_is_unreadable(self):
        home = Path(self.t.name, "amhome").resolve(); home.mkdir(); (home / "key").write_text("SECRET")
        old = os.environ.get("AGENTVOW_HOME"); os.environ["AGENTVOW_HOME"] = str(home)
        try:
            r = sandboxed(f"import sys\ntry:\n    print('LEAK', open(r'{home}/key').read())\nexcept OSError:\n    print('denied')\n", self.repo, self.scratch)
        finally:
            if old is None: os.environ.pop("AGENTVOW_HOME", None)
            else: os.environ["AGENTVOW_HOME"] = old
        self.assertEqual(r.stdout.strip(), "denied", r.stdout + r.stderr)

    def test_install_mode_allows_network_flag_only_when_asked(self):
        cmd = runner.wrap(["true"], self.repo, None, network=True, writable=[self.repo])
        if sys.platform.startswith("linux"):
            self.assertNotIn("--unshare-net", cmd)
        self.assertEqual(subprocess.run(cmd, capture_output=True).returncode, 0)


if __name__ == "__main__":
    unittest.main()
