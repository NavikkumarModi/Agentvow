import base64, hashlib, hmac, json, sys, time, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from agentvow import policy as P  # noqa: E402
from controlplane.service.core import Config, Service  # noqa: E402
from controlplane.service.github import GitHub, GitHubError  # noqa: E402
from controlplane.service.oidc import OidcError, OidcVerifier, ISSUER  # noqa: E402
from controlplane.service.store import Store  # noqa: E402

GATE_SHA = "c" * 40
WF = f"o/gate/.github/workflows/gate-service.yml@{GATE_SHA}"
TREE, COMMIT = "b" * 40, "a" * 40
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def b64(x): return base64.urlsafe_b64encode(x).rstrip(b"=").decode()


def jwk(key, kid):
    n = key.public_key().public_numbers()
    return {"kty": "RSA", "kid": kid, "n": b64(n.n.to_bytes(256, "big")), "e": b64(n.e.to_bytes(3, "big"))}


def token(claims, key=KEY, kid="k1", alg="RS256"):
    h, p = b64(json.dumps({"alg": alg, "kid": kid}).encode()), b64(json.dumps(claims).encode())
    return f"{h}.{p}.{b64(key.sign(f'{h}.{p}'.encode(), padding.PKCS1v15(), hashes.SHA256()))}"


def claims(**o):
    c = {"iss": ISSUER, "aud": "agentvow", "exp": time.time() + 300, "repository": "o/n", "repository_id": "99", "job_workflow_ref": WF, "job_workflow_sha": GATE_SHA, "event_name": "pull_request", "ref": "refs/pull/7/merge", "sha": "f" * 40, "run_id": 5, "run_attempt": 1}
    c.update(o); return c


def receipt(verdict="SUPPORTED_BY_PRIOR_EVIDENCE", pr=7, **over):
    d = {"status": "x", "commit": COMMIT, "unexamined": 0, "findings": [{"kind": "tests_pass", "verdict": verdict, "meta": {}}], "pack": {"reproducibility": {"code": "both"}, "contexts": []}}
    r = P.build_receipt(d, "o/n", TREE, "main", pr); r.update(over); return r


class FakeGH:
    def __init__(self):
        self.tree, self.private, self.head, self.policy, self.perm, self.author = TREE, False, COMMIT, None, "write", "bob"
        self.checks, self.comments, self.fail_policy, self.branch_ok, self.refs = [], [], False, True, []
        self.app_installed = True   # what GitHub says about the App on a repository: True, False (404) or None (unknown)
    def repo_info(self, repo): return {"private": self.private, "default_branch": "main"}
    def installed(self, repo): return self.app_installed
    def commit_tree(self, repo, sha): return self.tree
    def pr_info(self, repo, n): return {"head_sha": self.head, "base_ref": "main", "state": "open", "user": self.author}
    def branch_sha(self, repo, branch):
        self.refs.append(branch)
        if not self.branch_ok: raise GitHubError("no such branch", 404)
        return "c" * 40
    def file_at(self, repo, path, ref):
        if self.fail_policy: raise GitHubError("boom", 500)
        return self.policy
    def permission(self, repo, login): return self.perm
    def set_check(self, repo, sha, name, status, conclusion, title, summary, check_id=None):
        self.checks.append((repo, sha, name, status, conclusion, title, summary)); return 100 + len(self.checks)
    def comment(self, repo, n, text): self.comments.append(text)


def make(gh=None, **cfg):
    gh = gh or FakeGH()
    verifier = OidcVerifier("agentvow", lambda: {"keys": [jwk(KEY, "k1")]})
    c = Config(trusted_workflows=frozenset({WF}), webhook_secret=b"s3cret", **cfg)
    return Service(c, verifier, gh, Store()), gh


def bound(body, **c):
    """A token issued for exactly this body (audience '<audience>:<sha256 of the body>'), as the gate workflow requests it."""
    return token(claims(aud="agentvow:" + hashlib.sha256(body).hexdigest(), **c))


def post(svc, r=None, tok=None, body=None, **c):
    body = body if body is not None else json.dumps(r or receipt()).encode()
    return svc.post_receipt({"authorization": "Bearer " + (tok or bound(body, **c))}, body)


def hook(svc, event, payload, secret=b"s3cret"):
    body = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
    return svc.webhook({"x-hub-signature-256": sig, "x-github-event": event}, body)


class Oidc(unittest.TestCase):
    def v(self, **kw): return OidcVerifier("agentvow", lambda: {"keys": [jwk(KEY, "k1")]}, **kw)
    def test_good(self): self.assertEqual(self.v().verify(token(claims()))["repository"], "o/n")
    def test_refusals(self):
        bad = [token(claims(), alg="none"), token(claims(), alg="HS256"), token(claims(), key=OTHER), token(claims(), kid="zz"), token(claims(aud="x")), token(claims(iss="https://evil")),
               token(claims(exp=time.time() - 999)), token(claims(nbf=time.time() + 999)), "a.b", "", "a.b.c"]
        for t in bad:
            with self.assertRaises(OidcError, msg=t[:20]): self.v().verify(t)
    def test_jwks_refresh_is_rate_limited(self):
        n = []; t = [1000.0]
        v = OidcVerifier("agentvow", lambda: (n.append(1), {"keys": []})[1], now=lambda: t[0])
        for _ in range(5):
            with self.assertRaises(OidcError): v.verify(token(claims(exp=t[0] + 99), kid="q"))
        self.assertEqual(len(n), 1)


class Receipts(unittest.TestCase):
    def test_happy_path_sets_success(self):
        s, gh = make(); code, o = post(s)
        self.assertEqual(code, 200); self.assertEqual(o["decision"]["decision"], "allow"); self.assertEqual(gh.checks[-1][2:5], ("agentvow/evidence", "completed", "success"))
    def test_no_auth_and_bad_token(self):
        s, _ = make()
        self.assertEqual(s.post_receipt({}, b"{}")[0], 401)
        self.assertEqual(post(s, tok=token(claims(), key=OTHER))[0], 401)
    def test_refusals(self):
        s, gh = make()
        self.assertEqual(post(s, repository="o/other")[0], 403)
        self.assertEqual(post(s, job_workflow_ref="o/gate/.github/workflows/gate.yml@refs/heads/evil")[0], 403)
        self.assertEqual(post(s, event_name="schedule")[0], 403)
        self.assertEqual(post(s, body=b"not json")[0], 400)
        self.assertEqual(post(s, body=b"{}")[0], 422)
        self.assertEqual(post(s, body=b"x" * 70000)[0], 413)
        gh.tree = "c" * 40; self.assertEqual(post(s)[0], 422)
        gh.tree = TREE; gh.head = "d" * 40; self.assertEqual(post(s)[0], 422)
        self.assertEqual(gh.checks, [])
    def test_contradicted_fails(self):
        s, gh = make(); code, o = post(s, receipt("CONTRADICTED")); self.assertEqual(gh.checks[-1][4], "failure")
    def test_unknown_needs_ack_never_success_or_neutral(self):
        s, gh = make(); post(s, receipt("UNKNOWN")); self.assertEqual(gh.checks[-1][4], "action_required")
    def test_policy_from_base_branch_and_error_fails_closed(self):
        s, gh = make(); gh.policy = json.dumps({"schema": P.POLICY, "supported": "block"}); post(s); self.assertEqual(gh.checks[-1][4], "failure")
        gh.policy = "{nope"; post(s, receipt(pr=7, created_at="2")); self.assertEqual(gh.checks[-1][4], "failure")
        gh.policy = json.dumps({"schema": P.POLICY, "evil": 1}); post(s, receipt(created_at="3")); self.assertEqual(gh.checks[-1][4], "failure")
        gh.policy = None; gh.fail_policy = True; post(s, receipt(created_at="4")); self.assertEqual(gh.checks[-1][4], "failure")
    def test_private_repo_needs_paid_plan_and_rate_limit(self):
        s, gh = make(); gh.private = True
        self.assertEqual(post(s)[0], 402); self.assertEqual(gh.checks[-1][4], "action_required")
        s.store.set_plan("o/n", "team"); self.assertEqual(post(s)[0], 200)
        s2, _ = make(per_minute=2)
        codes = [post(s2, receipt(created_at=str(i)))[0] for i in range(4)]; self.assertEqual(codes, [200, 200, 429, 429])
    def test_monthly_allowance(self):
        s, _ = make(monthly_receipts={"free": 2, "team": 9, "business": 9})
        codes = [post(s, receipt(created_at=str(i)))[0] for i in range(3)]; self.assertEqual(codes, [200, 200, 429])
    def test_latest_run_wins_over_older(self):
        s, gh = make(); post(s, receipt("CONTRADICTED"), run_id=9)
        code, o = post(s, receipt("SUPPORTED_BY_PRIOR_EVIDENCE", created_at="2"), run_id=5)   # an older run arrives later
        self.assertEqual(s.check("o/n", COMMIT)[1]["conclusion"], "failure")
        self.assertEqual(gh.checks[-1][4], "failure")   # FINDING C: the published check is the latest run's, not the last arrival
        post(s, receipt("CONTRADICTED"), run_id=9)   # the same receipt again must not lose its place
        self.assertEqual(gh.checks[-1][4], "failure")
    def test_github_outage_is_502_not_success(self):
        s, gh = make(); gh.commit_tree = lambda *a: (_ for _ in ()).throw(GitHubError("down", 500))
        self.assertEqual(post(s)[0], 502); self.assertEqual(gh.checks, [])


