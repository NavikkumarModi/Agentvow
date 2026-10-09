"""Regression tests for the 2026-10-07 adversarial review of the integration surface (docs/research/RISKS.md)."""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "examples"))
os.environ.setdefault("AGENTMIRROR_HOME", tempfile.mkdtemp(prefix="am_home_"))
from agentmirror import adapters, ci, claims, envsetup, reality, report, runner  # noqa: E402
from make_demo import build, git  # noqa: E402


def passfail(shell):
    """A test command that prints '1 passed' if `shell` succeeds, else '1 failed'."""
    return ["sh", "-c", f"( {shell} ) >/dev/null 2>&1 && echo '1 passed in 0.01s' || echo '1 failed in 0.01s'"]


class G1_Isolation(unittest.TestCase):
    def test_project_imported_from_outside_the_worktree_is_detected(self):
        with tempfile.TemporaryDirectory() as t:
            other, repo = Path(t) / "other", build(Path(t) / "r")
            (other / "pkgz").mkdir(parents=True)
            (other / "pkgz" / "__init__.py").write_text("X = 'head'\n")
            (repo / "src" / "pkgz").mkdir(parents=True)       # src layout: cwd does not shadow an installed copy
            (repo / "src" / "pkgz" / "__init__.py").write_text("X = 'base'\n")
            env = {"PATH": os.environ["PATH"], "PYTHONPATH": str(other)}   # as if an editable install pointed at another checkout
            self.assertIn("outside this worktree", runner.isolation_problem(repo, [sys.executable], env) or "")
            env["PYTHONPATH"] = f"{repo / 'src'}:{repo}"
            self.assertIsNone(runner.isolation_problem(repo, [sys.executable], env))

    def test_runner_puts_the_worktree_first_on_pythonpath(self):
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            rec = runner.run_tests(repo, ["sh", "-c", "echo $PYTHONPATH | grep -q \"^%s/src:%s\" && echo '1 passed in 0.01s' || echo '1 failed in 0.01s'" % (repo.resolve(), repo.resolve())], write=False)
            self.assertEqual(rec["counts"].get("passed"), 1)


class G2_SandboxCannotForgeEvidence(unittest.TestCase):
    def test_signing_key_cannot_be_read_from_inside_the_sandbox(self):
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            key = Path(os.environ["AGENTMIRROR_HOME"]) / "key"
            reality._key()   # make sure it exists
            self.assertTrue(key.exists())
            rec = runner.run_tests(repo, passfail(f"cat {key}"), write=False)
            self.assertEqual(rec["counts"].get("failed"), 1, "the sandboxed process could read the signing key")

    def test_cannot_write_outside_the_worktree_even_into_temp(self):
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            outside = Path(t) / "forged_evidence.json"
            rec = runner.run_tests(repo, passfail(f"echo forged > {outside}"), write=False)
            self.assertFalse(outside.exists())
            self.assertEqual(rec["counts"].get("failed"), 1)

    def test_credential_directories_are_not_readable(self):
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            rec = runner.run_tests(repo, passfail("ls ~/.ssh"), write=False)   # ~ is the throwaway HOME, so use the real path
            real = Path.home() / ".ssh"
            if real.exists():
                rec = runner.run_tests(repo, passfail(f"ls {real}"), write=False)
                self.assertEqual(rec["counts"].get("failed"), 1)


class G3_NoSymlinkWrites(unittest.TestCase):
    def test_safe_write_refuses_symlinked_directory_and_file(self):
        with tempfile.TemporaryDirectory() as t:
            repo, victim_dir = build(Path(t) / "r"), Path(t) / "victim"
            victim_dir.mkdir()
            (repo / ".agentmirror").mkdir(exist_ok=True)
            os.symlink(victim_dir, repo / ".agentmirror" / "last")
            with self.assertRaises(OSError):
                reality.safe_write(repo, Path(".agentmirror") / "last" / "report.html", "x")
            self.assertEqual(list(victim_dir.iterdir()), [])
            (repo / ".agentmirror" / "last").unlink()
            (repo / ".agentmirror" / "last").mkdir()
            victim = Path(t) / "victim.txt"
            victim.write_text("keep")
            os.symlink(victim, repo / ".agentmirror" / "last" / "report.html")
            with self.assertRaises(OSError):
                reality.safe_write(repo, Path(".agentmirror") / "last" / "report.html", "x")
            self.assertEqual(victim.read_text(), "keep")

    def test_hook_does_not_overwrite_a_file_through_a_planted_symlink(self):
        with tempfile.TemporaryDirectory() as t:
            repo, victim = build(Path(t) / "r"), Path(t) / "victim.txt"
            victim.write_text("keep")
            last = repo / ".agentmirror" / "last"
            last.mkdir(parents=True)
            os.symlink(victim, last / "report.html")
            r = subprocess.run([sys.executable, "-m", "agentmirror", "check", "--hook"], capture_output=True, text=True, cwd=ROOT,
                               input=json.dumps({"cwd": str(repo), "last_assistant_message": "No downstream impact."}), env={**os.environ})
            self.assertEqual(victim.read_text(), "keep")
            self.assertEqual(r.returncode, 0)   # still informs, never blocks


