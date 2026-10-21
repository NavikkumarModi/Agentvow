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

    def test_existing_agentvow_hook_with_other_command_is_left_alone_unless_forced(self):
        d = self.repo()
        (d / ".claude").mkdir()
        old = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "/old/agentvow check --hook --python .venv/bin/python", "timeout": 5}]}]}}
        (d / ".claude" / "settings.local.json").write_text(json.dumps(old))
        code, out, _ = run("--repo", str(d), "--yes", "--no-verify")
        s = json.loads((d / ".claude" / "settings.local.json").read_text())
        self.assertEqual([h["command"] for g in s["hooks"]["Stop"] for h in g["hooks"]], ["/old/agentvow check --hook --python .venv/bin/python"])   # customised flags kept
        self.assertIn("left unchanged", out)
        self.assertIn("PostToolUse", s["hooks"])   # the other hook was still added
        run("--repo", str(d), "--yes", "--no-verify", "--force")
        s = json.loads((d / ".claude" / "settings.local.json").read_text())
        self.assertEqual([h["command"] for g in s["hooks"]["Stop"] for h in g["hooks"]], [f"{PREFIX} check --hook --evidence-pack"])

    def test_force_replaces_only_our_command_not_other_hooks_in_the_same_group(self):
        d = self.repo()
        (d / ".claude").mkdir()
        grp = {"hooks": [{"type": "command", "command": "notify-me.sh"}, {"type": "command", "command": "/old/agentvow check --hook"}]}
        (d / ".claude" / "settings.local.json").write_text(json.dumps({"hooks": {"Stop": [grp]}}))
        code, out, _ = run("--repo", str(d), "--yes", "--no-verify", "--force")
        s = json.loads((d / ".claude" / "settings.local.json").read_text())
        cmds = [h["command"] for g in s["hooks"]["Stop"] for h in g["hooks"]]
        self.assertEqual(cmds, ["notify-me.sh", f"{PREFIX} check --hook --evidence-pack"])
        self.assertIn("replaced `/old/agentvow check --hook`", out)
        run("--repo", str(d), "--remove", "--yes")
        s = json.loads((d / ".claude" / "settings.local.json").read_text())
        self.assertEqual([h["command"] for g in s["hooks"]["Stop"] for h in g["hooks"]], ["notify-me.sh"])

    def test_lookalike_commands_are_not_ours(self):
        self.assertFalse(init._ours("my-agentvow-linter check --hook-x", "Stop"))
        self.assertFalse(init._ours("echo agentvow check --hook", "Stop"))
        self.assertTrue(init._ours("/a/b/agentvow check --hook --evidence-pack", "Stop"))
        self.assertTrue(init._ours("/usr/bin/python3 -I -m agentvow check --hook", "Stop"))
        self.assertTrue(init._ours("agentvow post-test-hook", "PostToolUse"))
        self.assertFalse(init._ours("agentvow post-test-hook", "Stop"))

    def test_fallback_prefix_is_isolated(self):
        with mock.patch.object(init.shutil, "which", return_value=None), mock.patch.object(init.Path, "is_file", return_value=False):
            self.assertIn(" -I -m agentvow", init.command_prefix())

    def test_symlinked_target_folder_or_file_is_refused(self):
        d = self.repo()
        victim = Path(tempfile.mkdtemp()) / "victim"
        victim.mkdir()
        (d / ".claude").symlink_to(victim)
        code, out, err = run("--repo", str(d), "--yes", "--no-verify")
        self.assertEqual(code, 3)
        self.assertIn("symbolic link", err)
        self.assertEqual(list(victim.iterdir()), [])
        (d / ".claude").unlink()
        (d / ".claude").mkdir()
        (d / ".claude" / "settings.local.json").symlink_to(victim / "x.json")
        self.assertEqual(run("--repo", str(d), "--yes", "--no-verify")[0], 3)

    def test_planted_predictable_temp_name_is_never_written_through(self):
        d = self.repo()
        (d / ".claude").mkdir()
        victim = Path(tempfile.mkdtemp()) / "zshrc"
        victim.write_text("keep me")
        (d / ".claude" / "settings.local.json.agentvow-tmp").symlink_to(victim)
        run("--repo", str(d), "--yes", "--no-verify")
        self.assertEqual(victim.read_text(), "keep me")
        self.assertTrue((d / ".claude" / "settings.local.json").is_file())

    def test_file_mode_is_kept_and_text_is_not_escaped(self):
        import os, stat
        d = self.repo()
        (d / ".claude").mkdir()
        f = d / ".claude" / "settings.local.json"
        f.write_text(json.dumps({"note": "caf\u00e9"}, ensure_ascii=False), encoding="utf-8")
        os.chmod(f, 0o600)
        run("--repo", str(d), "--yes", "--no-verify")
        self.assertEqual(stat.S_IMODE(f.stat().st_mode), 0o600)
        self.assertIn("café", f.read_text(encoding="utf-8"))

    def test_worktree_where_dot_git_is_a_file_gets_the_exclude_entry(self):
        d = self.repo()
        subprocess.run(["git", "-C", str(d), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "x"], check=True)
        wt = Path(tempfile.mkdtemp()) / "wt"
        subprocess.run(["git", "-C", str(d), "worktree", "add", "-q", "--detach", str(wt)], check=True)
        self.assertTrue((wt / ".git").is_file())
        (wt / ".venv" / "bin").mkdir(parents=True); (wt / ".venv" / "bin" / "python").write_text("")
        code, out, _ = run("--repo", str(wt), "--yes", "--no-verify")
        self.assertEqual(code, 0, out)
        ex = Path(subprocess.run(["git", "-C", str(wt), "rev-parse", "--git-path", "info/exclude"], capture_output=True, text=True).stdout.strip())
        ex = ex if ex.is_absolute() else wt / ex
        self.assertIn(".agentvow/", ex.read_text())

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