class Findings(unittest.TestCase):
    """One test per reproduced finding of the adversarial review (docs/review/CONTROLPLANE_REVIEW_2026-10-22.md)."""
    def test_A_token_is_bound_to_the_receipt_body(self):
        s, gh = make(); real = json.dumps(receipt("UNKNOWN")).encode(); forged = json.dumps(receipt("SUPPORTED_BY_PRIOR_EVIDENCE")).encode()
        stolen = bound(real)   # what a malicious server receives when a caller points service-url at it
        self.assertEqual(s.post_receipt({"authorization": "Bearer " + stolen}, forged)[0], 401)
        self.assertEqual(gh.checks, [])
        self.assertEqual(post(s, tok=token(claims()), body=forged)[0], 401)   # a token for the plain audience no longer works either
        self.assertEqual(s.post_receipt({"authorization": "Bearer " + stolen}, real)[0], 200)   # replaying the very same receipt is harmless
    def test_A_token_must_name_this_pull_request_or_commit(self):
        s, gh = make()
        self.assertEqual(post(s, ref="refs/pull/8/merge")[0], 403)                   # a token from another pull request of the same repository
        self.assertEqual(post(s, receipt(pr=None))[0], 403)                          # pull_request event but a receipt without a pull request
        self.assertEqual(post(s, receipt(pr=None), event_name="push", sha="e" * 40)[0], 403)   # push token for another commit
        self.assertEqual(post(s, receipt(pr=None), event_name="push", sha=COMMIT)[0], 200)
        self.assertEqual(post(s, repository_id="")[0], 403)
    def test_A_renamed_or_recycled_repository_name_is_refused(self):
        s, gh = make(); self.assertEqual(post(s)[0], 200)
        self.assertEqual(post(s, receipt(created_at="2"), repository_id="1234")[0], 403)
    def test_B_policy_comes_from_the_default_branch_never_a_branch_the_author_chose(self):
        s, gh = make(); gh.policy = json.dumps({"schema": P.POLICY, "unknown": "block"})
        post(s, receipt("UNKNOWN", base="lax")); self.assertEqual(gh.checks[-1][4], "failure")
        self.assertEqual(set(gh.refs), {"main"})
    def test_C_run_order_never_moves_backwards(self):
        s, _ = make(); r = receipt()
        post(s, r, run_id=9); post(s, r, run_id=3)
        self.assertEqual(s.store.q("select run_order from receipts")[0][0], 9001)
    def test_D_app_factory_runs_under_uvicorn_and_fails_at_startup_without_config(self):
        import os, uvicorn
        from unittest import mock
        pem = KEY.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError): uvicorn.Config("controlplane.service.asgi:create_app", factory=True).load()   # startup, not first request
        env = {"AGENTVOW_CP_APP_ID": "1", "AGENTVOW_CP_PRIVATE_KEY": pem, "AGENTVOW_CP_WEBHOOK_SECRET": "x", "AGENTVOW_CP_TRUSTED_WORKFLOWS": WF, "AGENTVOW_CP_AUDIENCE": "a", "AGENTVOW_CP_DB": ":memory:"}
        with mock.patch.dict(os.environ, env, clear=True):
            cfg = uvicorn.Config("controlplane.service.asgi:create_app", factory=True); cfg.load()
        self.assertEqual(cfg.interface, "asgi3")   # the old lazy `app(scope, receive, send)` function was detected as asgi2 and failed every request
    def test_F_object_ids_and_names_are_strict(self):
        s, gh = make()
        for bad in ("abc/../../../../pulls/1?x=", "A" * 40, "g" * 40, "a" * 39):
            self.assertEqual(post(s, receipt(commit=bad))[0], 422)
            self.assertEqual(post(s, receipt(git_tree=bad))[0], 422)
        self.assertEqual(post(s, receipt(repo="o/n/../x"))[0], 422)
        self.assertIsNone(GitHub("1", KEY.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()), lambda *a: (500, b"")).commit_tree("o/n", "../x"))
    def test_G1_unresolvable_default_branch_blocks_instead_of_defaulting(self):
        s, gh = make(); gh.branch_ok = False
        post(s); self.assertEqual(gh.checks[-1][4], "failure")
    def test_G2_odd_policy_listing_and_odd_signature_do_not_crash(self):
        def t(method, url, hdr, body):
            if url.endswith("/installation"): return 200, b'{"id": 3}'
            if "access_tokens" in url: return 201, b'{"token": "tok"}'
            return 200, b'[{"name": "policy.json"}]'   # the path is a directory
        gh = GitHub("12", KEY.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()), t)
        with self.assertRaises(GitHubError): gh.file_at("o/n", ".agentvow/policy.json", "c" * 40)
        s, _ = make(); self.assertEqual(s.webhook({"x-hub-signature-256": "sha256=\u00e9\u00e9", "x-github-event": "ping"}, b"{}")[0], 401)
    def test_G2_unexpected_exception_fails_closed(self):
        s, gh = make(); s.store.acks = lambda *a: (_ for _ in ()).throw(RuntimeError("bug"))
        self.assertEqual(post(s)[0], 500); self.assertEqual(gh.checks[-1][4], "failure")
    def test_H_concurrent_first_publishes_make_one_check_run(self):
        import threading
        s, gh = make(); made = []
        orig = gh.set_check
        def slow(repo, sha, name, status, conclusion, title, summary, check_id=None):
            time.sleep(0.05); made.append(check_id); return orig(repo, sha, name, status, conclusion, title, summary, check_id)
        gh.set_check = slow
        ts = [threading.Thread(target=post, args=(s, receipt(created_at=str(i)))) for i in range(4)]
        [t.start() for t in ts]; [t.join() for t in ts]
        self.assertEqual(made.count(None), 1)
    def test_I_reopen_does_not_reset_a_finished_check(self):
        s, gh = make(); post(s)
        hook(s, "pull_request", {**Hooks.PR, "action": "reopened"}); self.assertEqual(gh.checks[-1][4], "success")
    def test_J_acknowledgement_needs_the_receipt_id_and_is_not_replayable_or_self_served(self):
        s, gh = make(); gh.policy = json.dumps({"schema": P.POLICY, "acknowledgers": ["alice", "bob"]}); post(s, receipt("UNKNOWN"))
        rid = s.store.latest_receipts("o/n", COMMIT)[0][0]
        c = lambda body, login="alice": {"action": "created", "repository": {"full_name": "o/n"}, "issue": {"number": 7, "pull_request": {"url": "u"}}, "comment": {"body": body, "user": {"login": login, "type": "User"}}}
        hook(s, "issue_comment", c("/agentvow acknowledge")); self.assertEqual(gh.checks[-1][4], "action_required")      # no id: refused
        hook(s, "issue_comment", c(f"/agentvow acknowledge {rid[:12]}", "bob")); self.assertEqual(gh.checks[-1][4], "action_required")   # bob authored the PR
        body = json.dumps(c(f"/agentvow acknowledge {rid[:12]}")).encode()
        sig = "sha256=" + hmac.new(b"s3cret", body, hashlib.sha256).hexdigest(); h = {"x-hub-signature-256": sig, "x-github-event": "issue_comment", "x-github-delivery": "d1"}
        self.assertEqual(s.webhook(h, body)[1].get("decision"), "allow")
        self.assertEqual(s.webhook(h, body)[1].get("ignored"), "delivery already processed")
    def test_K_quota_counts_only_stored_receipts_and_refusals_do_not_burn_it(self):
        s, gh = make(monthly_receipts={"free": 2, "team": 9, "business": 9}, per_minute=1000)
        codes = [post(s, receipt(created_at=str(i)))[0] for i in range(6)]
        self.assertEqual(codes, [200, 200, 429, 429, 429, 429]); self.assertEqual(s.store.usage("o/n")[0], 2)
        self.assertEqual(post(s, receipt(created_at="0"))[0], 200)   # an already stored receipt is not counted again
    def test_L_rate_limiter_memory_is_bounded(self):
        from controlplane.service.core import RateLimiter
        t = [0.0]; rl = RateLimiter(5, now=lambda: t[0], max_keys=50)
        for i in range(500): rl.ok(f"k{i}"); t[0] += 1
        self.assertLessEqual(len(rl.hits), 100)
    def test_L_jwks_failure_is_not_retried_every_request(self):
        n = []; t = [1000.0]
        def bad(): n.append(1); raise OSError("down")
        v = OidcVerifier("agentvow", bad, now=lambda: t[0])
        for _ in range(5):
            with self.assertRaises(Exception): v.verify(token(claims(exp=t[0] + 99), kid="q"))
        self.assertEqual(len(n), 1)
    def test_M_cli_zero_days_is_not_permanent_and_keys_are_not_silently_replaced(self):
        import tempfile
        from controlplane.service import cli
        db = tempfile.mkdtemp() + "/x.db"
        with self.assertRaises(SystemExit): cli.main(["--db", db, "set-plan", "o/n", "team", "--days", "0"])
        self.assertEqual(cli.main(["--db", db, "issue-key", "o/n"]), 0)
        with self.assertRaises(SystemExit): cli.main(["--db", db, "issue-key", "o/n"])
        self.assertEqual(cli.main(["--db", db, "issue-key", "o/n", "--rotate"]), 0)


