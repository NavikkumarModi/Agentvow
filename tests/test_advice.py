import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agentvow import advice, pack  # noqa: E402


def ctx(name, result, summary="", counts=None):
    return {"name": name, "basis": "x", "available": True, "result": result, "counts": counts or {}, "summary": summary}


NATIVE, CAP = "project-native setup", "captured environment"


class Advice(unittest.TestCase):
    def test_pass_has_no_next_step(self):
        self.assertIsNone(advice.step(ctx(NATIVE, "pass")))

    def test_missing_dependency_names_the_package_and_the_context(self):
        s = "missing dependency in Agentvow's environment: uvicorn, numpy (the repository's own files do not provide it)"
        n = advice.step(ctx(NATIVE, "inconclusive", s), other=ctx(CAP, "pass"))
        self.assertEqual(n["kind"], "missing_dependency")
        self.assertIn("uvicorn, numpy", n["text"])
        self.assertIn("repository's own files", n["text"])
        self.assertIn("other context reproduced", n["text"])
        self.assertIn("likely difference", n["text"])   # not stated as certain
        c = advice.step(ctx(CAP, "inconclusive", s))
        self.assertIn("captured packages do not include uvicorn, numpy", c["text"])
        self.assertIn("agentvow capture", c["text"])
        r = advice.step(ctx("the agent's declared recipe", "inconclusive", s))
        self.assertIn("declared recipe did not provide", r["text"])

    def test_own_package_is_a_layout_problem_not_an_install_problem(self):
        n = advice.step(ctx(CAP, "inconclusive", "missing dependency in Agentvow's environment: localstack (x)"), own="localstack")
        self.assertIn("project's own package", n["text"])
        self.assertNotIn("agentvow capture", n["text"])

    def test_credential_skip(self):
        n = advice.step(ctx(NATIVE, "inconclusive", "exit 1; Skipped: GOOGLE_API_KEY environment variable not set"))
        self.assertEqual(n["kind"], "credential")
        self.assertIn("GOOGLE_API_KEY", n["text"])
        self.assertIn("never passes secrets", n["text"])

    def test_environment_not_built_by_guard(self):
        for why, key in (("environment too heavy", "size limit"), ("disk low", "disk space"), ("timeout", "time limit"), ("shadowing", "project's own name")):
            n = advice.step(ctx(NATIVE, "not built", f"the environment could not be built ({why})"))
            self.assertIn(key, n["text"], why)
            self.assertIn("nothing about the agent's claim", n["text"])

    def test_no_tests_and_timeout_and_failure(self):
        self.assertEqual(advice.step(ctx(NATIVE, "inconclusive", "exit 5; no tests ran in 0.01s", {"passed": 0, "failed": 0, "errors": 0}))["kind"], "no_tests")
        n = advice.step(ctx(NATIVE, "inconclusive", "timeout after 600s"))
        self.assertEqual(n["kind"], "test_timeout")
        self.assertIn("--test-timeout", n["text"])
        f = advice.step(ctx(NATIVE, "fail", "exit 1; 3 failed, 94 passed", {"passed": 94, "failed": 3, "errors": 0}))
        self.assertEqual(f["kind"], "test_failure")
        self.assertIn("3 failed", f["text"])

    def test_no_result_recorded(self):
        n = advice.step(ctx(NATIVE, "unknown", ""))
        self.assertIn("no detail recorded", n["text"])

    def test_pack_renders_next_steps_in_all_three_formats(self):
        nxt = advice.next_steps([ctx(CAP, "pass"), ctx(NATIVE, "inconclusive", "missing dependency in Agentvow's environment: six (x)")])
        self.assertEqual(len(nxt), 1)
        p = {"version": 1, "manifest": None, "timing": None, "receipt": {"commit": "abc", "dirty": False, "base": "main", "command": "python -m pytest -q", "replay_python": "3.13", "created": "t", "valid_for": "x"},
             "contexts": [ctx(CAP, "pass", counts={"passed": 1, "failed": 0}), dict(ctx(NATIVE, "inconclusive", "missing dependency: six"), counts={})],
             "reproducibility": {"code": "captured_only", "text": "reading", "next_steps": nxt}, "coverage": {"available": False, "reason": "n/a"}, "limits": "l"}
        txt = "\n".join(pack.render_text(p))
        self.assertIn("Next step (project-native setup)", txt)
        self.assertIn("six", txt)
        md = "\n".join(pack.render_markdown(p, lambda x, n=None: str(x)))
        self.assertIn("Next step (project-native setup)", md)
        self.assertIn("Next step", pack.render_html(p, lambda x: str(x)))