class G4_NoCodeExecutionFromGit(unittest.TestCase):
    def test_hooks_and_fsmonitor_in_an_untrusted_repo_do_not_run(self):
        with tempfile.TemporaryDirectory() as t:
            repo, marker = build(Path(t) / "r"), Path(t) / "marker"
            hook = repo / ".git" / "hooks" / "post-checkout"
            hook.write_text(f"#!/bin/sh\ntouch {marker}.hook\n")
            hook.chmod(0o755)
            fs = repo / "fsm.sh"
            fs.write_text(f"#!/bin/sh\ntouch {marker}.fsmonitor\nexit 0\n")
            fs.chmod(0o755)
            subprocess.run(["git", "-C", str(repo), "config", "core.fsmonitor", str(fs)], check=True)
            reality.snapshot(repo)
            reality.changed_files(repo, "HEAD~1")
            subprocess.run(["git", *reality.GIT_SAFE, "-C", str(repo), "worktree", "add", "--detach", str(Path(t) / "wt"), "HEAD"], capture_output=True)
            self.assertFalse(Path(f"{marker}.hook").exists(), "post-checkout hook executed")
            self.assertFalse(Path(f"{marker}.fsmonitor").exists(), "fsmonitor executed")


class G7_RenamedModuleIsNotAMissingDependency(unittest.TestCase):
    def test_module_that_existed_at_base_is_a_regression_signal(self):
        with tempfile.TemporaryDirectory() as t:
            head, base = build(Path(t) / "h"), build(Path(t) / "b")
            (base / "core.py").write_text("X = 1\n")                 # existed at base, renamed away at head
            out = "ERROR tests/a.py\\nModuleNotFoundError: No module named 'core'"
            rec = runner.run_tests(head, ["sh", "-c", f"printf '{out}\\n'; exit 2"], write=False,
                                   baseline_failed=[], baseline_passed=["tests/a.py::t1"], base_repo=base)
            self.assertNotIn("missing dependency", rec["summary"])
            self.assertTrue(rec["counts"].get("regressions"))

    def test_genuinely_third_party_module_is_still_an_environment_limit(self):
        with tempfile.TemporaryDirectory() as t:
            head, base = build(Path(t) / "h"), build(Path(t) / "b")
            rec = runner.run_tests(head, ["sh", "-c", "echo \"ModuleNotFoundError: No module named 'requests'\"; exit 2"], write=False,
                                   baseline_failed=[], baseline_passed=["tests/a.py::t1"], base_repo=base)
            self.assertIn("missing dependency", rec["summary"])


class G9_Platform(unittest.TestCase):
    def test_refuses_to_run_repository_code_without_the_sandbox(self):
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            with mock.patch("agentmirror.runner.shutil.which", return_value=None):
                with self.assertRaises(RuntimeError) as cm:
                    runner.run_tests(repo, ["true"], write=False)
            self.assertIn("unsandboxed", str(cm.exception))


class G10_CI(unittest.TestCase):
    def test_ci_authority_is_not_claimed_as_independent_of_the_change(self):
        ev = ci.ci_evidence(Path("."), reality.Snapshot("abc", False), slug="o/r",
                            fetch=lambda p: {"check_runs": [{"name": "tests", "status": "completed", "conclusion": "success"}], "total_count": 1})
        self.assertEqual(ev[0].independence["authority"], "unknown")


class G12_G13_UntrustedText(unittest.TestCase):
    def test_markdown_has_no_mentions_emoji_shortcodes_or_invisible_characters(self):
        md = report._md("ping @octocat :rotating_light: a​b ‮gnp.exe")
        self.assertNotIn("@octocat", md)
        self.assertNotIn("​", md)
        self.assertNotIn("‮", md)
        self.assertIn("\\:rotating", md)

    def test_claim_extraction_is_bounded_on_adversarial_text(self):
        text = "1," * 40000
        t0 = time.time()
        claims.extract(text)
        self.assertLess(time.time() - t0, 3.0)

    def test_deeply_nested_json_does_not_crash_the_transcript_reader(self):
        raw = "[" * 100000 + "]" * 100000
        adapters.final_message_from_text(raw)   # must not raise RecursionError


class EnvSetup(unittest.TestCase):
    def test_project_is_copied_not_installed_in_place(self):
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            dest = Path(t) / "copy"
            self.assertTrue(envsetup._copy_project(repo, dest))
            self.assertTrue((dest / "payments" / "retry.py").exists())
            self.assertFalse((dest / ".git").exists())

    def test_project_name_is_read_for_uninstall(self):
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "pyproject.toml").write_text('[project]\nname = "my-proj"\n')
            self.assertEqual(envsetup._project_name(Path(t)), "my-proj")


class Seal(unittest.TestCase):
    def test_seal_is_over_both_files(self):
        a = reality.seal(b"page", b"dec")
        self.assertEqual(a, reality.seal(b"page", b"dec"))
        self.assertNotEqual(a, reality.seal(b"page2", b"dec"))
        self.assertNotEqual(a, reality.seal(b"page", b"dec2"))


if __name__ == "__main__":
    unittest.main()


class TimeoutKillsTheWholeGroup(unittest.TestCase):
    def test_background_daemons_do_not_outlive_a_timed_out_run(self):
        marker = "sleep 31337"
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            rec = runner.run_tests(repo, ["sh", "-c", f"{marker} & {marker}"], timeout=2, write=False)
            self.assertEqual(rec["result"], "inconclusive")
            self.assertIn("timeout", rec["summary"])
        time.sleep(0.5)
        left = subprocess.run(["pgrep", "-f", marker], capture_output=True, text=True).stdout.strip()
        self.assertEqual(left, "", f"leaked process(es): {left}")


if __name__ == "__main__":
    unittest.main()