class SecondReview(unittest.TestCase):
    """Regression tests for the second adversarial review (docs/review/CONTROLPLANE_REVIEW_2026-10-22.md, second round)."""
    def test_1_a_later_push_run_cannot_hide_a_pull_request_contradiction(self):
        s, gh = make(); post(s, receipt("CONTRADICTED"), run_id=5)
        gh.policy = json.dumps({"schema": P.POLICY, "no_claims": "allow"})
        push = receipt(pr=None); push["claims"] = []
        code, o = post(s, push, event_name="push", sha=COMMIT, run_id=9)
        self.assertEqual(code, 200); self.assertEqual(gh.checks[-1][4], "failure")
        self.assertEqual(len(o["decision"]["receipts"]), 2)
    def test_2_a_slow_acknowledgement_cannot_overwrite_a_newer_result(self):
        import threading
        s, gh = make(); gh.policy = json.dumps({"schema": P.POLICY, "acknowledgers": ["alice"]}); post(s, receipt("UNKNOWN"), run_id=1)
        rid = s.store.latest_receipts("o/n", COMMIT)[0][0]
        orig = s.decide; stale = threading.Event()
        def slow(*a, **k):
            r = orig(*a, **k)
            if r and r["decision"] == "allow":   # the acknowledgement has read and decided; its (soon stale) result waits before reaching GitHub
                stale.set(); time.sleep(0.4)
            return r
        s.decide = slow
        ev = {"action": "created", "repository": {"full_name": "o/n"}, "issue": {"number": 7, "pull_request": {"url": "u"}}, "comment": {"body": f"/agentvow acknowledge {rid[:12]}", "user": {"login": "alice", "type": "User"}}}
        t = threading.Thread(target=hook, args=(s, "issue_comment", ev)); t.start()
        stale.wait(2); post(s, receipt("UNKNOWN", created_at="2"), run_id=2); t.join()
        self.assertEqual(gh.checks[-1][4], "action_required")   # run 2 is not acknowledged and must be what GitHub ends up showing
    def test_3_a_failed_publish_is_remembered_and_retried(self):
        s, gh = make(); post(s)
        orig = gh.set_check; gh.set_check = lambda *a, **k: (_ for _ in ()).throw(GitHubError("503", 503))
        self.assertEqual(post(s, receipt("CONTRADICTED", created_at="2"), run_id=9)[0], 502)
        self.assertEqual(s.store.dirty(), [("o/n", COMMIT)])
        gh.set_check = orig; s.reconcile()
        self.assertEqual(gh.checks[-1][4], "failure"); self.assertEqual(s.store.dirty(), [])
    def test_4_check_says_it_is_under_the_current_policy_and_audit_lists_only_counted_acks(self):
        s, gh = make(); gh.policy = json.dumps({"schema": P.POLICY, "acknowledgers": ["alice"]}); post(s, receipt("UNKNOWN"))
        rid = s.store.latest_receipts("o/n", COMMIT)[0][0]; s.store.add_ack("o/n", rid, "mallory", "x")   # an acknowledgement from someone the policy does not list
        k = s.store.issue_key("o/n")
        self.assertEqual(s.audit("o/n", {"authorization": "Bearer " + k})[1]["records"][0]["acknowledged_by"], [])
        self.assertIn("policy in force now", s.check("o/n", COMMIT)[1]["evaluated"])
    def test_5_a_failed_delivery_is_processed_again_on_redelivery(self):
        s, gh = make(); gh.policy = json.dumps({"schema": P.POLICY, "acknowledgers": ["alice"]}); post(s, receipt("UNKNOWN"))
        rid = s.store.latest_receipts("o/n", COMMIT)[0][0]
        body = json.dumps({"action": "created", "repository": {"full_name": "o/n"}, "issue": {"number": 7, "pull_request": {"url": "u"}}, "comment": {"body": f"/agentvow acknowledge {rid[:12]}", "user": {"login": "alice", "type": "User"}}}).encode()
        h = {"x-hub-signature-256": "sha256=" + hmac.new(b"s3cret", body, hashlib.sha256).hexdigest(), "x-github-event": "issue_comment", "x-github-delivery": "d9"}
        orig = gh.permission; gh.permission = lambda *a: (_ for _ in ()).throw(GitHubError("502", 502))
        self.assertEqual(s.webhook(h, body)[0], 502)
        gh.permission = orig
        self.assertEqual(s.webhook(h, body)[1].get("decision"), "allow")
    def test_6_an_untrusted_token_cannot_claim_a_repository_name(self):
        s, gh = make()
        self.assertEqual(post(s, repository_id="666", job_workflow_ref="evil/wf/.github/workflows/x.yml@refs/heads/main")[0], 403)
        self.assertEqual(post(s)[0], 200)   # the real repository (id 99) is not locked out
        s.store.unbind_repo("o/n"); self.assertTrue(s.store.bind_repo_id("o/n", "5"))
    def test_6b_empty_or_missing_repository_id_is_refused_for_a_new_name(self):
        s, _ = make(); self.assertEqual(post(s, repository_id="")[0], 403)
        self.assertEqual(post(s, repository_id=None)[0], 403)
    def test_7_many_claims_are_capped_keeping_the_worst_and_a_bad_file_does_not_crash(self):
        d = {"status": "x", "commit": COMMIT, "unexamined": 0, "findings": [{"kind": f"k{i}", "verdict": "SUPPORTED_BY_PRIOR_EVIDENCE", "meta": {}} for i in range(300)] + [{"kind": "late", "verdict": "CONTRADICTED", "meta": {}}], "pack": {}}
        r = P.build_receipt(d, "o/n", TREE, "main", 7)
        self.assertIsNone(P.validate_receipt(r)); self.assertEqual(r["claims"][0]["verdict"], "CONTRADICTED"); self.assertEqual(r["claims"][-1]["verdict"], "UNKNOWN")
        def t(method, url, hdr, body):
            if url.endswith("/installation"): return 200, b'{"id": 3}'
            if "access_tokens" in url: return 201, b'{"token": "tok"}'
            return 200, b'{"type": "file", "encoding": "base64", "content": "!!!not base64"}'
        gh = GitHub("12", KEY.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()), t)
        with self.assertRaises(GitHubError): gh.file_at("o/n", "p", "c" * 40)
    def test_8_branch_names_with_slashes_are_not_encoded(self):
        seen = []
        def t(method, url, hdr, body):
            seen.append(url)
            if url.endswith("/installation"): return 200, b'{"id": 3}'
            if "access_tokens" in url: return 201, b'{"token": "tok"}'
            return 200, ('{"object": {"sha": "%s"}}' % ("d" * 40)).encode()
        gh = GitHub("12", KEY.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()), t)
        self.assertEqual(gh.branch_sha("o/n", "release/1.x"), "d" * 40); self.assertTrue(seen[-1].endswith("/git/ref/heads/release/1.x"))
        gh2 = GitHub("12", KEY.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()), lambda m, u, h, b: (404, b"{}") if "/git/ref/" in u else t(m, u, h, b))
        with self.assertRaises(GitHubError): gh2.branch_sha("o/n", "gone")   # a missing branch is an error, never 'no policy'
    def test_hex_strictness_is_in_the_schema_itself(self):
        for bad in ("A" * 40, "g" * 40, "a" * 39, "a/../b"):
            self.assertIsNotNone(P.validate_receipt({**receipt(), "commit": bad})); self.assertIsNotNone(P.validate_receipt({**receipt(), "git_tree": bad}))
        for ok in ("a" * 40, "a" * 64):
            self.assertIsNone(P.validate_receipt({**receipt(), "commit": ok}))
        self.assertIsNone(P.validate_receipt({**receipt(), "repo": "foo.bar/.github"})); self.assertIsNotNone(P.validate_receipt({**receipt(), "repo": "o/n/../x"}))
    def test_every_refusal_of_an_acknowledgement_fires_for_its_own_reason(self):
        s, gh = make(); gh.policy = json.dumps({"schema": P.POLICY, "acknowledgers": ["alice"]}); post(s, receipt("UNKNOWN"))
        rid = s.store.latest_receipts("o/n", COMMIT)[0][0]
        c = lambda login="alice", typ="User", rid_=rid[:12]: {"action": "created", "repository": {"full_name": "o/n"}, "issue": {"number": 7, "pull_request": {"url": "u"}}, "comment": {"body": f"/agentvow acknowledge {rid_} {login}{typ}{gh.perm}", "user": {"login": login, "type": typ}}}   # varied text: identical bodies share a delivery id here
        self.assertEqual(hook(s, "issue_comment", c("mallory"))[1]["refused"], "not a listed acknowledger")
        self.assertEqual(hook(s, "issue_comment", c(typ="Bot"))[1]["ignored"], "not a person")
        self.assertEqual(hook(s, "issue_comment", c(rid_="0" * 12))[1]["refused"], "receipt id mismatch")
        gh.perm = "read"; self.assertEqual(hook(s, "issue_comment", c())[1]["refused"], "no write access")
        gh.perm = "write"; self.assertEqual(hook(s, "issue_comment", c())[1]["decision"], "allow")
    def test_an_acknowledgement_of_another_receipt_does_not_count_and_cannot_clear_a_contradiction(self):
        s, gh = make(); gh.policy = json.dumps({"schema": P.POLICY, "acknowledgers": ["alice"]}); post(s, receipt("CONTRADICTED"))
        rid = s.store.latest_receipts("o/n", COMMIT)[0][0]
        ev = {"action": "created", "repository": {"full_name": "o/n"}, "issue": {"number": 7, "pull_request": {"url": "u"}}, "comment": {"body": f"/agentvow acknowledge {rid[:12]}", "user": {"login": "alice", "type": "User"}}}
        hook(s, "issue_comment", ev); self.assertEqual(gh.checks[-1][4], "failure")


