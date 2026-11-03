"""Receipt authentication for `queue --github --verify`: GitHub's attestation check is reused through `gh`, and the signer COMMIT must be on an allowed list (a signer path alone passes a pull request that edits the signer)."""
import io
import json
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from agentvow import cli, ghreceipts, queue  # noqa: E402
from test_ghreceipts import REPO, art, fake_gh, zip_of  # noqa: E402
from test_pilot_report import rcpt  # noqa: E402

try:
    import yaml
except ImportError:
    yaml = None

SIGNER = ghreceipts.DEFAULT_SIGNER
GOOD, OLD = "a" * 40, "b" * 40


def cert(digest=GOOD, repo=REPO, signer=SIGNER):
    return [{"verificationResult": {"signature": {"certificate": {"subjectAlternativeName": f"https://github.com/{signer}@{digest}", "buildSignerDigest": digest, "sourceRepositoryURI": f"https://github.com/{repo}", "runnerEnvironment": "github-hosted"}}}}]


def gh_with_attestation(base, outcome, seen=None):
    """outcome: a certificate list (verification passes) or None (gh exits 1: no attestation / wrong signer)."""
    def run(cmd, **kw):
        if cmd[:3] == ["gh", "attestation", "verify"]:
            if seen is not None:
                seen.append((cmd, Path(cmd[3]).read_bytes()))
            return subprocess.CompletedProcess(cmd, 0 if outcome else 1, json.dumps(outcome) if outcome else "", "")
        return base(cmd, **kw)
    return run


class Verify(unittest.TestCase):
    def setUp(self):
        self.sha = f"{1:040x}"
        self.r = rcpt(1, "UNKNOWN"); self.r["repo"] = REPO
        self.base = fake_gh([(7, self.sha)], {self.sha: [11]}, {11: [art(21)]}, {21: zip_of(self.r)})
        self.v = {"digests": [GOOD]}

    def fetch(self, outcome, verify=None, seen=None):
        auth = {}
        got, missing, note = ghreceipts.fetch(REPO, run=gh_with_attestation(self.base, outcome, seen), verify=verify or self.v, auth=auth)
        return got, auth, note

    def test_a_receipt_from_the_pinned_signer_at_an_allowed_commit_verifies(self):
        seen = []
        got, auth, note = self.fetch(cert(), seen=seen)
        self.assertEqual(auth[(REPO, self.sha)], (True, ""))
        self.assertEqual(len(got), 1)
        self.assertEqual(seen[0][1], zip_of_bytes(self.r))   # the bytes handed to gh are exactly the file in the artifact
        self.assertIn("--signer-workflow", seen[0][0]); self.assertIn(SIGNER, seen[0][0]); self.assertIn("--deny-self-hosted-runners", seen[0][0])
        self.assertNotIn("not authenticated", note)

    def test_no_attestation_or_a_wrong_signer_does_not_verify(self):
        _, auth, _ = self.fetch(None)
        self.assertFalse(auth[(REPO, self.sha)][0])

    def test_the_right_signer_at_a_commit_not_on_the_list_does_not_verify(self):   # experiment C: a pull request edits the signer at the same path
        _, auth, _ = self.fetch(cert(digest=OLD))
        ok, why = auth[(REPO, self.sha)]
        self.assertFalse(ok); self.assertIn("allowed list", why)

    def test_another_repository_or_signer_in_the_certificate_does_not_verify(self):
        for c in (cert(repo="evil/n"), cert(signer="evil/Agentvow/.github/workflows/gate-attest.yml")):
            _, auth, _ = self.fetch(c)
            self.assertFalse(auth[(REPO, self.sha)][0])

    def test_garbage_output_from_gh_does_not_verify(self):
        for out in ({"verificationResult": {}}, [], [{}], [{"verificationResult": None}]):
            _, auth, _ = self.fetch(out or [{}])
            self.assertFalse(auth[(REPO, self.sha)][0])

    def test_the_allowed_list_is_mandatory_and_validated(self):
        for bad in ({}, {"digests": []}, {"digests": ["main"]}, {"digests": [GOOD], "signer": "../x"}, {"digests": [GOOD] * 21}):
            with self.assertRaises(ValueError):
                ghreceipts.fetch(REPO, run=lambda *a, **k: self.fail("gh was called"), verify=bad, auth={})

    def test_without_verify_gh_attestation_is_never_called(self):
        seen = []
        got, missing, note = ghreceipts.fetch(REPO, run=gh_with_attestation(self.base, cert(), seen))
        self.assertEqual((len(got), seen), (1, []))
        self.assertIn("not authenticated", note)


def zip_of_bytes(r):
    import zipfile
    with zipfile.ZipFile(io.BytesIO(zip_of(r))) as z:
        return z.read("receipt.json")


