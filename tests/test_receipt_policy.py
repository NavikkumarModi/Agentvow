import io, json, subprocess, sys, tempfile, unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agentvow import cli, policy  # noqa: E402

DECISION = {"status": "NO CONTRADICTION FOUND (scoped, not a safety verdict)", "commit": "a" * 40, "unexamined": 1,
            "findings": [{"claim": "All tests pass. (secret path /home/me/x)", "kind": "tests_pass", "verdict": "SUPPORTED_BY_PRIOR_EVIDENCE", "why": "free text with /home/me/project/secret.py",
                          "meta": {"support_basis": "captured_environment", "changed_line_coverage": {"executed": 3, "executable": 4, "not_run": {"a.py": [9]}}}}],
            "pack": {"reproducibility": {"code": "both", "text": "t"}, "contexts": [{"name": "captured environment", "result": "pass", "counts": {"passed": 5, "failed": 0}, "dropped_pins": []},
                                                                                  {"name": "project-native setup", "result": "pass", "counts": {"passed": 5, "failed": 0}, "steps": ["pip install -r requirements.txt"], "env_names": ["TOKEN_X=1"]}],
                     "coverage": {"available": True, "executed": 3, "executable": 4}, "manifest": {"items": [{"category": "environment variables", "names": ["SECRET_NAME"]}]}}}


def receipt(**over):
    r = policy.build_receipt(json.loads(json.dumps(DECISION)), "o/n", "b" * 40, "main")
    r.update(over)
    return r


def with_verdict(v, **meta):
    d = json.loads(json.dumps(DECISION)); d["findings"][0]["verdict"] = v; d["findings"][0]["meta"].update(meta)
    return policy.build_receipt(d, "o/n", "b" * 40)


def ack(r, by="alice"):
    return {"schema": policy.ACK, "receipt_sha": policy.sha(r), "by": by, "at": "t", "note": "ok"}


class Receipt(unittest.TestCase):
    def test_receipt_is_minimal_no_free_text_no_env_values_no_paths(self):
        r = receipt()
        txt = json.dumps(r)
        for leak in ("/home/me", "secret.py", "TOKEN_X", "=1", "pip install", "SECRET_NAME"):
            self.assertNotIn(leak, txt)
        self.assertEqual(r["claims"][0]["verdict"], "SUPPORTED_BY_PRIOR_EVIDENCE")
        self.assertEqual(r["not_reproduced"], ["environment variables"])   # category names only
        self.assertEqual(r["coverage"], {"executed": 3, "executable": 4})
        self.assertEqual(r["git_tree"], "b" * 40)

    def test_hash_is_stable_and_changes_with_content(self):
        self.assertEqual(policy.sha({"a": 1, "b": 2}), policy.sha({"b": 2, "a": 1}))
        self.assertNotEqual(policy.sha({"a": 1}), policy.sha({"a": 2}))