class Lifecycle(unittest.TestCase):
    def inst(self, s, ev, action, **extra):
        body = json.dumps({"action": action, "installation": {"id": 5, "account": {"login": "o"}}, **extra}).encode()
        return s.webhook({"x-hub-signature-256": "sha256=" + hmac.new(b"s3cret", body, hashlib.sha256).hexdigest(), "x-github-event": ev}, body)
    def test_account_plan_covers_its_repositories_and_the_repository_plan_wins(self):
        s, _ = make(); self.assertEqual(s.store.plan("o/n"), "free")
        s.store.set_plan("o", "team"); self.assertEqual(s.store.plan("o/n"), "team"); self.assertEqual(s.store.plan("x/n"), "free")
        s.store.set_plan("o/n", "business"); self.assertEqual(s.store.plan("o/n"), "business")
        s.store.set_plan("o/n", "free", time.time() - 5); self.assertEqual(s.store.plan("o/n"), "team")   # an ended repository plan falls back to the account's
    def test_install_lifecycle_and_erasure_after_the_grace_period(self):
        s, gh = make(); post(s); k = s.store.issue_key("o/n"); s.store.set_plan("o/n", "team")
        self.assertEqual(self.inst(s, "installation", "created", repositories=[{"full_name": "o/n"}, {"full_name": "../evil"}])[0], 200)
        self.assertEqual(s.store.stats()["installations"], 1)
        self.assertEqual(self.inst(s, "installation_repositories", "removed", repositories_removed=[{"full_name": "o/n"}])[0], 200)
        gh.app_installed = False
        self.assertEqual(s.maintain()["repositories_erased"], 0)   # first seen gone: inside the grace period
        self.assertEqual(len(s.audit("o/n", {"authorization": "Bearer " + k})[1]["records"]), 1)
        s.store.q("update gone_since set since = ?", time.time() - 40 * 86400)
        self.assertEqual(s.maintain()["repositories_erased"], 1)
        self.assertEqual(s.store.receipts("o/n"), []); self.assertFalse(s.store.key_ok("o/n", k)); self.assertEqual(s.store.plan("o/n"), "free")
        self.assertEqual(self.inst(s, "installation", "deleted")[0], 200)
    def test_malformed_install_payloads_are_refused_not_crashing(self):
        s, _ = make()
        self.assertEqual(s.webhook({"x-hub-signature-256": "sha256=" + hmac.new(b"s3cret", b"[]", hashlib.sha256).hexdigest(), "x-github-event": "installation"}, b"[]")[0], 200)
        self.assertEqual(self.inst(s, "installation", "created", installation={"id": "x"})[0], 400)
    def test_retention_follows_the_plan(self):
        s, _ = make(); post(s); post(s, receipt(created_at="2"))
        s.store.q("update receipts set received = ?", time.time() - 40 * 86400)
        self.assertEqual(s.maintain()["receipts_expired"], 2)   # free: 30 days
        post(s, receipt(created_at="3")); s.store.set_plan("o/n", "team"); s.store.q("update receipts set received = ?", time.time() - 40 * 86400)
        self.assertEqual(s.maintain()["receipts_expired"], 0)   # team: 365 days
    def test_dashboard_needs_the_key_escapes_everything_and_keeps_the_key_out_of_urls(self):
        s, gh = make(); post(s, receipt(created_at="2")); k = s.store.issue_key("o/n")
        self.assertEqual(s.dashboard("o/n", "wrong")[0], 401); self.assertEqual(s.dashboard("o/n", "")[0], 401)
        code, page = s.dashboard("o/n", k); self.assertEqual(code, 200); self.assertIn("allow", page); self.assertNotIn(k, page)
        evil = receipt(created_at="3"); evil["not_reproduced"] = ["<script>alert(1)</script>", "a|b"]
        post(s, evil); page = s.dashboard("o/n", k)[1]
        self.assertNotIn("<script>alert", page); self.assertIn("&lt;script&gt;", page)
        from starlette.testclient import TestClient
        from controlplane.service.asgi import make_app
        c = TestClient(make_app(s))
        self.assertEqual(c.get("/dashboard").status_code, 200)
        r = c.post("/dashboard", data={"repo": "o/n", "key": k}); self.assertEqual(r.status_code, 200); self.assertEqual(r.headers["cache-control"], "no-store"); self.assertIn("default-src 'none'", r.headers["content-security-policy"])
        self.assertEqual(c.post("/dashboard", data={"repo": "o/n", "key": "nope"}).status_code, 401)
        self.assertEqual(c.post("/dashboard", content=b"x" * 5000).status_code, 413)
    def test_backup_is_a_consistent_private_copy_and_cli_commands_work(self):
        import tempfile, os, stat
        from controlplane.service import cli
        s, _ = make(); post(s)
        d = tempfile.mkdtemp(); db = d + "/live.db"
        from controlplane.service.store import Store
        live = Store(db); live.add_receipt("o/n", "id", "a" * 40, None, {"x": 1}, 1)
        self.assertEqual(cli.main(["--db", db, "backup", d + "/b.db"]), 0); self.assertEqual(stat.S_IMODE(os.stat(d + "/b.db").st_mode), 0o600)
        self.assertEqual(Store(d + "/b.db").stats()["receipts"], 1)
        self.assertEqual(cli.main(["--db", db, "set-plan", "o", "team"]), 0); self.assertEqual(Store(db).plan("o/anything"), "team")
        self.assertEqual(cli.main(["--db", db, "erase", "o/n"]), 0); self.assertEqual(Store(db).stats()["receipts"], 0)
        self.assertEqual(cli.main(["--db", db, "stats"]), 0); self.assertEqual(cli.main(["--db", db, "maintain"]), 0)


