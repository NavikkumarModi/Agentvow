import io, json, re, sys, tempfile, unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agentvow import cli, explain, policy  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def result(decision, *reasons):
    return {"decision": decision, "conclusion": {"allow": "success", "needs_acknowledgement": "action_required", "block": "failure"}[decision],
            "reasons": [{"rule": r, "outcome": o, "text": t, "acknowledged_by": by} for r, o, t, by in reasons], "receipt_sha": "ab" * 32}


class Explain(unittest.TestCase):
    def test_every_rule_the_engine_and_the_service_can_emit_has_a_plain_description(self):
        rules = set(re.findall(r'add\("([a-z_]+)"', (ROOT / "agentvow" / "policy.py").read_text())) | set(re.findall(r'"rule": "([a-z_]+)"', (ROOT / "agentvow" / "policy.py").read_text()))
        rules |= set(re.findall(r'"rule": "([a-z_]+)"', (ROOT / "controlplane" / "service" / "core.py").read_text()))
        rules |= set(re.findall(r'"rule": "([a-z_]+)"', (ROOT / "controlplane" / "service" / "core.py").read_text()))
        self.assertTrue({"contradicted", "unknown", "supported", "partial_capture", "unauthenticated_capture", "policy_unreadable", "invalid_input"} <= rules, rules)
        self.assertEqual(sorted(rules - set(explain.RULES) - {"no_receipt"}), [])   # a new rule without a plain sentence fails here, not in front of a user

    def test_each_decision_says_what_it_means_for_the_merge(self):
        self.assertIn("nothing that needs a person's attention", explain.explain(result("allow", ("supported", "allow", "x", None))))
        t = explain.explain(result("needs_acknowledgement", ("unknown", "needs_acknowledgement", "x", None)), ["1234567890abcdef"], ["alice"], mode="service")
        self.assertIn("must look at it and acknowledge", t); self.assertIn("`/agentvow acknowledge 1234567890ab`", t); self.assertIn("@alice", t); self.assertIn("never be acknowledged", t)
        b = explain.explain(result("block", ("contradicted", "block", "x", None)))
        self.assertIn("will not let this through", b); self.assertIn("cannot be acknowledged away", b); self.assertNotIn("/agentvow acknowledge", b)
        for text in (t, b):
            self.assertIn("What this does not show", text)

    def test_a_block_from_the_policy_is_not_offered_an_acknowledgement(self):
        t = explain.explain(result("block", ("unknown", "block", "x", None)), ["a" * 12], ["alice"])
        self.assertIn("cannot be acknowledged", t); self.assertNotIn("a listed acknowledger replies", t); self.assertNotIn("/agentvow acknowledge", t)
        self.assertIn("a rule in this repository's policy is set to block it", t)

    def test_several_receipts_each_get_their_own_command_and_the_requirements_are_stated(self):
        t = explain.explain(result("needs_acknowledgement", ("unknown", "needs_acknowledgement", "x", None)), ["a" * 12, "b" * 12], ["alice"], mode="service")
        self.assertIn("Each receipt that needs it needs its own comment", t); self.assertIn("`/agentvow acknowledge " + "a" * 12 + "` and `/agentvow acknowledge " + "b" * 12 + "`", t)
        self.assertIn("write access", t); self.assertIn("cannot be the pull request's author", t)

    def test_a_supported_result_that_the_policy_wants_confirmed_asks_for_a_person(self):
        t = explain.explain(result("needs_acknowledgement", ("supported", "needs_acknowledgement", "x", None)), ["a" * 12], ["alice"], mode="service")
        self.assertIn("asks a person to confirm even supported results", t); self.assertNotIn("Nothing to do", t)

    def test_an_unlisted_acknowledger_is_said_plainly_and_an_acknowledged_item_asks_for_nothing(self):
        self.assertIn("lists no acknowledger", explain.explain(result("needs_acknowledgement", ("unknown", "needs_acknowledgement", "x", None)), ["a" * 12], [], mode="service"))
        done = explain.explain(result("allow", ("unknown", "needs_acknowledgement", "x", "alice")))
        self.assertIn("Acknowledged by @alice", done); self.assertNotIn("What to do", done)

    def test_local_mode_does_not_pretend_there_is_a_pull_request_comment_flow_and_never_guesses_who_may_acknowledge(self):
        res = result("needs_acknowledgement", ("unknown", "needs_acknowledgement", "x", None))
        unknown = explain.explain(res, ["a" * 12])                                  # acknowledgers not known (an older result)
        self.assertIn("agentvow policy evaluate --ack FILE", unknown); self.assertNotIn("Listed acknowledgers", unknown); self.assertNotIn("lists no acknowledger", unknown)
        self.assertIn("Listed acknowledgers: @alice", explain.explain(res, ["a" * 12], ["alice"])); self.assertIn("lists no acknowledger", explain.explain(res, ["a" * 12], []))

    def test_an_evaluation_carries_the_policys_acknowledgers_and_the_cli_prints_them(self):
        d = {"status": "x", "commit": "a" * 40, "unexamined": 0, "findings": [{"kind": "tests_pass", "verdict": "UNKNOWN", "meta": {}}], "pack": {}}
        res = policy.evaluate(policy.build_receipt(d, "o/n", "b" * 40), {"schema": policy.POLICY, "acknowledgers": ["alice"]})
        self.assertEqual(res["acknowledgers"], ["alice"])
        f = Path(tempfile.mkdtemp()) / "r.json"; f.write_text(json.dumps(res)); out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(cli.main(["policy", "explain", "--result", str(f)]), 0)
        self.assertIn("Listed acknowledgers: @alice", out.getvalue())

    def test_repeated_reasons_are_grouped(self):
        t = explain.explain(result("needs_acknowledgement", ("unknown", "needs_acknowledgement", "a", None), ("unknown", "needs_acknowledgement", "b", None)), ["a" * 12])
        self.assertEqual(t.count("could not be confirmed or refuted"), 1); self.assertIn("(2 claims)", t)

    def test_text_that_came_from_a_receipt_cannot_inject_markup(self):
        evil = "<script>alert(1)</script> [x](http://evil) | a |\n# heading `code` @everyone"
        t = explain.explain(result("needs_acknowledgement", ("unknown", "needs_acknowledgement", evil, "bob<img src=x>")), ["../../x`" + "a" * 20], ["eve|<b>"])
        for bad in ("<script>", "<img", "<b>", "](http", "\n# heading", "@everyone", "| a |"):
            self.assertNotIn(bad, t)
        self.assertEqual(explain.explain({"decision": "weird", "reasons": "nope"}).split("\n")[0], explain.HEADLINES["block"])   # an unknown decision reads as blocked, malformed reasons do not crash

    def test_cli_explain_prints_the_text_and_refuses_bad_input(self):
        f = Path(tempfile.mkdtemp()) / "r.json"; f.write_text(json.dumps(result("block", ("contradicted", "block", "x", None))))
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            self.assertEqual(cli.main(["policy", "explain", "--result", str(f)]), 0)
        self.assertIn("will not let this through", out.getvalue())
        f.write_text("[1]")
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(["policy", "explain", "--result", str(f)]), 3)
            self.assertEqual(cli.main(["policy", "explain", "--result", str(f) + ".missing"]), 3)

    def test_the_text_for_a_real_evaluation_is_readable_without_knowing_the_internals(self):
        d = {"status": "x", "commit": "a" * 40, "unexamined": 0, "findings": [{"kind": "tests_pass", "verdict": "UNKNOWN", "meta": {}}], "pack": {}}
        res = policy.evaluate(policy.build_receipt(d, "o/n", "b" * 40))
        t = explain.explain(res, [res["receipt_sha"]])
        for jargon in ("receipt_sha", "policy_sha", "capture_source", "git tree"):
            self.assertNotIn(jargon, t)
        self.assertIn("What to do", t)


if __name__ == "__main__":
    unittest.main()
