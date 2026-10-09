import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "examples"))
os.environ.setdefault("AGENTMIRROR_HOME", tempfile.mkdtemp(prefix="am_home_"))
from agentmirror import cli  # noqa: E402
from make_demo import build  # noqa: E402


def cmd(*args, cwd=ROOT):
    return subprocess.run([sys.executable, "-m", "agentmirror", *args], capture_output=True, text=True, cwd=cwd, env={**os.environ})


class Instructions(unittest.TestCase):
    def test_block_is_delimited_and_quotes_paths_with_spaces(self):
        b = cli.instructions_block("/Users/me/My Tools/agentmirror")
        self.assertTrue(b.startswith(cli.INSTR_BEGIN) and b.rstrip().endswith(cli.INSTR_END))
        self.assertIn('"/Users/me/My Tools/agentmirror" check', b)
        self.assertIn("|| true", b)                      # a non-zero verdict exit code must not make the agent's tool call fail

    def test_write_creates_appends_once_and_preserves_existing_content(self):
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / ".github" / "copilot-instructions.md"
            self.assertEqual(cmd("agent-instructions", "--write", str(f)).returncode, 0)
            self.assertIn(cli.INSTR_BEGIN, f.read_text())
            before = f.read_text()
            self.assertIn("already contains", cmd("agent-instructions", "--write", str(f)).stdout)
            self.assertEqual(f.read_text(), before)      # idempotent
            g = Path(t) / "existing.md"
            g.write_text("# My own instructions\nBe concise.\n")
            cmd("agent-instructions", "--write", str(g))
            self.assertTrue(g.read_text().startswith("# My own instructions\nBe concise."))
            self.assertEqual(g.read_text().count(cli.INSTR_BEGIN), 1)

    def test_write_refuses_a_symlink(self):
        with tempfile.TemporaryDirectory() as t:
            victim = Path(t) / "victim.md"
            victim.write_text("keep")
            link = Path(t) / "link.md"
            os.symlink(victim, link)
            self.assertEqual(cmd("agent-instructions", "--write", str(link)).returncode, 3)
            self.assertEqual(victim.read_text(), "keep")

    def test_the_command_in_the_block_really_runs_and_shows_the_verdict(self):
        with tempfile.TemporaryDirectory() as t:
            shim = Path(t) / "agentmirror"
            shim.write_text(f'#!/bin/sh\nPYTHONPATH={ROOT} exec {sys.executable} -m agentmirror "$@"\n')
            shim.chmod(0o755)
            repo = build(Path(t) / "repo")
            block = cli.instructions_block(str(shim))
            script = re.search(r"```bash\n(.*?)\n```", block, re.S).group(1).replace("<your draft final answer>", "I changed it. There is no downstream impact.")
            r = subprocess.run(["bash", "-c", script], cwd=repo, capture_output=True, text=True, env={**os.environ})
            self.assertEqual(r.returncode, 0, r.stderr)    # '|| true'
            self.assertIn("AgentMirror", r.stdout)
            self.assertIn("Contradicted", r.stdout)

    def test_version_flag(self):
        r = cmd("--version")
        self.assertEqual(r.returncode, 0)
        self.assertRegex(r.stdout, r"agentmirror \d+\.\d+\.\d+")


if __name__ == "__main__":
    unittest.main()