class ThirdReview(unittest.TestCase):
    """Regression tests for the third adversarial review (new lifecycle, retention, dashboard and helper code)."""
    def test_C1_a_lapsed_plan_never_deletes_the_audit_trail(self):
        s, _ = make(); post(s); s.store.set_plan("o/n", "team", time.time() - 5)   # ended yesterday: a late invoice
        s.store.q("update receipts set received = ?", time.time() - 100 * 86400)
        self.assertEqual(s.store.plan("o/n"), "free"); self.assertEqual(s.store.retention_plan("o/n"), "team")
        self.assertEqual(s.maintain()["receipts_expired"], 0)
    def test_C2_background_pass_survives_failures_and_runs_maintenance_when_due_even_after_restarts(self):
        from controlplane.service.asgi import background_pass
        s, _ = make(); calls = []
        s.reconcile = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
        orig = s.maintain; s.maintain = lambda: (calls.append(1), orig())[1]
        t = [1000000.0]; background_pass(s, now=lambda: t[0]); self.assertEqual(len(calls), 1)   # reconcile failed, maintenance still ran
        background_pass(s, now=lambda: t[0] + 100); self.assertEqual(len(calls), 1)               # not due again (the time is persisted: a restart does not reset it)
        background_pass(s, now=lambda: t[0] + 86401); self.assertEqual(len(calls), 2)
        s.maintain = lambda: (_ for _ in ()).throw(RuntimeError("boom")); background_pass(s, now=lambda: t[0] + 3 * 86400)   # must not raise
    def test_C3_erasure_follows_what_github_says_now_not_webhook_order(self):
        s, gh = make(); post(s); inst = TestLifecycleHelper(s)
        inst("installation_repositories", "removed", 6, repositories_removed=[{"full_name": "o/n"}])   # a stale removal of ANOTHER installation
        s.store.record_install(5, "o", ["o/n"]); inst("installation_repositories", "removed", 6, repositories_removed=[{"full_name": "o/n"}])
        self.assertIsNone(s.store.q("select removed_at from install_repos where repo='o/n'")[0][0])   # scoped by installation id
        gh.app_installed = None; s.maintain(); self.assertEqual(s.store.q("select count(*) from gone_since")[0][0], 0)   # unknown: nothing changes
        gh.app_installed = False; self.assertEqual(s.maintain()["repositories_erased"], 0)
        gh.app_installed = True; s.maintain(); self.assertEqual(s.store.q("select count(*) from gone_since")[0][0], 0)   # reinstalled: the clock resets
        s.store.q("delete from install_repos")   # a repository whose installation webhook was never received
        gh.app_installed = False; s.maintain(); s.store.q("update gone_since set since = ?", time.time() - 40 * 86400)
        self.assertEqual(s.maintain()["repositories_erased"], 1); self.assertEqual(s.store.receipts("o/n"), [])
    def test_C3_an_installation_cannot_name_another_accounts_repositories(self):
        s, _ = make(); TestLifecycleHelper(s)("installation", "created", 5, repositories=[{"full_name": "victim/repo"}, {"full_name": "o/mine"}])
        self.assertEqual([r for (r,) in s.store.q("select repo from install_repos")], ["o/mine"])
    def test_C4_plans_are_case_insensitive(self):
        s, _ = make(); s.store.set_plan("Acme", "team"); self.assertEqual(s.store.plan("acme/x"), "team"); self.assertEqual(s.store.plan("ACME/X"), "team")
    def test_C6_docker_context_excludes_secrets_and_everything_but_the_two_packages(self):
        d = (Path(__file__).resolve().parents[1] / ".dockerignore").read_text().splitlines()
        self.assertIn("*", d); self.assertIn("**/secrets", d); self.assertIn("!agentvow", d); self.assertIn("!controlplane", d)
        self.assertLess(d.index("!controlplane"), d.index("**/secrets"))   # the exclusion comes after the re-inclusion, so it wins
    def test_C7_glob_characters_in_agentvow_names_do_not_touch_the_tracked_policy(self):
        import tempfile, subprocess as sp
        from agentvow import reality
        d = Path(tempfile.mkdtemp()); g = lambda *a: sp.run(["git", "-C", str(d), *a], check=True, capture_output=True, text=True).stdout.strip()
        g("init", "-q", "-b", "main"); g("config", "user.email", "a@b"); g("config", "user.name", "t"); (d / ".agentvow").mkdir(); (d / ".agentvow" / "policy.json").write_text("{}"); (d / "a.py").write_text("x=1\n")
        g("add", "-A"); g("commit", "-qm", "c")
        for n in ("*", "p?licy.json", "[a-z]olicy.json"): (d / ".agentvow" / n).write_text("local state")
        self.assertEqual(reality.git_tree_hash(d), g("rev-parse", "HEAD^{tree}"))
    def test_P1_dashboard_is_capped_and_reads_are_rate_limited(self):
        s, _ = make(per_minute=1000, dashboard_rows=3); k = s.store.issue_key("o/n")
        for i in range(6): post(s, receipt(created_at=str(i)), run_id=i)
        page = s.dashboard("o/n", k)[1]; self.assertEqual(page.count("<tr><td>"), 3); self.assertIn("latest 3 of 6", page)
        s2, _ = make(per_minute=2); k2 = s2.store.issue_key("o/n"); post(s2)
        codes = [s2.audit("o/n", {"authorization": "Bearer " + k2})[0] for _ in range(4)]; self.assertIn(429, codes)
    def test_P2_register_helper_refuses_other_host_names(self):
        import tempfile, threading, urllib.request, urllib.error
        from http.server import HTTPServer
        from controlplane.service import register_app as R
        mh, page, state, on_app, done, hosts = R.main(["--tunnel", "https://t.example", "--repo", "u/r", "--workflow-sha", "c" * 40, "--out", tempfile.mkdtemp() + "/x", "--port", "0"], convert_fn=lambda c: {}, serve=False)
        srv = HTTPServer(("127.0.0.1", 0), mh(page, state, on_app, ())); threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{srv.server_address[1]}/", headers={"Host": "evil.example"})
            with self.assertRaises(urllib.error.HTTPError) as e: urllib.request.urlopen(req)
            self.assertEqual(e.exception.code, 403)
        finally:
            srv.shutdown()
        with self.assertRaises(SystemExit): R.main(["--tunnel", "https://t.example", "--repo", "u/r", "--workflow-sha", "v1", "--out", "x"], serve=False)   # a tag is not a sha
        with self.assertRaises(SystemExit): R.main(["--tunnel", "https://t.example", "--repo", "bad repo; rm", "--workflow-sha", "c" * 40, "--out", "x"], serve=False)
    def test_P3_register_helper_replaces_existing_files_and_links_with_private_ones(self):
        import tempfile, os, stat
        from controlplane.service import register_app as R
        d = tempfile.mkdtemp() + "/o"; os.makedirs(d, mode=0o755); target = d + "/elsewhere"; open(target, "w").write("keep")
        os.symlink(target, d + "/app.private-key.pem"); open(d + "/cp.env", "w").write("old"); os.chmod(d + "/cp.env", 0o644)
        R.save(d, "u/r", {"id": 1, "pem": "PEM", "webhook_secret": "WS"}, "aud", "u/r/.github/workflows/gate.yml@refs/tags/v1")
        self.assertEqual(open(target).read(), "keep")   # not written through the link
        for f in ("app.private-key.pem", "cp.env"): self.assertEqual(stat.S_IMODE(os.lstat(f"{d}/{f}").st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(d).st_mode), 0o700)
    def test_P5_erase_removes_every_table_and_retention_removes_acknowledgements(self):
        s, gh = make(); gh.policy = json.dumps({"schema": P.POLICY, "acknowledgers": ["alice"]}); post(s, receipt("UNKNOWN")); k = s.store.issue_key("o/n")
        rid = s.store.latest_receipts("o/n", COMMIT)[0][0]; s.store.add_ack("o/n", rid, "alice", "x"); s.store.mark_dirty("o/n", COMMIT); s.store.set_plan("o/n", "team")
        s.store.q("update receipts set received = ?", time.time() - 40 * 86400); self.assertEqual(s.maintain()["receipts_expired"], 0)   # team keeps 365 days
        s.store.set_plan("o/n", "free"); s.store.q("delete from plans")
        self.assertEqual(s.maintain()["receipts_expired"], 1); self.assertEqual(s.store.acks("o/n", rid), [])   # free: 30 days; acknowledgements go with their receipt
        post(s, receipt("UNKNOWN", created_at="9")); s.store.mark_dirty("o/n", COMMIT)
        s.store.erase_repo("o/n")
        for t in ("receipts", "checks", "acks", "plans", "keys", "usage", "repo_ids", "dirty", "install_repos", "gone_since"):
            self.assertEqual(s.store.q(f"select count(*) from {t} where repo='o/n'")[0][0], 0, t)
    def test_P6_dashboard_security_headers(self):
        from starlette.testclient import TestClient
        from controlplane.service.asgi import make_app
        r = TestClient(make_app(make()[0])).get("/dashboard"); csp = r.headers["content-security-policy"]
        for part in ("default-src 'none'", "form-action 'self'", "frame-ancestors 'none'"): self.assertIn(part, csp)
        self.assertEqual(r.headers["referrer-policy"], "no-referrer"); self.assertEqual(r.headers["x-frame-options"], "DENY")
    def test_deliveries_are_pruned_by_maintenance(self):
        s, _ = make(); s.store.record_delivery("old"); s.store.q("update deliveries set at = ?", time.time() - 20 * 86400)
        s.store.record_delivery("new"); s.maintain(); self.assertFalse(s.store.delivery_seen("old")); self.assertTrue(s.store.delivery_seen("new"))