class Evaluate(unittest.TestCase):
    def test_supported_is_allowed_under_the_default_policy(self):
        res = policy.evaluate(receipt())
        self.assertEqual((res["decision"], res["conclusion"]), ("allow", "success"))

    def test_contradicted_blocks_and_cannot_be_acknowledged(self):
        r = with_verdict("CONTRADICTED")
        res = policy.evaluate(r, {"schema": policy.POLICY, "acknowledgers": ["alice"]}, [ack(r)])
        self.assertEqual((res["decision"], res["conclusion"]), ("block", "failure"))
        self.assertIn("cannot be acknowledged", res["reasons"][0]["text"])

    def test_unknown_needs_acknowledgement_then_a_listed_person_can_acknowledge_exactly_this_receipt(self):
        r = with_verdict("UNKNOWN")
        pol = {"schema": policy.POLICY, "acknowledgers": ["Alice"]}
        self.assertEqual(policy.evaluate(r, pol)["decision"], "needs_acknowledgement")
        self.assertEqual(policy.evaluate(r, pol, [ack(r, "alice")])["decision"], "allow")   # case-insensitive login
        self.assertEqual(policy.evaluate(r, pol, [ack(r, "mallory")])["decision"], "needs_acknowledgement")   # not a listed acknowledger
        other = with_verdict("UNKNOWN", support_basis="x")   # a changed receipt invalidates the old acknowledgement
        self.assertEqual(policy.evaluate(other, pol, [ack(r, "alice")])["decision"], "needs_acknowledgement")
        bad = {**ack(r, "alice"), "schema": "wrong"}
        self.assertEqual(policy.evaluate(r, pol, [bad])["decision"], "needs_acknowledgement")

    def test_policy_can_block_unknown_and_unauthenticated_capture_and_low_coverage(self):
        self.assertEqual(policy.evaluate(with_verdict("UNKNOWN"), {"schema": policy.POLICY, "unknown": "block"})["decision"], "block")
        r = with_verdict("SUPPORTED_BY_PRIOR_EVIDENCE", capture_source="bundle")
        self.assertEqual(policy.evaluate(r, {"schema": policy.POLICY})["decision"], "needs_acknowledgement")   # the default asks a person
        self.assertEqual(policy.evaluate(r, {"schema": policy.POLICY, "unauthenticated_capture": "allow"})["decision"], "allow")
        self.assertEqual(policy.evaluate(r, {"schema": policy.POLICY, "unauthenticated_capture": "block"})["decision"], "block")
        self.assertEqual(policy.evaluate(receipt(), {"schema": policy.POLICY, "min_changed_line_coverage": 0.9})["decision"], "needs_acknowledgement")   # 3 of 4 = 75%
        self.assertEqual(policy.evaluate(receipt(), {"schema": policy.POLICY, "min_changed_line_coverage": 0.5})["decision"], "allow")

    def test_require_reproducibility_both(self):
        r = receipt(reproducibility="single")
        self.assertEqual(policy.evaluate(r, {"schema": policy.POLICY, "require_reproducibility": "both"})["decision"], "needs_acknowledgement")
        self.assertEqual(policy.evaluate(receipt(), {"schema": policy.POLICY, "require_reproducibility": "both"})["decision"], "allow")

    def test_no_claims_needs_acknowledgement_by_default(self):
        d = json.loads(json.dumps(DECISION)); d["findings"] = []
        self.assertEqual(policy.evaluate(policy.build_receipt(d, "o/n", "b" * 40))["decision"], "needs_acknowledgement")

    def test_invalid_policy_blocks_everything(self):
        for bad in ({"schema": policy.POLICY, "contradicted": "allow"}, {"schema": policy.POLICY, "typo_key": 1}, {"schema": "x"}, {"schema": policy.POLICY, "min_changed_line_coverage": 7}):
            self.assertEqual(policy.evaluate(receipt(), bad)["decision"], "block", bad)

    def test_evaluation_is_deterministic(self):
        r = receipt()
        self.assertEqual(policy.evaluate(r, {"schema": policy.POLICY}), policy.evaluate(r, {"schema": policy.POLICY}))


