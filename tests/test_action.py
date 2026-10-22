import re, unittest
from pathlib import Path

ACTION = (Path(__file__).resolve().parents[1] / "action.yml").read_text()


class ActionFile(unittest.TestCase):
    def test_run_tests_is_opt_in_and_warns_that_it_runs_pull_request_code(self):
        m = re.search(r"  run-tests:\n    description: \"(.*?)\"\n    required: false\n    default: \"(.*?)\"", ACTION, re.S)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(2), "false")
        self.assertIn("RUNS THE PULL REQUEST'S CODE", m.group(1))
        self.assertIn("refuses to run this on events other than pull_request", m.group(1))
        self.assertIn("evidence to weigh, not verification", m.group(1))

    def test_sandbox_prerequisites_only_when_asked_and_on_linux(self):
        self.assertIn("if: ${{ inputs.run-tests == 'true' && runner.os == 'Linux' && runner.environment == 'github-hosted' }}", ACTION)   # never on a self-hosted runner
        self.assertIn("sudo apt-get install -y -qq bubblewrap", ACTION)

    def test_the_check_adds_the_pack_only_when_asked(self):
        self.assertIn('if [ "$RUN_TESTS" = "true" ]; then PACK=(--evidence-pack --test-timeout "${TEST_TIMEOUT:-900}"); fi', ACTION)
        self.assertIn('"${PACK[@]}"', ACTION)   # an array, quoted: a timeout value cannot add arguments

    def test_default_behaviour_is_unchanged_without_run_tests(self):
        # the original arguments are all still there
        for tok in ("--ci --ci-wait", "--html", "--markdown", "--transcript"):
            self.assertIn(tok, ACTION)

    def _guard(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed")
        step = yaml.safe_load(ACTION)["runs"]["steps"][0]
        self.assertIn("Refuse to run", step["name"])
        return step

    def _run_guard(self, event, runner_env="github-hosted", fork="false", timeout="900"):
        import os, subprocess
        step = self._guard()
        env = {**os.environ, "EVENT": event, "RUNNER_ENV": runner_env, "IS_FORK": fork, "TEST_TIMEOUT": timeout}
        return subprocess.run(["bash", "-c", step["run"]], env=env, capture_output=True, text=True)

    def test_guard_allows_pull_request_push_and_dispatch(self):
        for ev in ("pull_request", "push", "workflow_dispatch"):
            self.assertEqual(self._run_guard(ev).returncode, 0, ev)

    def test_guard_refuses_pull_request_target_workflow_run_and_comment_events(self):
        for ev in ("pull_request_target", "workflow_run", "issue_comment", "pull_request_review"):
            r = self._run_guard(ev)
            self.assertEqual(r.returncode, 1, ev)
            self.assertIn("refused", r.stdout)

    def test_guard_refuses_fork_pull_requests_on_self_hosted_runners_only(self):
        self.assertEqual(self._run_guard("pull_request", "self-hosted", "true").returncode, 1)
        self.assertEqual(self._run_guard("pull_request", "self-hosted", "false").returncode, 0)
        self.assertEqual(self._run_guard("pull_request", "github-hosted", "true").returncode, 0)

    def test_guard_refuses_a_timeout_that_is_not_a_whole_number(self):
        for bad in ("900 --python /x", "", "9;0", "-1", "1.5"):
            self.assertEqual(self._run_guard("pull_request", timeout=bad).returncode, 1, repr(bad))
        self.assertEqual(self._run_guard("pull_request", timeout="1200").returncode, 0)

    def test_guard_only_runs_when_run_tests_is_true(self):
        self.assertIn("inputs.run-tests == 'true'", self._guard()["if"])

    def test_yaml_is_valid_when_pyyaml_is_available(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed")
        d = yaml.safe_load(ACTION)
        self.assertEqual(d["inputs"]["run-tests"]["default"], "false")
        self.assertEqual(d["inputs"]["test-timeout"]["default"], "900")


if __name__ == "__main__":
    unittest.main()
