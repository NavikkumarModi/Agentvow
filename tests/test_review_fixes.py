"""Regression tests for the 2026-10-06 adversarial review findings (docs/research/RISKS.md)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "examples"))
os.environ.setdefault("AGENTVOW_HOME", tempfile.mkdtemp(prefix="am_home_"))

from agentvow import api_diff, ci, claims, decision, reality, runner  # noqa: E402
from agentvow.reality import Evidence, Snapshot  # noqa: E402
from make_demo import build, git  # noqa: E402

IND = {"framing": "separate", "evidence": "separate", "mechanism": "separate", "authority": "unknown"}


def ev(counts, result="pass"):
    return Evidence("e", "prior_verification", "r", "abcdef123456", "h", "VALID", IND, "e.json", f"{result}: x", counts=counts)


class Evidence_(unittest.TestCase):
    def test_forged_unsigned_evidence_is_not_independent(self):
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            head = git(repo, "rev-parse", "HEAD")
            (repo / ".agentvow/evidence/forged.json").write_text(json.dumps(
                {"commit": head, "result": "pass", "counts": {"passed": 5}, "summary": "ok", "produced_by": "ci"}))
            e = next(x for x in reality.load_prior_evidence(repo, reality.snapshot(repo)) if x.evidence_id == "forged")
            self.assertEqual(e.independence["mechanism"], "same")

    def test_signed_record_is_trusted_and_tampering_breaks_it(self):
        rec = reality.sign_record({"commit": "a", "result": "pass", "counts": {"passed": 1}})
        self.assertTrue(reality.verify_record(rec))
        rec["counts"]["passed"] = 99
        self.assertFalse(reality.verify_record(rec))

    def test_clean_head_rejects_evidence_recorded_on_a_dirty_tree(self):
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            head = git(repo, "rev-parse", "HEAD")
            (repo / ".agentvow/evidence/d.json").write_text(json.dumps({"commit": head, "tree": "deadbeef", "result": "pass"}))
            e = next(x for x in reality.load_prior_evidence(repo, reality.snapshot(repo)) if x.evidence_id == "d")
            self.assertEqual(e.freshness, "STALE")


class TestsDisappearing(unittest.TestCase):
    snap = Snapshot("abcdef123456", False)

    def v(self, counts):
        return decision._tests(claims.Claim(claims.TESTS_PASS, "All tests pass", None), [ev(counts)], self.snap).verdict

    def test_all_skipped_is_not_support(self):
        self.assertEqual(self.v({"passed": 0, "failed": 0, "skipped": 2}), "UNKNOWN")

    def test_deleted_tests_are_not_support(self):
        self.assertEqual(self.v({"passed": 1, "failed": 0, "skipped": 0, "regressions": 0, "uncomparable": 0, "missing": 3}), "UNKNOWN")

    def test_intact_suite_is_support(self):
        self.assertEqual(self.v({"passed": 4, "failed": 0, "skipped": 0, "regressions": 0, "uncomparable": 0, "missing": 0}),
                         "SUPPORTED_BY_PRIOR_EVIDENCE")

    def test_runner_counts_missing_tests(self):
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            rec = runner.run_tests(repo, ["sh", "-c", "printf 'PASSED tests/a.py::t1\\n= 1 passed in 0.1s =\\n'"], write=False,
                                   baseline_failed=[], baseline_passed=["tests/a.py::t1", "tests/a.py::t2"])
            self.assertEqual(rec["counts"]["missing"], 1)

    def test_lookalike_ran_line_cannot_forge_counts(self):
        out = "Ran 999 tests in 0.1s\nFAIL: test_x (m.C.test_x)\nRan 2 tests in 0.2s\nFAILED (failures=1)"
        self.assertEqual(runner.parse_counts(out)["passed"], 1)

    def test_subtest_counts_never_negative(self):
        out = "Ran 1 test in 0.1s\nFAILED (failures=3)"
        self.assertEqual(runner.parse_counts(out)["passed"], 0)


class CIFixes(unittest.TestCase):
    snap = Snapshot("abcdef123456", False)

    def evid(self, runs, total=None):
        return ci.ci_evidence(Path("."), self.snap, fetch=lambda p: {"check_runs": runs, "total_count": total if total is not None else len(runs)}, slug="o/r")

    def test_red_ci_beats_a_local_pass(self):
        red = self.evid([{"name": "tests", "status": "completed", "conclusion": "failure"}])
        local = ev({"passed": 5, "failed": 0, "skipped": 0, "regressions": 0, "uncomparable": 0, "missing": 0})
        f = decision._tests(claims.Claim(claims.TESTS_PASS, "All tests pass", None), red + [local], self.snap)
        self.assertEqual(f.verdict, "CONTRADICTED")

    def test_skipped_and_neutral_jobs_are_not_a_pass(self):
        self.assertEqual(self.evid([{"name": "tests", "status": "completed", "conclusion": "skipped"},
                                    {"name": "unit", "status": "completed", "conclusion": "neutral"}]), [])

    def test_truncated_listing_gives_no_evidence(self):
        self.assertEqual(self.evid([{"name": "tests", "status": "completed", "conclusion": "success"}], total=150), [])


class DecisionFixes(unittest.TestCase):
    def test_negated_statement_is_not_a_success_claim(self):
        got = [(c.kind) for c in claims.extract("I could not confirm all tests pass.")]
        self.assertEqual(got, ["unchecked"])

    def test_deleted_module_blocks_no_impact_claim(self):
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            git(repo, "rm", "-q", "payments/retry.py")
            git(repo, "commit", "-qm", "remove")
            d = decision.check(repo, "HEAD~1", "No downstream impact.")
            f = next(x for x in d.findings if x.kind == claims.NO_IMPACT)
            self.assertEqual(f.verdict, "UNKNOWN")

    def test_default_base_prefers_head_for_dirty_tree(self):
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            self.assertEqual(reality.default_base(repo, True)[0], "HEAD")
            self.assertEqual(reality.default_base(repo, False)[0], "HEAD~1")

    def test_src_layout_imports_resolve(self):
        with tempfile.TemporaryDirectory() as t:
            repo = Path(t)
            (repo / "src/pkg").mkdir(parents=True)
            (repo / "src/pkg/__init__.py").write_text("")
            (repo / "src/pkg/core.py").write_text("X = 1\n")
            (repo / "src/pkg/user.py").write_text("from pkg.core import X\n")
            self.assertIn("src/pkg/user.py", reality.build_graph(repo).dependents("src/pkg/core.py"))

    def test_bare_import_module_is_a_gap(self):
        with tempfile.TemporaryDirectory() as t:
            repo = Path(t)
            (repo / "a.py").write_text("from importlib import import_module\nimport_module('b')\n")
            self.assertTrue(any("dynamic import" in g for g in reality.build_graph(repo).gaps))


class APIDiffFixes(unittest.TestCase):
    def b(self, old, new, init=False):
        return api_diff.breaking(api_diff.public_api(old, init), api_diff.public_api(new, init))

    def test_optional_to_required_param(self):
        self.assertTrue(self.b("def f(a, b=1): pass\n", "def f(a, b): pass\n"))

    def test_annotated_constant_removed(self):
        self.assertTrue(self.b("X: int = 1\n", "Y = 1\n"))

    def test_init_reexport_removed(self):
        self.assertTrue(self.b("from .core import Thing\n", "", init=True))

    def test_compatible_changes_pass(self):
        self.assertEqual(self.b("def f(a): pass\n", "def f(a, b=2): pass\n"), [])


class ExitCodes(unittest.TestCase):
    def run_cli(self, text, repo):
        return subprocess.run([sys.executable, "-m", "agentvow", "check", "--repo", str(repo)], input=text, capture_output=True,
                              text=True, cwd=ROOT, env={**os.environ, "AGENTVOW_HOME": os.environ["AGENTVOW_HOME"]}).returncode

    def test_insufficient_evidence_is_nonzero(self):
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            self.assertEqual(self.run_cli("Refactored things.", repo), 2)

    def test_review_required_is_one(self):
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            self.assertEqual(self.run_cli("No downstream impact.", repo), 1)

    def test_missing_repo_is_insufficient_not_ok(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(self.run_cli("x", Path(t) / "does_not_exist"), 2)

    def test_tool_crash_is_three_not_a_verdict(self):
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            r = subprocess.run([sys.executable, "-m", "agentvow", "check", "--repo", str(repo), "--session", str(Path(t) / "nope.jsonl")],
                               capture_output=True, text=True, cwd=ROOT, env={**os.environ})
            self.assertEqual(r.returncode, 3)


if __name__ == "__main__":
    unittest.main()


class Productisation(unittest.TestCase):
    def test_modified_existing_tests_downgrade_support(self):
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            (repo / "tests/test_retry.py").write_text("def test_retry():\n    assert True\n")  # trivialised
            git(repo, "add", "-A"); git(repo, "commit", "-qm", "edit test")
            head = git(repo, "rev-parse", "HEAD")
            (repo / ".agentvow/evidence").mkdir(parents=True, exist_ok=True)
            (repo / ".agentvow/evidence/run.json").write_text(json.dumps(reality.sign_record({
                "commit": head, "tree": "", "result": "pass", "produced_by": "agentvow-runner", "summary": "ok",
                "counts": {"passed": 2, "failed": 0, "skipped": 0, "regressions": 0, "uncomparable": 0, "missing": 0}})))
            d = decision.check(repo, "HEAD~1", "All 2 tests pass.")
            f = next(x for x in d.findings if x.kind == claims.TESTS_PASS)
            self.assertEqual(f.verdict, "NOT_CONTRADICTED")
            self.assertIn("modified existing test", f.why)

    def test_unexamined_statements_are_counted(self):
        text = "All 3 tests pass. I also rewrote the billing module completely. The deployment pipeline was updated as well."
        self.assertEqual(claims.count_unexamined(text, claims.extract(text)), 2)

    def test_hook_never_blocks_and_reports(self):
        with tempfile.TemporaryDirectory() as t:
            repo = build(Path(t) / "r")
            sess = Path(t) / "s.jsonl"
            sess.write_text(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "No downstream impact."}]}}))
            r = subprocess.run([sys.executable, "-m", "agentvow", "check", "--hook"], capture_output=True, text=True, cwd=ROOT,
                               input=json.dumps({"transcript_path": str(sess), "cwd": str(repo)}), env={**os.environ})
            self.assertEqual(r.returncode, 0)
            self.assertIn("REVIEW REQUIRED", json.loads(r.stdout)["systemMessage"])

    def test_hook_ignores_non_repo_and_loop_guard(self):
        r = subprocess.run([sys.executable, "-m", "agentvow", "check", "--hook"], capture_output=True, text=True, cwd=ROOT,
                           input=json.dumps({"stop_hook_active": True}), env={**os.environ})
        self.assertEqual((r.returncode, r.stdout.strip()), (0, ""))


class EnvSetup(unittest.TestCase):
    def test_default_python_prefers_the_projects_own_venv(self):
        from agentvow import envsetup
        with tempfile.TemporaryDirectory() as t:
            repo = Path(t)
            self.assertEqual(envsetup.default_python(repo), sys.executable)
            (repo / ".venv/bin").mkdir(parents=True)
            (repo / ".venv/bin/python").write_text("")
            self.assertEqual(envsetup.default_python(repo), str(repo / ".venv/bin/python"))

    def test_extras_are_detected_from_pyproject(self):
        from agentvow import envsetup
        with tempfile.TemporaryDirectory() as t:
            repo = Path(t)
            (repo / "pyproject.toml").write_text('[project]\nname="x"\n[project.optional-dependencies]\ndev=["a"]\ndocs=["b"]\ntest=["c"]\n')
            self.assertEqual(envsetup.detect_extras(repo), ["test", "dev"])

    def test_low_disk_refuses_to_start(self):
        from agentvow import envsetup
        with tempfile.TemporaryDirectory() as t:
            py, notes, aborted = envsetup.build_env(Path(t), Path(t) / "v", Path(t) / "h", min_free=10**18)
            self.assertIsNone(py)
            self.assertEqual(aborted, "disk low")

    def test_size_watchdog_kills_a_runaway_install(self):
        from agentvow import envsetup
        with tempfile.TemporaryDirectory() as t:
            venv = Path(t) / "venv"
            (venv / "bin").mkdir(parents=True)
            # a fake 'pip' that grows the environment without bound
            (venv / "bin" / "pip").write_text("#!/bin/sh\nwhile true; do head -c 200000 /dev/zero >> \"$(dirname $0)/../big\"; sleep 0.2; done\n")
            (venv / "bin" / "pip").chmod(0o755)
            rc, why = envsetup._pip(venv, Path(t), Path(t) / "home", ["install", "x"], timeout=60, max_venv=1_000_000, min_free=0)
            self.assertEqual((rc, why), (125, "environment too heavy"))
            self.assertLess(envsetup.dir_size(venv), 50_000_000)


class DependencyGroups(unittest.TestCase):
    def test_pep735_test_groups_are_detected(self):
        from agentvow import envsetup
        with tempfile.TemporaryDirectory() as t:
            repo = Path(t)
            (repo / "pyproject.toml").write_text('[project]\nname="x"\n[dependency-groups]\ndocs=["a"]\ndev=["b"]\ntest=["c"]\n')
            self.assertEqual(envsetup.detect_groups(repo), ["test", "dev"])

    def test_no_groups_is_empty(self):
        from agentvow import envsetup
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(envsetup.detect_groups(Path(t)), [])
