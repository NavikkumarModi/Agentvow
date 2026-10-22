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

WF = "o/gate/.github/workflows/gate.yml@refs/tags/v1"
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
    c = {"iss": ISSUER, "aud": "agentvow", "exp": time.time() + 300, "repository": "o/n", "job_workflow_ref": WF, "event_name": "pull_request", "run_id": 5, "run_attempt": 1}
    c.update(o); return c


def receipt(verdict="SUPPORTED_BY_PRIOR_EVIDENCE", pr=7, **over):
    d = {"status": "x", "commit": COMMIT, "unexamined": 0, "findings": [{"kind": "tests_pass", "verdict": verdict, "meta": {}}], "pack": {"reproducibility": {"code": "both"}, "contexts": []}}
    r = P.build_receipt(d, "o/n", TREE, "main", pr); r.update(over); return r


class FakeGH:
    def __init__(self):
        self.tree, self.private, self.head, self.policy, self.perm = TREE, False, COMMIT, None, "write"
        self.checks, self.comments, self.fail_policy = [], [], False
    def repo_info(self, repo): return {"private": self.private, "default_branch": "main"}
    def commit_tree(self, repo, sha): return self.tree
    def pr_info(self, repo, n): return {"head_sha": self.head, "base_ref": "main", "state": "open"}
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


def post(svc, r=None, tok=None, body=None):
    r = r or receipt()
    return svc.post_receipt({"authorization": "Bearer " + (tok or token(claims()))}, body if body is not None else json.dumps(r).encode())


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
        self.assertEqual(post(s, tok=token(claims(repository="o/other")))[0], 403)
        self.assertEqual(post(s, tok=token(claims(job_workflow_ref="o/gate/.github/workflows/gate.yml@refs/heads/evil")))[0], 403)
        self.assertEqual(post(s, tok=token(claims(event_name="schedule")))[0], 403)
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
        s, gh = make(); post(s, receipt("CONTRADICTED"), tok=token(claims(run_id=9)))
        post(s, receipt("SUPPORTED_BY_PRIOR_EVIDENCE", created_at="2"), tok=token(claims(run_id=5)))   # older run arrives later
        self.assertEqual(s.check("o/n", COMMIT)[1]["conclusion"], "failure")
    def test_github_outage_is_502_not_success(self):
        s, gh = make(); gh.commit_tree = lambda *a: (_ for _ in ()).throw(GitHubError("down", 500))
        self.assertEqual(post(s)[0], 502); self.assertEqual(gh.checks, [])


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
        self.assertEqual(hook(s, "issue_comment", self.comment())[1].get("decision"), "allow"); self.assertEqual(gh.checks[-1][4], "success")
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
        self.assertEqual(c.post("/v1/receipts", content=json.dumps(receipt())).status_code, 401)
        r = c.post("/v1/receipts", content=json.dumps(receipt()), headers={"Authorization": "Bearer " + token(claims())}); self.assertEqual(r.status_code, 200)
        self.assertEqual(c.post("/v1/webhook", content=b"{}").status_code, 401)
        self.assertEqual(c.get("/v1/check", params={"repo": "o/n", "commit": COMMIT}).status_code, 401)
        k = s.store.issue_key("o/n")
        self.assertEqual(c.get("/v1/check", params={"repo": "o/n", "commit": COMMIT}, headers={"Authorization": "Bearer " + k}).json()["conclusion"], "success")
        self.assertEqual(c.get("/v1/audit", params={"repo": "o/n"}).status_code, 401)


if __name__ == "__main__":
    unittest.main()
