"""The gate's configuration (test command, timeout, Agentvow version) is set by a workflow file the pull request can edit, and a verified receipt does not bind it (docs/research/RECEIPT_AUTH_DESIGN.md, section 11).
The receipt now records it, and the policy can ask a person when it is not the project's own."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from agentvow import policy  # noqa: E402
from test_pilot_report import rcpt  # noqa: E402


def with_inputs(cmd="", timeout=900, version="0.5.2"):
    r = rcpt(1)
    r["gate_inputs"] = {"test_command": cmd, "test_timeout": timeout}
    r["tool_version"] = version
    return r


def rules(r, pol=None, acks=None):
    ev = policy.evaluate(r, pol, acks)
    return [(x["rule"], x["outcome"]) for x in ev["reasons"] if x["outcome"] != "allow"], ev


class Recording(unittest.TestCase):
    def test_nothing_is_recorded_unless_the_workflow_says_so(self):
        self.assertIsNone(policy.gate_inputs_from_env({}))
        self.assertIsNone(policy.gate_inputs_from_env({"AGENTVOW_GATE_TEST_TIMEOUT": "900"}))

    def test_an_empty_command_is_recorded_as_the_default(self):
        self.assertEqual(policy.gate_inputs_from_env({"AGENTVOW_GATE_TEST_COMMAND": "", "AGENTVOW_GATE_TEST_TIMEOUT": "900"}), {"test_command": "", "test_timeout": 900})

    def test_the_command_is_capped_and_made_printable_and_a_bad_timeout_is_dropped(self):
        g = policy.gate_inputs_from_env({"AGENTVOW_GATE_TEST_COMMAND": "x" * 500 + "\n\x00é", "AGENTVOW_GATE_TEST_TIMEOUT": "9; rm -rf"})
        self.assertEqual(len(g["test_command"]), policy.MAX_COMMAND); self.assertIsNone(g["test_timeout"])
        g = policy.gate_inputs_from_env({"AGENTVOW_GATE_TEST_COMMAND": "a\nb\x00é"})
        self.assertEqual(g["test_command"], "a?b??")

    def test_the_receipt_carries_the_inputs_only_when_given_and_validates(self):
        dec = {"commit": "a" * 40, "findings": []}
        self.assertNotIn("gate_inputs", policy.build_receipt(dec, "o/n", "b" * 40))
        r = policy.build_receipt(dec, "o/n", "b" * 40, gate_inputs={"test_command": "make test", "test_timeout": 60})
        self.assertEqual(r["gate_inputs"], {"test_command": "make test", "test_timeout": 60}); self.assertIsNone(policy.validate_receipt(r))

    def test_malformed_inputs_make_the_receipt_invalid(self):
        for bad in ({"test_command": "x" * 201}, {"test_command": 5}, {"test_command": "", "extra": 1}, "x", {"test_command": "", "test_timeout": -1}, {"test_command": "", "test_timeout": "9"}):
            r = rcpt(1); r["gate_inputs"] = bad
            self.assertIsNotNone(policy.validate_receipt(r), bad)


class Rules(unittest.TestCase):
    def test_by_default_nothing_changes(self):
        self.assertEqual(rules(with_inputs("{py} -c pass"))[0], [])
        self.assertEqual(rules(rcpt(1))[0], [])

    def test_a_command_the_policy_does_not_list_asks_a_person(self):
        got, ev = rules(with_inputs("{py} -c pass"), {"allowed_test_commands": ["{py} -m pytest -q"]})
        self.assertEqual(got, [("gate_inputs", "needs_acknowledgement")]); self.assertEqual(ev["decision"], "needs_acknowledgement")
        self.assertIn("{py} -c pass", ev["reasons"][-1]["text"])

    def test_the_default_command_and_listed_commands_pass(self):
        pol = {"allowed_test_commands": ["{py} -m pytest -q"]}
        self.assertEqual(rules(with_inputs(""), pol)[0], [])
        self.assertEqual(rules(with_inputs("{py} -m pytest -q"), pol)[0], [])
        self.assertEqual(rules(with_inputs("anything"), {"allowed_test_commands": None})[0], [])

    def test_an_older_agentvow_than_the_floor_asks_a_person(self):
        pol = {"min_tool_version": "0.5.2"}
        self.assertEqual(rules(with_inputs(version="0.5.2"), pol)[0], [])
        self.assertEqual(rules(with_inputs(version="0.6.0"), pol)[0], [])
        self.assertEqual(rules(with_inputs(version="0.5.1"), pol)[0], [("gate_inputs", "needs_acknowledgement")])
        r = rcpt(1); r.pop("tool_version", None)
        self.assertEqual(rules(r, pol)[0], [("gate_inputs", "needs_acknowledgement")])   # unknown version is not read as new enough
        self.assertEqual(rules(with_inputs(version="0.5.2.dev1"), pol)[0], [("gate_inputs", "needs_acknowledgement")])

    def test_a_receipt_that_does_not_say_how_the_gate_was_configured_asks_a_person_when_the_policy_requires_it(self):
        self.assertEqual(rules(rcpt(1), {"require_gate_inputs": True})[0], [("gate_inputs", "needs_acknowledgement")])
        self.assertEqual(rules(with_inputs(""), {"require_gate_inputs": True})[0], [])

    def test_a_listed_acknowledger_can_acknowledge_it_and_a_contradiction_still_blocks(self):
        pol = {"allowed_test_commands": [], "acknowledgers": ["ann"]}
        r = with_inputs("{py} -c pass")
        ev = policy.evaluate(r, pol)
        ack = {"schema": policy.ACK, "receipt_sha": ev["receipt_sha"], "by": "ann"}
        self.assertEqual(policy.evaluate(r, pol, [ack])["decision"], "allow")
        bad = with_inputs("{py} -c pass"); bad["claims"][0]["verdict"] = "CONTRADICTED"
        self.assertEqual(policy.evaluate(bad, pol)["decision"], "block")

    def test_the_new_policy_keys_are_validated(self):
        for bad in ({"allowed_test_commands": "x"}, {"allowed_test_commands": [1]}, {"allowed_test_commands": ["x"] * 21}, {"min_tool_version": "latest"}, {"require_gate_inputs": "yes"}):
            self.assertIsNotNone(policy.validate_policy({**policy.DEFAULT_POLICY, **bad}), bad)
        self.assertIsNone(policy.validate_policy({**policy.DEFAULT_POLICY, "allowed_test_commands": ["a"], "min_tool_version": "0.5.2", "require_gate_inputs": True}))


class Workflows(unittest.TestCase):
    def test_every_gate_workflow_passes_the_inputs_to_the_receipt_step(self):
        for f in ("gate.yml", "gate-service.yml", "gate-service-fork.yml", "gate-attest.yml"):
            t = (ROOT / ".github" / "workflows" / f).read_text()
            self.assertIn("AGENTVOW_GATE_TEST_COMMAND: ${{ inputs.test-command }}", t, f); self.assertIn("AGENTVOW_GATE_TEST_TIMEOUT: ${{ inputs.test-timeout }}", t, f)


if __name__ == "__main__":
    unittest.main()
