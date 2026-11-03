"""The reusable queue workflow (.github/workflows/queue.yml): static checks that it stays read-only and runs no pull-request code."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
try:
    import yaml
except ImportError:
    yaml = None
WF = ROOT / ".github" / "workflows" / "queue.yml"


@unittest.skipIf(yaml is None, "PyYAML not installed")
class QueueWorkflow(unittest.TestCase):
    def setUp(self):
        self.text = WF.read_text()
        self.doc = yaml.safe_load(self.text)
        self.job = self.doc["jobs"]["queue"]

    def test_it_is_read_only_and_holds_no_oidc_permission(self):
        for perms in (self.doc["permissions"], self.job["permissions"]):
            self.assertEqual(perms, {"contents": "read", "pull-requests": "read", "actions": "read"})
        self.assertNotIn("id-token", self.text.replace("# ", "").split("permissions:", 1)[1])

    def test_it_checks_out_nothing_and_runs_no_pull_request_code(self):
        self.assertFalse(any("checkout" in s.get("uses", "") for s in self.job["steps"]))
        self.assertNotIn("pull_request", " ".join(str(s.get("env", "")) for s in self.job["steps"]))

    def test_it_runs_only_on_schedule_or_manual_dispatch(self):
        guard = next(s for s in self.job["steps"] if s.get("name") == "Check the inputs")
        self.assertIn("schedule|workflow_dispatch", guard["run"])

    def test_inputs_reach_shell_only_through_environment_variables(self):
        for s in self.job["steps"]:
            self.assertNotRegex(s.get("run", ""), r"\$\{\{")

    def test_actions_are_pinned_by_sha_and_agentvow_comes_from_pypi_at_an_exact_version(self):
        for s in self.job["steps"]:
            if "uses" in s:
                self.assertRegex(s["uses"], r"@[0-9a-f]{40}$")
        self.assertIn('pip install --quiet "agentvow==$VERSION"', self.text)

    def test_every_python_runs_isolated_from_the_runner_temp_directory(self):
        for s in self.job["steps"]:
            if "python" in s.get("run", ""):
                self.assertEqual(s.get("working-directory"), "${{ runner.temp }}")
                for line in s["run"].splitlines():
                    if re.search(r"(^|\s)python\s", line):
                        self.assertIn("python -I", line)

    def test_a_missing_policy_means_the_default_but_any_other_read_failure_fails(self):
        run = next(s for s in self.job["steps"] if s.get("id") == "rank")["run"]
        self.assertIn('[ "$code" != "404" ]', run)
        self.assertIn("not falling back", run)
        self.assertIn("ref=$DEFAULT_BRANCH", run)

    def test_fail_on_defaults_to_never_and_only_two_values_are_accepted(self):
        self.assertEqual(self.doc[True]["workflow_call"]["inputs"]["fail-on"]["default"], "never")
        guard = next(s for s in self.job["steps"] if s.get("name") == "Check the inputs")["run"]
        self.assertIn("never|needs_person", guard)


if __name__ == "__main__":
    unittest.main()
