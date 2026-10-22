import json, sys, time, unittest, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agentvow import policy  # noqa: E402
from controlplane import mock_server as cp  # noqa: E402

SECRET = b"test-secret"
WF = "agentvow/gate-workflow/.github/workflows/gate.yml@refs/tags/v1"
TREE = "b" * 40
COMMIT = "a" * 40


def receipt(verdict="SUPPORTED_BY_PRIOR_EVIDENCE", repo="o/n", commit=COMMIT, tree=TREE):
    d = {"status": "x", "commit": commit, "unexamined": 0, "findings": [{"kind": "tests_pass", "verdict": verdict, "meta": {}}], "pack": {"reproducibility": {"code": "both"}, "contexts": [], "coverage": {"available": False}}}
    return policy.build_receipt(d, repo, tree)


def tok(**c):
    return "Bearer " + cp.make_token(SECRET, {"repository": "o/n", "job_workflow_ref": WF, "exp": time.time() + 600, **c})


class Mock(unittest.TestCase):
    def setUp(self):
        self.app = cp.App(cp.MockAuth(SECRET), cp.Oracle({("o/n", COMMIT): TREE}))
        self.app.handle("PUT", "/v1/policy", {"Authorization": "Bearer admin"}, json.dumps({"repo": "o/n", "policy": {"schema": policy.POLICY, "acknowledgers": ["alice"]}}).encode())

    def post(self, r, auth=None):
        return self.app.handle("POST", "/v1/receipts", {"Authorization": auth or tok()}, json.dumps(r).encode())

    def check(self, commit=COMMIT):
        return self.app.handle("GET", f"/v1/check?repo=o/n&commit={commit}", {})[1]

    def test_a_good_receipt_is_accepted_and_the_check_allows(self):
        code, o = self.post(receipt())
        self.assertEqual((code, o["decision"]["decision"]), (200, "allow"))
        self.assertEqual(self.check()["conclusion"], "success")

    def test_forged_expired_alg_none_and_missing_tokens_are_refused(self):
        r = receipt()
        for auth in (None, "", "Bearer garbage", "Bearer " + cp.make_token(b"wrong", {"repository": "o/n", "job_workflow_ref": WF, "exp": time.time() + 60}),
                     "Bearer " + cp.make_token(SECRET, {"repository": "o/n", "job_workflow_ref": WF, "exp": time.time() - 5}),
                     "Bearer " + cp._b64(b'{"alg":"none"}') + "." + cp._b64(json.dumps({"repository": "o/n", "job_workflow_ref": WF, "exp": time.time() + 60}).encode()) + "."):
            code, _ = self.app.handle("POST", "/v1/receipts", {"Authorization": auth} if auth is not None else {}, json.dumps(r).encode())
            self.assertEqual(code, 401, auth)

    def test_token_for_another_repository_or_an_untrusted_workflow_is_refused(self):
        self.assertEqual(self.post(receipt(), tok(repository="evil/repo"))[0], 403)
        self.assertEqual(self.post(receipt(), tok(job_workflow_ref="o/n/.github/workflows/mine.yml@refs/heads/pr-branch"))[0], 403)   # a pull request's own workflow cannot post receipts

    def test_a_receipt_whose_content_hash_does_not_match_the_commit_is_refused(self):
        self.assertEqual(self.post(receipt(tree="c" * 40))[0], 422)
        self.assertEqual(self.post(receipt(commit="d" * 40))[0], 422)   # unknown commit

    def test_unknown_blocks_until_a_listed_person_acknowledges_exactly_that_receipt(self):
        r = receipt("UNKNOWN")
        _, o = self.post(r)
        self.assertEqual(o["decision"]["decision"], "needs_acknowledgement")
        self.assertEqual(self.check()["conclusion"], "action_required")
        rsha = o["id"]
        ack = lambda login: self.app.handle("POST", "/v1/acks", {"Authorization": "Bearer " + cp.make_token(SECRET, {"login": login, "exp": time.time() + 60})}, json.dumps({"receipt_sha": rsha, "note": "seen"}).encode())
        self.assertEqual(ack("mallory")[0], 403)
        self.assertEqual(self.check()["conclusion"], "action_required")
        self.assertEqual(ack("alice")[0], 200)
        self.assertEqual(self.check()["conclusion"], "success")

    def test_a_contradicted_receipt_fails_the_check_and_acknowledgement_does_not_help(self):
        _, o = self.post(receipt("CONTRADICTED"))
        self.assertEqual(self.check()["conclusion"], "failure")
        self.app.handle("POST", "/v1/acks", {"Authorization": "Bearer " + cp.make_token(SECRET, {"login": "alice", "exp": time.time() + 60})}, json.dumps({"receipt_sha": o["id"]}).encode())
        self.assertEqual(self.check()["conclusion"], "failure")

    def test_no_receipt_for_a_commit_fails_closed(self):
        c = self.check("e" * 40)
        self.assertEqual(c["conclusion"], "action_required")
        self.assertIn("No receipt", c["reasons"][0]["text"])

    def test_the_ack_identity_comes_from_the_token_not_the_body(self):
        _, o = self.post(receipt("UNKNOWN"))
        code, _ = self.app.handle("POST", "/v1/acks", {"Authorization": "Bearer " + cp.make_token(SECRET, {"login": "mallory", "exp": time.time() + 60})},
                                  json.dumps({"receipt_sha": o["id"], "by": "alice"}).encode())
        self.assertEqual(code, 403)

    def test_policy_and_audit_need_the_admin_token_and_audit_lists_everything(self):
        self.assertEqual(self.app.handle("PUT", "/v1/policy", {}, b"{}")[0], 401)
        self.assertEqual(self.app.handle("GET", "/v1/audit?repo=o/n", {})[0], 401)
        self.post(receipt("UNKNOWN"))
        code, o = self.app.handle("GET", "/v1/audit?repo=o/n", {"Authorization": "Bearer admin"})
        self.assertEqual((code, len(o["records"])), (200, 1))
        self.assertEqual(o["records"][0]["decision"], "needs_acknowledgement")
        code, c = self.app.handle("GET", "/v1/audit?repo=o/n&format=csv", {"Authorization": "Bearer admin"})
        self.assertIn("receipt_sha,commit,git_tree,decision", c["csv"])

    def test_oversized_and_malformed_bodies_and_invalid_policy_are_refused(self):
        self.assertEqual(self.app.handle("POST", "/v1/receipts", {"Authorization": tok()}, b"x" * (cp.MAX_BODY + 1))[0], 413)
        self.assertEqual(self.app.handle("POST", "/v1/receipts", {"Authorization": tok()}, b"{not json")[0], 400)
        self.assertEqual(self.app.handle("PUT", "/v1/policy", {"Authorization": "Bearer admin"}, json.dumps({"repo": "o/n", "policy": {"schema": policy.POLICY, "contradicted": "allow"}}).encode())[0], 422)

    def test_it_works_over_http(self):
        srv = cp.serve(self.app)
        try:
            url = f"http://127.0.0.1:{srv.server_address[1]}"
            req = urllib.request.Request(url + "/v1/receipts", data=json.dumps(receipt()).encode(), headers={"Authorization": tok(), "Content-Type": "application/json"}, method="POST")
            self.assertEqual(json.load(urllib.request.urlopen(req))["decision"]["decision"], "allow")
            self.assertEqual(json.load(urllib.request.urlopen(f"{url}/v1/check?repo=o/n&commit={COMMIT}"))["conclusion"], "success")
        finally:
            srv.shutdown()


if __name__ == "__main__":
    unittest.main()
