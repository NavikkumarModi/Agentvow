import io, json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
from agentvow import capsule, cli


def _online():
    try:
        import socket
        socket.create_connection(("pypi.org", 443), timeout=3).close(); return True
    except OSError:
        return False


def mkrepo(d, venv=True):
    r = Path(d) / "r"; (r / "tests").mkdir(parents=True)
    g = lambda *x: subprocess.run(["git", "-C", str(r), *x], check=True, capture_output=True)
    g("init", "-q", "-b", "main"); g("config", "user.email", "a@b"); g("config", "user.name", "t")
    (r / ".gitignore").write_text(".venv/\n.agentvow/\n")
    (r / "lib.py").write_text("def f():\n    return 1\n"); (r / "tests" / "__init__.py").write_text("")
    (r / "tests" / "test_a.py").write_text("import lib\n\ndef test_f():\n    assert lib.f() in (1, 2)\n")
    g("add", "."); g("commit", "-qm", "base")
    (r / "lib.py").write_text("def f():\n    return 2\n"); g("commit", "-qam", "change")
    return r


class NoNetwork(unittest.TestCase):
    def test_no_environment_means_no_capsule_and_never_agentvows_own_interpreter(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["AGENTVOW_HOME"] = str(Path(d) / "home")
            os.environ.pop("VIRTUAL_ENV", None)
            r = mkrepo(d)
            rec, msg = capsule.capture(r)
            self.assertIsNone(rec)
            self.assertIn("no project environment", msg)

    def test_a_capsule_for_another_state_or_with_a_bad_signature_is_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["AGENTVOW_HOME"] = str(Path(d) / "home")
            r = mkrepo(d)
            from agentvow import reality
            snap = reality.snapshot(r)
            rec = {"schema": capsule.SCHEMA, "commit": snap.commit, "tree": snap.tree, "packages": ["pytest==8.0.0"], "python_version": "3.12.0"}
            reality.safe_write(r, Path(".agentvow") / "capsules" / f"{snap.commit[:10]}_clean.json", json.dumps(reality.sign_record(rec)))
            self.assertIsNotNone(capsule.load(r))
            forged = dict(reality.sign_record(rec)); forged["packages"] = ["evil==1"]
            reality.safe_write(r, Path(".agentvow") / "capsules" / f"{snap.commit[:10]}_clean.json", json.dumps(forged))
            self.assertIsNone(capsule.load(r))   # signature no longer matches
            reality.safe_write(r, Path(".agentvow") / "capsules" / f"{snap.commit[:10]}_clean.json", json.dumps(reality.sign_record(rec)))
            (r / "lib.py").write_text("def f():\n    return 3\n")   # the state changed after the capture
            self.assertIsNone(capsule.load(r))

    def test_to_recipe_installs_only_the_pinned_file(self):
        rec, files = capsule.to_recipe({"commit": "c", "tree": "", "packages": ["pytest==8.0.0", "pluggy==1.4.0"], "python_version": "3.12.1"}, ["-m", "pytest", "-q"])
        self.assertEqual(rec.setup, [["-r", capsule.REQS]])
        self.assertEqual(files[capsule.REQS], "pytest==8.0.0\npluggy==1.4.0\n")


@unittest.skipUnless(_online(), "needs network (builds a virtualenv with pytest and replays from it)")
class EndToEnd(unittest.TestCase):
    def test_capture_then_replay_from_the_capsule_and_fail_closed_when_the_state_changes(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["AGENTVOW_HOME"] = str(Path(d) / "home")
            r = mkrepo(d)
            subprocess.run([sys.executable, "-m", "venv", str(r / ".venv")], check=True, capture_output=True)
            subprocess.run([str(r / ".venv" / "bin" / "pip"), "install", "-q", "pytest"], check=True, capture_output=True)
            rec, msg = capsule.capture(r)
            self.assertIsNotNone(rec, msg)
            self.assertTrue(any(p.startswith("pytest==") for p in rec["packages"]))
            self.assertFalse(rec["env_values_recorded"])

            def check():
                old = sys.stdin, sys.stdout, sys.stderr
                sys.stdin = io.StringIO("All tests pass."); out = io.StringIO(); sys.stdout = out; sys.stderr = io.StringIO()
                try:
                    cli.main(["check", "--repo", str(r), "--base", "HEAD~1", "--run-tests", "--from-capsule", "--json"])
                finally:
                    sys.stdin, sys.stdout, sys.stderr = old
                o = json.loads(out.getvalue())
                return o, [x for x in o["findings"] if x["kind"] == "tests_pass"][0]
            o, f = check()
            self.assertIn(f["verdict"], ("SUPPORTED_BY_PRIOR_EVIDENCE", "NOT_CONTRADICTED"), f)
            self.assertEqual(f["meta"].get("support_basis"), "captured_environment", f)
            self.assertIn("CAPTURED", f["why"])
            self.assertIn("captured when the agent ran its tests", o["scope"])
            (r / "lib.py").write_text("def f():\n    return 3\n")   # state changed: the capsule no longer applies
            o2, f2 = check()
            self.assertEqual(f2["verdict"], "UNKNOWN")
            self.assertIn("no environment capsule exists for this exact state", o2["scope"])


if __name__ == "__main__":
    unittest.main()


class TestTimeCapture(unittest.TestCase):
    def test_which_commands_count_as_test_runs(self):
        for cmd, want in (("cd x && .venv/bin/python -m pytest -q", True), ("pip install pytest", False), ("make test", True), ("ls", False), ("FOO=1 uv run pytest tests/", True),
                          ("echo pytest", False), ("python manage.py test app", True), (".venv/bin/pytest -x", True), ("cat tests/test_x.py | grep pytest", False), ("", False)):
            self.assertEqual(capsule.looks_like_test_command(cmd), want, cmd)

    def _setup(self, d):
        os.environ["AGENTVOW_HOME"] = str(Path(d) / "home")
        r = mkrepo(d)
        subprocess.run([sys.executable, "-m", "venv", str(r / ".venv")], check=True, capture_output=True)
        return r

    def _hook(self, r, cmd, tool="Bash"):
        payload = json.dumps({"tool_name": tool, "tool_input": {"command": cmd}, "cwd": str(r), "hook_event_name": "PostToolUse"})
        from agentvow import reality
        return subprocess.run(reality.isolated_argv(sys.executable, "post-test-hook"), input=payload, capture_output=True, text=True, timeout=120, env={**os.environ})

    def test_the_post_tool_hook_captures_only_after_a_test_command_and_is_silent(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._setup(d)
            p = self._hook(r, "ls -la")
            self.assertEqual((p.returncode, p.stdout), (0, ""))
            self.assertEqual(capsule.history(r), [])
            p = self._hook(r, ".venv/bin/python -m pytest -q")
            self.assertEqual((p.returncode, p.stdout), (0, ""))
            h = capsule.history(r)
            self.assertEqual([x["source"] for x in h], ["post-test"])
            self.assertIn("pytest", h[0]["command"])
            self.assertEqual(self._hook(r, "pytest", tool="Read").returncode, 0)   # a different tool is ignored
            self.assertEqual(len(capsule.history(r)), 1)
            self.assertEqual(self._hook(r, "pytest", tool="Bash").returncode, 0)
            p = subprocess.run([sys.executable, "-m", "agentvow.cli", "post-test-hook"], input="not json", capture_output=True, text=True, timeout=60)
            self.assertEqual((p.returncode, p.stdout), (0, ""))   # garbage input never errors

    def test_timing_says_what_happened_after_the_last_test_run(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._setup(d)
            self.assertEqual(capsule.timing(r, None)["kind"], "stop_only")
            self._hook(r, ".venv/bin/python -m pytest -q")
            (r / "tests" / "test_a.py").write_text("import lib\n\ndef test_f():\n    assert True\n")   # edit AFTER the last test run
            t = capsule.timing(r, None)
            self.assertEqual(t["kind"], "edited_after", t)
            self.assertIn("tests/test_a.py", t["edited"])
            self.assertIn("1 file(s) were edited after it", t["text"])
            (r / "tests" / "test_a.py").write_text("import lib\n\ndef test_f():\n    assert lib.f() in (1, 2)\n")   # back to the tested content
            self.assertEqual(capsule.timing(r, None)["kind"], "same_state")
            self._hook(r, "pytest -q")
            self.assertEqual(capsule.timing(r, None)["kind"], "same_state")

    def test_a_stop_time_capsule_only_is_reported_as_such(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._setup(d)
            rec, _ = capsule.capture(r)   # source "stop"
            t = capsule.timing(r, rec)
            self.assertEqual(t["kind"], "stop_only")
            self.assertIn("not at its last test run", t["text"])