class Hostile(unittest.TestCase):
    def test_malformed_receipts_block_and_never_raise(self):
        base = receipt()
        for bad in ({**base, "claims": [1]}, {**base, "claims": "abc"}, {**base, "claims": [{"verdict": "SUPPORTED_BY_PRIOR_EVIDENCE", "kind": "x", "changed_lines": {"executed": 1, "executable": "5"}}]},
                    {**base, "coverage": {"executed": -1, "executable": 3}}, {**base, "not_reproduced": [1]}, {**base, "pr": True}, {**base, "repo": ""}, {**base, "claims": [{"kind": "x"}] * 500}, [], "x", None, 7):
            res = policy.evaluate(bad)
            self.assertEqual(res["decision"], "block", bad if not isinstance(bad, dict) else list(bad))
            self.assertEqual(res["reasons"][0]["rule"], "invalid_input")
        self.assertIsNone(policy.validate_receipt(base))

    def test_unrecognised_or_oddly_cased_verdicts_never_become_acknowledgeable(self):
        pol = {"schema": policy.POLICY, "acknowledgers": ["bob"]}
        for v in ("contradicted", " CONTRADICTED ", "Contradicted"):
            r = with_verdict(v)
            res = policy.evaluate(r, pol, [ack(r, "BOB")])
            self.assertEqual(res["decision"], "block", v)
        r = with_verdict("MAYBE")
        res = policy.evaluate(r, pol, [ack(r, "bob")])
        self.assertEqual((res["decision"], res["reasons"][0]["rule"]), ("block", "unrecognized_verdict"))

    def test_a_coverage_floor_never_passes_silently_when_coverage_was_not_measured(self):
        floor = {"schema": policy.POLICY, "min_changed_line_coverage": 0.9}
        for cl in (None, {"executed": None, "executable": None}):
            r = with_verdict("SUPPORTED_BY_PRIOR_EVIDENCE")
            r["claims"][0]["changed_lines"] = cl
            r["coverage"] = None
            res = policy.evaluate(r, floor)
            self.assertEqual(res["decision"], "needs_acknowledgement", cl)
            self.assertIn("not measured", " ".join(x["text"] for x in res["reasons"]))
        r = with_verdict("SUPPORTED_BY_PRIOR_EVIDENCE")
        r["claims"][0]["changed_lines"] = {"executed": 0, "executable": 0}
        self.assertEqual(policy.evaluate(r, floor)["decision"], "allow")   # nothing executable changed (for example docs only): nothing to cover

    def test_receipts_record_where_a_capture_came_from(self):
        self.assertEqual(with_verdict("SUPPORTED_BY_PRIOR_EVIDENCE", capture_source="bundle")["claims"][0]["capture_source"], "bundle")
        self.assertEqual(with_verdict("SUPPORTED_BY_PRIOR_EVIDENCE")["claims"][0]["capture_source"], "")   # no capture at all is not "authenticated"


class Cli(unittest.TestCase):
    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_receipt_and_policy_commands_and_exit_codes(self):
        d = Path(tempfile.mkdtemp())
        g = lambda *a: subprocess.run(["git", "-C", str(d), *a], check=True, capture_output=True, text=True)
        g("init", "-q", "-b", "main"); g("config", "user.email", "a@b"); g("config", "user.name", "t"); (d / "a.py").write_text("x = 1\n"); g("add", "-A"); g("commit", "-qm", "c")
        dec = d.parent / (d.name + "_dec.json"); dec.write_text(json.dumps(DECISION))
        out = d.parent / (d.name + "_r.json")
        code, _, _ = self.run_cli("receipt", "--decision", str(dec), "--repo-slug", "o/n", "--repo", str(d), "-o", str(out))
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.read_text())["git_tree"], g("rev-parse", "HEAD^{tree}").stdout.strip())
        code, o, _ = self.run_cli("policy", "evaluate", "--receipt", str(out))
        self.assertEqual((code, json.loads(o)["decision"]), (0, "allow"))
        blocked = d.parent / (d.name + "_b.json"); blocked.write_text(json.dumps(with_verdict("CONTRADICTED")))
        self.assertEqual(self.run_cli("policy", "evaluate", "--receipt", str(blocked))[0], 1)
        unk = d.parent / (d.name + "_u.json"); unk.write_text(json.dumps(with_verdict("UNKNOWN")))
        self.assertEqual(self.run_cli("policy", "evaluate", "--receipt", str(unk))[0], 2)
        self.assertEqual(self.run_cli("policy", "init")[0], 0)
        self.assertEqual(self.run_cli("policy", "evaluate", "--receipt", "/nonexistent")[0], 3)


if __name__ == "__main__":
    unittest.main()