if __name__ == "__main__":
    unittest.main()


class ReplayState(unittest.TestCase):
    def test_untracked_files_and_symlinks_are_reported(self):
        import os, subprocess, tempfile
        d = Path(tempfile.mkdtemp())
        run = lambda *a: subprocess.run(["git", "-C", str(d), *a], capture_output=True, text=True, check=True)
        run("init", "-q"); run("config", "user.email", "t@t"); run("config", "user.name", "t")
        (d / "a.py").write_text("X = 1\n"); run("add", "-A"); run("commit", "-qm", "one")
        (d / "a.py").write_text("X = 2\n")
        (d / "helper.py").write_text("H = 1\n")
        (d / "link.py").symlink_to("/etc/hosts")
        (d / ".gitignore").write_text("secret.json\n"); (d / "secret.json").write_text("{}")
        st = pack.replay_state(d)
        self.assertEqual(st["n_untracked"], 3)   # helper.py, link.py, .gitignore (secret.json is ignored, not included)
        self.assertIn("helper.py", st["untracked"])
        self.assertEqual(st["symlinks_skipped"], ["link.py"])
        line = pack.state_line(st)
        self.assertIn("uncommitted change(s)", line)
        self.assertIn("helper.py", line)
        self.assertIn("never follows a link", line)
        self.assertIn("Git-ignored files are not included", line)
        self.assertNotIn("secret.json", line)

    def test_clean_tree_says_nothing(self):
        self.assertEqual(pack.state_line({"uncommitted": 0, "n_symlinks": 0, "n_untracked": 0, "untracked": [], "symlinks_skipped": []}), "")
        self.assertEqual(pack.state_line(None), "")


class IgnoredCaution(unittest.TestCase):
    def test_failure_with_ignored_files_in_the_tree_carries_a_caution(self):
        f = ctx("project-native setup", "fail", "exit 1; 1 failed", {"passed": 0, "failed": 1, "errors": 0})
        plain = advice.step(f)
        self.assertNotIn("git-ignored", plain["text"])
        cautious = advice.step(f, ignored=["fixtures/generated.json", "local.cfg"])
        self.assertIn("git-ignored files exist", cautious["text"])
        self.assertIn("fixtures/generated.json", cautious["text"])


class Honesty(unittest.TestCase):
    def test_a_failed_install_step_is_named_next_to_the_missing_package(self):
        c = dict(ctx("project-native setup", "inconclusive", "missing dependency in Agentvow's environment: six (x)"), setup_notes=["setup `pip install -r requirements.txt` failed: no matching distribution"])
        t = advice.step(c)["text"]
        self.assertIn("an install step failed", t)
        self.assertIn("An install step did fail here", t)
        self.assertIn("requirements.txt", t)

    def test_failure_text_does_not_claim_it_is_usually_a_result_and_handles_zero_count(self):
        t = advice.step(ctx("project-native setup", "fail", "exit 1", {"passed": 3, "failed": 0, "errors": 0}))["text"]
        self.assertNotIn("0 failed", t)
        self.assertNotIn("usually", t)
        self.assertIn("did not pass", t)
        self.assertIn("can also fail for lack of files or settings", t)

    def test_pack_names_install_inputs_the_change_touched_and_ci_env(self):
        c = dict(ctx("project-native setup", "pass", counts={"passed": 1, "failed": 0}), steps=["pip install ."], env_names=["FOO"], inputs_changed=[".github/workflows/ci.yml"], setup_notes=["x left out"])
        p = {"version": 1, "manifest": None, "timing": None, "receipt": {"commit": "abc", "dirty": False, "base": "main", "command": "c", "replay_python": "3", "created": "t", "valid_for": "v"},
             "contexts": [c], "reproducibility": {"code": "single", "text": "r", "next_steps": []}, "coverage": {"available": False, "reason": "n/a"}, "limits": "l"}
        txt = "\n".join(pack.render_text(p))
        self.assertIn("environment values set from CI: FOO", txt)
        self.assertIn("were changed in this change: .github/workflows/ci.yml", txt)
        self.assertIn("note: x left out", txt)