def TestLifecycleHelper(s):
    def send(ev, action, iid=5, **extra):
        body = json.dumps({"action": action, "installation": {"id": iid, "account": {"login": "o"}}, **extra}).encode()
        return s.webhook({"x-hub-signature-256": "sha256=" + hmac.new(b"s3cret", body, hashlib.sha256).hexdigest(), "x-github-event": ev}, body)
    return send


class ImmutablePins(unittest.TestCase):
    def test_a_tag_or_branch_pin_is_refused_at_construction_and_at_startup(self):
        import os, uvicorn
        from unittest import mock
        with self.assertRaises(ValueError): Service(Config(trusted_workflows=frozenset({"o/g/.github/workflows/gate-service.yml@refs/tags/v1"}), webhook_secret=b"x"), None, None, Store())
        with self.assertRaises(ValueError): Service(Config(trusted_workflows=frozenset({"o/g/.github/workflows/gate-service.yml@" + "c" * 39}), webhook_secret=b"x"), None, None, Store())
        Service(Config(trusted_workflows=frozenset({"o/g/.github/workflows/gate-service.yml@refs/tags/v1"}), webhook_secret=b"x", allow_mutable_refs=True), None, None, Store())   # development only
        pem = KEY.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
        env = {"AGENTVOW_CP_APP_ID": "1", "AGENTVOW_CP_PRIVATE_KEY": pem, "AGENTVOW_CP_WEBHOOK_SECRET": "x", "AGENTVOW_CP_TRUSTED_WORKFLOWS": "o/g/.github/workflows/gate-service.yml@refs/tags/v1", "AGENTVOW_CP_AUDIENCE": "a", "AGENTVOW_CP_DB": ":memory:"}
        from controlplane.service.asgi import build_service
        with self.assertRaises(ValueError): build_service(env)
        build_service({**env, "AGENTVOW_CP_ALLOW_MUTABLE_REFS": "1"})
    def test_the_token_commit_claim_must_agree_with_the_pin_and_a_moved_workflow_is_refused(self):
        s, gh = make()
        self.assertEqual(post(s, job_workflow_sha="d" * 40)[0], 403)      # the ref string says one commit, the signed claim another
        self.assertEqual(post(s, job_workflow_sha=None)[0], 403)
        self.assertEqual(post(s, job_workflow_ref=WF.replace("c" * 40, "d" * 40), job_workflow_sha="d" * 40)[0], 403)   # a different commit of the same workflow file is not trusted
        self.assertEqual(post(s)[0], 200)