class Ranking(unittest.TestCase):
    def build(self, receipts, ok, mode):
        return queue.build(receipts, None, [], auth={(r["repo"], r["commit"]): (ok, "no valid attestation from the pinned signer workflow") for r in receipts}, mode=mode)

    def clean(self):
        r = rcpt(1); r["repo"] = REPO
        self.assertEqual(queue.build([r])[0]["state"], "allow")   # the default fixture is a clean receipt under the default policy
        return r

    def test_an_unverified_clean_receipt_is_never_ranked_as_no_flag(self):
        r = self.clean()
        self.assertEqual(self.build([r], False, "report")[0]["state"], "unverified")
        self.assertEqual(self.build([r], False, "require")[0]["state"], "needs_acknowledgement")
        self.assertEqual(self.build([r], True, "require")[0]["state"], "allow")
        self.assertEqual(self.build([r], True, "require")[0]["auth"], "verified")
        self.assertEqual(queue.build([r])[0]["state"], "allow")   # verification off: unchanged

    def test_unverified_never_weakens_a_stop(self):
        r = rcpt(1, "CONTRADICTED"); r["repo"] = REPO
        base = queue.build([r])[0]["state"]
        self.assertEqual(self.build([r], False, "report")[0]["state"], base)

    def test_the_text_says_so_and_does_not_count_it_as_no_flag(self):
        r = self.clean()
        text = queue.render_text(self.build([r], False, "report"))
        self.assertIn("1 not authenticated", text); self.assertIn("0 with no flag raised", text); self.assertIn("could not be authenticated", text)
        self.assertIn("1 not authenticated", queue.render_markdown(self.build([r], False, "report")))

    def test_unverified_sorts_between_acknowledged_and_no_flag(self):
        self.assertTrue(queue.ORDER["acknowledged"] < queue.ORDER["unverified"] < queue.ORDER["allow"])


class Cli(unittest.TestCase):
    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                rc = cli.main(["queue", *args])
            except SystemExit as e:
                rc = e.code
        return rc, out.getvalue(), err.getvalue()

    def test_verify_needs_github(self):
        rc, _, err = self.run_cli("--receipts", ".", "--verify", "report")
        self.assertEqual(rc, 3); self.assertIn("--verify needs --github", err)

    def test_verify_without_an_allowed_commit_is_refused_before_any_call(self):
        with mock.patch("subprocess.run", side_effect=AssertionError("gh was called")):
            rc, _, err = self.run_cli("--github", REPO, "--verify", "require")
        self.assertEqual(rc, 3); self.assertIn("allowed signer commits", err)


@unittest.skipIf(yaml is None, "PyYAML not installed")
class AttestWorkflow(unittest.TestCase):
    WF = ROOT / ".github" / "workflows" / "gate-attest.yml"

    def setUp(self):
        self.text = self.WF.read_text()
        self.doc = yaml.safe_load(self.text)
        self.jobs = self.doc["jobs"]

    def test_the_replay_job_is_identical_to_the_local_gate_and_holds_no_token(self):
        local = yaml.safe_load((ROOT / ".github" / "workflows" / "gate.yml").read_text())
        self.assertEqual(self.jobs["replay"], local["jobs"]["replay"])
        self.assertEqual(self.jobs["replay"]["permissions"], {"contents": "read"})

    def test_only_the_attest_job_holds_oidc_and_attestation_permissions_and_it_runs_no_pull_request_code(self):
        self.assertEqual(self.jobs["attest"]["permissions"], {"contents": "read", "id-token": "write", "attestations": "write"})
        self.assertEqual(self.jobs["decide"]["permissions"], {})
        self.assertEqual(self.doc["permissions"], {"contents": "read"})
        self.assertFalse(any("checkout" in s.get("uses", "") for s in self.jobs["attest"]["steps"]))
        self.assertEqual(self.jobs["attest"]["needs"], ["replay"])
        for s in self.jobs["attest"]["steps"]:
            self.assertNotRegex(s.get("run", ""), r"\$\{\{")   # nothing from the event reaches the shell

    def test_the_attest_job_signs_only_the_file_the_replay_hashed(self):
        run = next(s for s in self.jobs["attest"]["steps"] if "run" in s)
        self.assertIn("EXPECTED", run["env"]); self.assertIn("needs.replay.outputs.receipt-sha", run["env"]["EXPECTED"])
        self.assertIn("exit 1", run["run"])
        sign = next(s for s in self.jobs["attest"]["steps"] if "attest" in s.get("uses", ""))
        self.assertTrue(sign["with"]["subject-path"].endswith("/gate/receipt.json"))

    def test_actions_are_pinned_by_sha(self):
        for j in self.jobs.values():
            for s in j["steps"]:
                if "uses" in s:
                    self.assertRegex(s["uses"], r"@[0-9a-f]{40}$")

    def test_the_decision_does_not_depend_on_the_attest_job(self):
        self.assertEqual(self.jobs["decide"]["needs"], ["replay"])


if __name__ == "__main__":
    unittest.main()
