import io, json, subprocess, sys, tempfile, unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agentvow import cli, init  # noqa: E402

PREFIX = "/opt/x/bin/agentvow"


def run(*args):
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.object(init, "command_prefix", return_value=PREFIX), redirect_stdout(out), redirect_stderr(err):
        code = cli.main(["init", *args])
    return code, out.getvalue(), err.getvalue()


class Init(unittest.TestCase):
    def repo(self):
        d = Path(tempfile.mkdtemp())
        subprocess.run(["git", "init", "-q", str(d)], check=True)
        (d / ".venv" / "bin").mkdir(parents=True)
        (d / ".venv" / "bin" / "python").write_text("")
        return d

    def test_dry_run_writes_nothing(self):
        d = self.repo()
        code, out, _ = run("--repo", str(d), "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("Dry run", out)
        self.assertFalse((d / ".claude").exists())
        self.assertNotIn(".agentvow", (d / ".git" / "info" / "exclude").read_text() if (d / ".git" / "info" / "exclude").exists() else "")

    def test_writes_both_hooks_exclude_and_is_idempotent(self):
        d = self.repo()
        code, out, _ = run("--repo", str(d), "--yes", "--no-verify")
        self.assertEqual(code, 0, out)
        s = json.loads((d / ".claude" / "settings.local.json").read_text())
        self.assertEqual(s["hooks"]["PostToolUse"][0]["matcher"], "Bash")
        self.assertEqual(s["hooks"]["PostToolUse"][0]["hooks"][0]["command"], f"{PREFIX} post-test-hook")
        self.assertEqual(s["hooks"]["Stop"][0]["hooks"][0]["command"], f"{PREFIX} check --hook --evidence-pack")
        self.assertIn(".agentvow/", (d / ".git" / "info" / "exclude").read_text())
        before = (d / ".claude" / "settings.local.json").read_text()
        code, out, _ = run("--repo", str(d), "--yes", "--no-verify")
        self.assertIn("Nothing to change", out)
        self.assertEqual((d / ".claude" / "settings.local.json").read_text(), before)
        self.assertEqual(len(list((d / ".claude").glob("*backup*"))), 0)
        self.assertEqual((d / ".git" / "info" / "exclude").read_text().count(".agentvow/"), 1)

    def test_other_settings_and_hooks_kept_and_backup_made(self):
        d = self.repo()
        (d / ".claude").mkdir()
        mine = {"model": "x", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo hi"}]}], "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "lint"}]}]}}
        (d / ".claude" / "settings.local.json").write_text(json.dumps(mine))
        code, out, _ = run("--repo", str(d), "--yes", "--no-verify")
        self.assertEqual(code, 0, out)
        s = json.loads((d / ".claude" / "settings.local.json").read_text())
        self.assertEqual(s["model"], "x")
        self.assertEqual(s["hooks"]["PreToolUse"], mine["hooks"]["PreToolUse"])
        self.assertEqual(len(s["hooks"]["Stop"]), 2)
        self.assertEqual(s["hooks"]["Stop"][0]["hooks"][0]["command"], "echo hi")
        b = list((d / ".claude").glob("*backup*"))
        self.assertEqual(len(b), 1)
        self.assertEqual(json.loads(b[0].read_text()), mine)

    def test_unreadable_settings_never_overwritten(self):
        d = self.repo()
        (d / ".claude").mkdir()
        (d / ".claude" / "settings.local.json").write_text("{not json")
        code, out, err = run("--repo", str(d), "--yes", "--no-verify")
        self.assertEqual(code, 3)
        self.assertEqual((d / ".claude" / "settings.local.json").read_text(), "{not json")
        self.assertIn("not touched", err)

    def test_no_confirmation_without_a_terminal_writes_nothing(self):
        d = self.repo()
        with mock.patch.object(sys.stdin, "isatty", return_value=False):
            code, out, err = run("--repo", str(d), "--no-verify")
        self.assertEqual(code, 2)
        self.assertFalse((d / ".claude").exists())
        self.assertIn("--yes", err)

    def test_older_agentvow_stop_hook_is_replaced_not_duplicated(self):
        d = self.repo()
        (d / ".claude").mkdir()
        old = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "/old/agentvow check --hook"}]}]}}
        (d / ".claude" / "settings.local.json").write_text(json.dumps(old))
        run("--repo", str(d), "--yes", "--no-verify")
        s = json.loads((d / ".claude" / "settings.local.json").read_text())
        cmds = [h["command"] for g in s["hooks"]["Stop"] for h in g["hooks"]]
        self.assertEqual(cmds, [f"{PREFIX} check --hook --evidence-pack"])   # an older Agentvow Stop hook is replaced, so the check does not run twice

    def test_replaces_own_entry_with_a_different_path(self):
        d = self.repo()
        (d / ".claude").mkdir()
        old = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "/old/agentvow check --hook --evidence-pack", "timeout": 5}]}]}}
        (d / ".claude" / "settings.local.json").write_text(json.dumps(old))
        run("--repo", str(d), "--yes", "--no-verify")
        s = json.loads((d / ".claude" / "settings.local.json").read_text())
        self.assertEqual([h["command"] for g in s["hooks"]["Stop"] for h in g["hooks"]], [f"{PREFIX} check --hook --evidence-pack"])

    def test_remove_only_our_entries(self):
        d = self.repo()
        (d / ".claude").mkdir()
        (d / ".claude" / "settings.local.json").write_text(json.dumps({"model": "x", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo hi"}]}]}}))
        run("--repo", str(d), "--yes", "--no-verify")
        code, out, _ = run("--repo", str(d), "--remove", "--yes")
        self.assertEqual(code, 0, out)
        s = json.loads((d / ".claude" / "settings.local.json").read_text())
        self.assertEqual(s, {"model": "x", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo hi"}]}]}})

    def test_shared_and_user_conflict_and_shared_warning(self):
        d = self.repo()
        self.assertEqual(run("--repo", str(d), "--shared", "--user", "--dry-run")[0], 3)
        code, out, _ = run("--repo", str(d), "--shared", "--dry-run")
        self.assertIn("every teammate", out)
        self.assertIn("settings.json", out)

    def test_exclude_not_added_when_already_ignored(self):
        d = self.repo()
        (d / ".gitignore").write_text(".agentvow/\n")
        run("--repo", str(d), "--yes", "--no-verify")
        ex = d / ".git" / "info" / "exclude"
        self.assertNotIn(".agentvow", ex.read_text() if ex.exists() else "")

    def test_warns_without_a_python_environment(self):
        d = Path(tempfile.mkdtemp())
        subprocess.run(["git", "init", "-q", str(d)], check=True)
        with mock.patch.dict("os.environ", {"VIRTUAL_ENV": ""}):
            code, out, _ = run("--repo", str(d), "--dry-run")
        self.assertIn("no .venv", out)


if __name__ == "__main__":
    unittest.main()