class FourthReview(unittest.TestCase):
    def test_the_sha_pin_pattern_is_strict(self):
        from controlplane.service.core import SHA_REF
        ok = "o/g/.github/workflows/gate-service.yml@" + "a" * 40
        self.assertTrue(SHA_REF.fullmatch(ok))
        for bad in (ok.replace("a" * 40, "A" * 40), ok + "a", ok[:-1], "o/g/.github/workflows/gate-service.yml@refs/heads/" + "a" * 40, ok + "\n", "o/g/workflows/x.yml@" + "a" * 40):
            self.assertFalse(SHA_REF.fullmatch(bad), bad)
    def test_receipts_from_an_older_agentvow_are_refused_whatever_the_workflow_says(self):
        s, gh = make(); old = receipt(); old["tool_version"] = "0.4.2"
        code, o = post(s, old); self.assertEqual(code, 422); self.assertIn("0.4.3", o["error"]); self.assertEqual(gh.checks, [])
        for bad in ("", "latest", None, "0.4"): self.assertEqual(post(s, {**receipt(created_at=str(bad)), "tool_version": bad})[0], 422, repr(bad))
        s2, _ = make(min_tool_version="0.4.2"); self.assertEqual(post(s2, old)[0], 200)
        newer = receipt(created_at="n"); newer["tool_version"] = "0.10.0"; self.assertEqual(post(s, newer)[0], 200)   # numeric, not text, comparison
    def test_policy_enums_and_provenance_types_are_checked(self):
        self.assertIsNotNone(P.validate_policy({"schema": P.POLICY, "partial_capture": "bogus"}))
        self.assertIsNone(P.validate_policy({"schema": P.POLICY, "partial_capture": "block"}))
        r = receipt(); r["claims"][0]["capture_authenticated"] = 1; self.assertIsNotNone(P.validate_receipt(r))
        r["claims"][0]["capture_authenticated"] = 0; self.assertIsNotNone(P.validate_receipt(r))
    def test_register_helper_without_a_sha_writes_a_placeholder_the_service_refuses_and_the_compose_secret_file(self):
        import tempfile, os, stat
        from controlplane.service import register_app as R
        d = tempfile.mkdtemp() + "/o"
        env = R.save(d, "u/r", {"id": 1, "pem": "PEM", "webhook_secret": "WS"}, "aud", "u/r/.github/workflows/gate-service.yml@<SET-THE-40-CHARACTER-SHA>")
        self.assertEqual(stat.S_IMODE(os.stat(d + "/webhook_secret").st_mode), 0o600); self.assertEqual(open(d + "/webhook_secret").read(), "WS")
        with self.assertRaises(ValueError): Service(Config(trusted_workflows=frozenset({"u/r/.github/workflows/gate-service.yml@<SET-THE-40-CHARACTER-SHA>"}), webhook_secret=b"x"), None, None, Store())


class PlainCheckText(unittest.TestCase):
    def test_the_check_run_carries_a_plain_title_and_explanation_for_each_decision(self):
        from agentvow import explain
        s, gh = make(); gh.policy = json.dumps({"schema": P.POLICY, "acknowledgers": ["alice"]})
        post(s, receipt("SUPPORTED_BY_PRIOR_EVIDENCE")); c = gh.checks[-1]
        self.assertEqual(c[5], explain.TITLES["allow"]); self.assertIn("nothing that needs a person's attention", c[6]); self.assertIn("What this does not show", c[6])
        post(s, receipt("UNKNOWN", created_at="2"), run_id=9); c = gh.checks[-1]
        rid = s.store.latest_receipts("o/n", COMMIT)[0][0]
        self.assertEqual(c[5], explain.TITLES["needs_acknowledgement"]); self.assertIn(f"/agentvow acknowledge {rid[:12]}", c[6]); self.assertIn("@alice", c[6])
        post(s, receipt("CONTRADICTED", created_at="3"), run_id=20); c = gh.checks[-1]
        self.assertEqual(c[5], explain.TITLES["block"]); self.assertIn("cannot be acknowledged away", c[6]); self.assertNotIn("/agentvow acknowledge", c[6])
    def test_an_unreadable_policy_is_explained_not_just_blocked(self):
        s, gh = make(); gh.fail_policy = True; post(s)
        self.assertIn("policy file could not be read", gh.checks[-1][6]); self.assertIn("Fix the policy file", gh.checks[-1][6])
    def test_the_acknowledgement_replies_are_plain(self):
        s, gh = make(); gh.policy = json.dumps({"schema": P.POLICY, "acknowledgers": ["alice"]}); post(s, receipt("UNKNOWN"))
        rid = s.store.latest_receipts("o/n", COMMIT)[0][0]
        ev = {"action": "created", "repository": {"full_name": "o/n"}, "issue": {"number": 7, "pull_request": {"url": "u"}}, "comment": {"body": f"/agentvow acknowledge {rid[:12]}", "user": {"login": "alice", "type": "User"}}}
        hook(s, "issue_comment", ev); self.assertIn("now allows this change", gh.comments[-1]); self.assertNotIn("Decision:", gh.comments[-1])


class Smoke(unittest.TestCase):
    def test_problems_lists_what_the_app_is_missing(self):
        from controlplane.service import smoke
        self.assertEqual(smoke.problems({"permissions": {"checks": "write", "contents": "read", "pull_requests": "write", "issues": "write", "metadata": "read"}, "events": ["pull_request", "issue_comment"]}), [])
        bad = smoke.problems({"permissions": {"checks": "read", "contents": "read"}, "events": ["pull_request"]})
        self.assertEqual(len(bad), 5); self.assertTrue(any("issue_comment" in b for b in bad))
    def test_main_reports_config_errors_and_bad_credentials(self):
        import io
        from controlplane.service import smoke
        out = io.StringIO(); self.assertEqual(smoke.main({}, out), 2); self.assertIn("CONFIG", out.getvalue())


