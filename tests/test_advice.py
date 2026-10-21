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
        c = advice.step(ctx(CAP, "inconclusive", s))
        self.assertIn("captured packages do not include uvicorn, numpy", c["text"])
        self.assertIn("agentvow capture", c["text"])
        r = advice.step(ctx("the agent's declared recipe", "inconclusive", s))
        self.assertIn("declared recipe does not install", r["text"])

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
