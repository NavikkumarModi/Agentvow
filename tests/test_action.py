import re, unittest
from pathlib import Path

ACTION = (Path(__file__).resolve().parents[1] / "action.yml").read_text()


class ActionFile(unittest.TestCase):
    def test_run_tests_is_opt_in_and_warns_that_it_runs_pull_request_code(self):
        m = re.search(r"  run-tests:\n    description: \"(.*?)\"\n    required: false\n    default: \"(.*?)\"", ACTION, re.S)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(2), "false")
        self.assertIn("RUNS THE PULL REQUEST'S CODE", m.group(1))
        self.assertIn("never on pull_request_target", m.group(1))

    def test_sandbox_prerequisites_only_when_asked_and_on_linux(self):
        self.assertRegex(ACTION, r"if: \$\{\{ inputs\.run-tests == 'true' && runner\.os == 'Linux' \}\}\n\s+shell: bash\n\s+run: \|\n\s+sudo apt-get update -qq && sudo apt-get install -y -qq bubblewrap")

    def test_the_check_adds_the_pack_only_when_asked(self):
        self.assertIn('if [ "$RUN_TESTS" = "true" ]; then PACK="--evidence-pack --test-timeout ${TEST_TIMEOUT:-900}"; fi', ACTION)
        self.assertIn("$PACK", ACTION)

    def test_default_behaviour_is_unchanged_without_run_tests(self):
        # the original arguments are all still there
        for tok in ("--ci --ci-wait", "--html", "--markdown", "--transcript"):
            self.assertIn(tok, ACTION)

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