class Register(unittest.TestCase):
    def test_manifest_flow_writes_secrets_private_and_rejects_wrong_state(self):
        import tempfile, os, threading, urllib.request, urllib.error, stat
        from http.server import HTTPServer
        from controlplane.service import register_app as R
        out = tempfile.mkdtemp() + "/x"
        make_handler, page, state, on_app, done, hosts = R.main(["--tunnel", "https://t.example", "--repo", "u/r", "--workflow-sha", "c" * 40, "--out", out, "--port", "0"], convert_fn=lambda code: {"id": 7, "name": "n", "slug": "n", "html_url": "https://github.com/apps/n", "pem": "PEM", "webhook_secret": "WS"}, serve=False)
        self.assertIn("https://t.example/v1/webhook", page); self.assertIn("pull_request", page); self.assertNotIn("WS", page)
        srv = HTTPServer(("127.0.0.1", 0), make_handler(page, state, on_app, ("127.0.0.1:%d" % 0,))); port = srv.server_address[1]; srv.RequestHandlerClass = make_handler(page, state, on_app, (f"127.0.0.1:{port}",))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            with self.assertRaises(urllib.error.HTTPError) as e: urllib.request.urlopen(f"http://127.0.0.1:{port}/callback?code=c&state=wrong")
            self.assertEqual(e.exception.code, 400); self.assertFalse(done)
            body = urllib.request.urlopen(f"http://127.0.0.1:{port}/callback?code=c&state={state}").read().decode()
        finally:
            srv.shutdown()
        self.assertNotIn("WS", body); self.assertNotIn("PEM", body)
        for f in ("app.private-key.pem", "cp.env"): self.assertEqual(stat.S_IMODE(os.stat(f"{out}/{f}").st_mode), 0o600)
        env = open(f"{out}/cp.env").read()
        self.assertIn("AGENTVOW_CP_APP_ID=7", env); self.assertIn("u/r/.github/workflows/gate-service.yml@" + "c" * 40, env)


class Hooks(unittest.TestCase):
    PR = {"action": "opened", "repository": {"full_name": "o/n"}, "pull_request": {"head": {"sha": COMMIT}}}
    def test_signature(self):
        s, gh = make()
        self.assertEqual(hook(s, "pull_request", self.PR, secret=b"wrong")[0], 401)
        self.assertEqual(s.webhook({"x-github-event": "pull_request"}, b"{}")[0], 401)
        self.assertEqual(gh.checks, [])
        s.cfg.webhook_secret = b""; self.assertEqual(hook(s, "pull_request", self.PR, secret=b"")[0], 401)
    def test_pr_open_creates_pending_check(self):
        s, gh = make(); self.assertEqual(hook(s, "pull_request", self.PR)[0], 200); self.assertEqual(gh.checks[-1][3:5], ("in_progress", None))
    def comment(self, body="/agentvow acknowledge", login="alice", typ="User"):
        return {"action": "created", "repository": {"full_name": "o/n"}, "issue": {"number": 7, "pull_request": {}}, "comment": {"body": body, "user": {"login": login, "type": typ}}}
    def setup_unknown(self):
        s, gh = make(); gh.policy = json.dumps({"schema": P.POLICY, "acknowledgers": ["alice"]}); post(s, receipt("UNKNOWN")); return s, gh
    def test_acknowledge_flow(self):
        s, gh = self.setup_unknown(); self.assertEqual(gh.checks[-1][4], "action_required")
        rid = s.store.latest_receipts("o/n", COMMIT)[0][0]
        self.assertEqual(hook(s, "issue_comment", self.comment(body=f"/agentvow acknowledge {rid[:12]}"))[1].get("decision"), "allow"); self.assertEqual(gh.checks[-1][4], "success")
    def test_acknowledge_refusals(self):
        s, gh = self.setup_unknown()
        for c in (self.comment(login="mallory"), self.comment(typ="Bot"), self.comment(body="please /agentvow acknowledge"), self.comment(body="/agentvow acknowledge deadbeef")):
            hook(s, "issue_comment", c)
        gh.perm = "read"; hook(s, "issue_comment", self.comment())
        self.assertEqual(gh.checks[-1][4], "action_required")
    def test_ack_cannot_clear_contradiction(self):
        s, gh = make(); gh.policy = json.dumps({"schema": P.POLICY, "acknowledgers": ["alice"]}); post(s, receipt("CONTRADICTED"))
        hook(s, "issue_comment", self.comment()); self.assertEqual(gh.checks[-1][4], "failure")
    def test_no_receipt_nothing_to_acknowledge(self):
        s, gh = make(); hook(s, "issue_comment", self.comment()); self.assertTrue(gh.comments and not gh.checks)


class Audit(unittest.TestCase):
    def test_tenant_isolation_and_csv_injection(self):
        s, gh = make(); post(s); ka = s.store.issue_key("o/n"); kb = s.store.issue_key("o/other")
        self.assertEqual(s.audit("o/n", {})[0], 401)
        self.assertEqual(s.audit("o/n", {"authorization": "Bearer " + kb})[0], 401)
        code, o = s.audit("o/n", {"authorization": "Bearer " + ka}); self.assertEqual((code, len(o["records"])), (200, 1))
        self.assertEqual(s.audit("o/other", {"authorization": "Bearer " + kb})[1]["records"], [])
        self.assertEqual(Service._cell("=cmd()"), "'=cmd()")
        self.assertIn("receipt_sha", s.audit("o/n", {"authorization": "Bearer " + ka}, "csv")[1]["csv"])


class GitHubClient(unittest.TestCase):
    def test_app_flow_and_policy_404(self):
        pem = KEY.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()); seen = []
        def t(method, url, hdr, body):
            seen.append((method, url, hdr["Authorization"][:6]))
            if url.endswith("/installation"): return 200, b'{"id": 3}'
            if "access_tokens" in url: return 201, b'{"token": "tok"}'
            if "/contents/" in url: return 404, b"{}"
            return 200, b'{"private": false, "default_branch": "main"}'
        gh = GitHub("12", pem, t)
        self.assertIsNone(gh.file_at("o/n", ".agentvow/policy.json", "main")); self.assertTrue(gh.repo_info("o/n")["default_branch"] == "main")
        self.assertEqual(seen[0][2], "Bearer"); self.assertEqual(sum("access_tokens" in u for _, u, _ in seen), 1)   # token cached
        gh2 = GitHub("12", pem, lambda *a: (500, b"")); 
        with self.assertRaises(GitHubError): gh2.file_at("o/n", "p", "main")


class Http(unittest.TestCase):
    def test_routes_and_fail_closed_config(self):
        from starlette.testclient import TestClient
        from controlplane.service.asgi import build_service, make_app
        with self.assertRaises(RuntimeError): build_service({})
        s, gh = make(); c = TestClient(make_app(s))
        self.assertEqual(c.get("/healthz").text, "ok")
        body = json.dumps(receipt()).encode()
        self.assertEqual(c.post("/v1/receipts", content=body).status_code, 401)
        r = c.post("/v1/receipts", content=body, headers={"Authorization": "Bearer " + bound(body)}); self.assertEqual(r.status_code, 200)
        self.assertEqual(c.post("/v1/receipts", content=b"x" * 70000, headers={"Authorization": "Bearer x"}).status_code, 413)
        self.assertEqual(c.post("/v1/webhook", content=b"{}").status_code, 401)
        self.assertEqual(c.get("/v1/check", params={"repo": "o/n", "commit": COMMIT}).status_code, 401)
        k = s.store.issue_key("o/n")
        self.assertEqual(c.get("/v1/check", params={"repo": "o/n", "commit": COMMIT}, headers={"Authorization": "Bearer " + k}).json()["conclusion"], "success")
        self.assertEqual(c.get("/v1/audit", params={"repo": "o/n"}).status_code, 401)


if __name__ == "__main__":
    unittest.main()
