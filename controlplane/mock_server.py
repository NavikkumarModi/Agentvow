"""MOCK control plane (phase 0): the shape of the paid service, standard library only, NOT for production and not shipped in the wheel. It never executes customer code: it receives receipts that a
customer's own runner produced, checks who sent them and whether they are bound to the commit as GitHub has it, evaluates the repository's policy, records acknowledgements and answers "what should the
required check say for this commit". Phase 1 replaces three seams with real ones: `MockAuth` (RS256 verification of the GitHub Actions OIDC token against GitHub's published keys), `Oracle` (GitHub's API for
commit -> tree and for the pull request head) and `Store` (a managed database); and reads the policy from the BASE branch instead of `PUT /v1/policy`. Threat model: docs/CONTROLPLANE_THREAT_MODEL.md.

Endpoints (JSON): POST /v1/receipts (runner token) | PUT /v1/policy (admin token) | POST /v1/acks (user token) | GET /v1/check?repo=&commit= | GET /v1/audit?repo=&format=json|csv (admin token)."""
import base64
import csv
import hashlib
import hmac
import io
import json
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from agentvow import policy as policy_mod

MAX_BODY = 64 * 1024


def _b64(x: bytes) -> str:
    return base64.urlsafe_b64encode(x).rstrip(b"=").decode()


def _cell(v) -> str:
    """CSV cell safe against spreadsheet formula injection."""
    t = str(v)
    return "'" + t if t[:1] in ("=", "+", "-", "@", "\t", "\r") else t


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def make_token(secret: bytes, claims: dict) -> str:
    """Test helper: an HS256 token. (The real service verifies RS256 OIDC tokens from GitHub.)"""
    h, p = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()), _b64(json.dumps(claims).encode())
    return f"{h}.{p}.{_b64(hmac.new(secret, f'{h}.{p}'.encode(), hashlib.sha256).digest())}"


class MockAuth:
    def __init__(self, secret: bytes):
        self.secret = secret

    def verify(self, token: str):
        """-> claims or None. Rejects other algorithms (including "none"), bad signatures and expired tokens."""
        try:
            h, p, s = token.split(".")
            if json.loads(_unb64(h)).get("alg") != "HS256":
                return None
            if not hmac.compare_digest(_b64(hmac.new(self.secret, f"{h}.{p}".encode(), hashlib.sha256).digest()), s):
                return None
            claims = json.loads(_unb64(p))
        except (ValueError, TypeError, KeyError):
            return None
        return claims if isinstance(claims, dict) and isinstance(claims.get("exp"), (int, float)) and claims["exp"] > time.time() else None


class Oracle:
    """The seam to GitHub: what the platform itself says. `trees` maps (repo, commit) -> git tree hash."""
    def __init__(self, trees: dict):
        self.trees = trees

    def tree_of(self, repo: str, commit: str):
        return self.trees.get((repo, commit))


class Store:
    def __init__(self):
        self.db = sqlite3.connect(":memory:", check_same_thread=False)
        self.lock = threading.Lock()
        self.db.executescript("""create table receipts(id text, repo text, commit_sha text, body text, received real, run_order integer);
                                 create table policies(repo text primary key, body text);
                                 create table acks(receipt_sha text, by text, note text, at real);""")

    def q(self, sql, *a):
        with self.lock:
            cur = self.db.execute(sql, a)
            self.db.commit()
            return cur.fetchall()


class App:
    def __init__(self, auth, oracle, store=None, trusted_workflows=(), admin_token="admin", audience="agentvow-control-plane", events=("pull_request", "push", "workflow_dispatch")):
        """`trusted_workflows`: the EXACT `job_workflow_ref` values accepted, each with its pinned ref (for example
        "OWNER/REPO/.github/workflows/gate-service.yml@refs/tags/v0.4.0"); none by default, so nothing is accepted until configured."""
        self.auth, self.oracle, self.store = auth, oracle, store or Store()
        self.trusted, self.admin_token, self.audience, self.events = frozenset(trusted_workflows), admin_token, audience, frozenset(events)

    def _is_admin(self, headers) -> bool:
        return hmac.compare_digest(str(headers.get("Authorization", "")), f"Bearer {self.admin_token}")

    # ---- helpers
    def _claims(self, headers):
        h = headers.get("Authorization", "")
        return self.auth.verify(h[7:]) if h.startswith("Bearer ") else None

    def _policy(self, repo):
        r = self.store.q("select body from policies where repo=?", repo)
        return json.loads(r[0][0]) if r else None

    def _acks(self, rsha):
        return [{"schema": policy_mod.ACK, "receipt_sha": rsha, "by": b, "note": n, "at": str(a)} for b, n, a in self.store.q("select by, note, at from acks where receipt_sha=?", rsha)]

    def _decide(self, receipt):
        return policy_mod.evaluate(receipt, self._policy(receipt["repo"]), self._acks(policy_mod.sha(receipt)))

    # ---- routes
    def handle(self, method, path, headers, body=b""):
        u = urlparse(path)
        qs = {k: v[0] for k, v in parse_qs(u.query).items()}
        if len(body) > MAX_BODY:
            return 413, {"error": "body too large"}
        try:
            data = json.loads(body) if body else {}
        except ValueError:
            return 400, {"error": "not JSON"}
        route = (method, u.path)
        if route == ("POST", "/v1/receipts"):
            return self.post_receipt(headers, data)
        if route == ("PUT", "/v1/policy"):
            if not self._is_admin(headers):
                return 401, {"error": "admin token required"}
            bad = policy_mod.validate_policy(data.get("policy"))
            if bad or not isinstance(data.get("repo"), str):
                return 422, {"error": bad or "repo is required"}
            self.store.q("insert or replace into policies values(?,?)", data["repo"], json.dumps(data["policy"]))
            return 200, {"ok": True, "policy_sha": policy_mod.sha(data["policy"])}
        if route == ("POST", "/v1/acks"):
            return self.post_ack(headers, data)
        if route == ("GET", "/v1/check"):
            return self.get_check(qs)
        if route == ("GET", "/v1/audit"):
            return self.get_audit(headers, qs)
        return 404, {"error": "not found"}

    def post_receipt(self, headers, r):
        c = self._claims(headers)
        if not c:
            return 401, {"error": "a valid, unexpired runner token is required"}
        bad = policy_mod.validate_receipt(r)
        if bad:
            return 422, {"error": f"malformed receipt: {bad}"}
        if c.get("repository") != r["repo"]:
            return 403, {"error": "the token is for another repository than the receipt claims"}
        if str(c.get("job_workflow_ref", "")) not in self.trusted:
            return 403, {"error": "receipts are accepted only from the exact trusted gate workflow at its pinned ref (job_workflow_ref)"}
        if c.get("aud") != self.audience:
            return 403, {"error": "the token was issued for another audience"}
        if c.get("event_name") not in self.events:
            return 403, {"error": "the token comes from an event the service does not accept"}
        tree = self.oracle.tree_of(r["repo"], r["commit"])
        if tree is None or tree != r.get("git_tree"):
            return 422, {"error": "the receipt's content hash does not match the commit as GitHub has it"}
        rsha = policy_mod.sha(r)
        if not self.store.q("select 1 from receipts where id=?", rsha):
            self.store.q("insert into receipts values(?,?,?,?,?,?)", rsha, r["repo"], r["commit"], json.dumps(r), time.time(), int(c.get("run_id") or 0) * 1000 + int(c.get("run_attempt") or 0))
        return 200, {"id": rsha, "decision": self._decide(r)}

    def post_ack(self, headers, d):
        c = self._claims(headers)
        if not c or not isinstance(c.get("login"), str):
            return 401, {"error": "a valid user token is required"}
        rows = self.store.q("select body from receipts where id=?", d.get("receipt_sha"))
        if not rows:
            return 404, {"error": "unknown receipt"}
        r = json.loads(rows[0][0])
        pol = {**policy_mod.DEFAULT_POLICY, **(self._policy(r["repo"]) or {})}
        if c["login"].lower() not in {x.lower() for x in pol["acknowledgers"]}:
            return 403, {"error": "not a listed acknowledger for this repository"}
        self.store.q("insert into acks values(?,?,?,?)", d["receipt_sha"], c["login"], str(d.get("note", ""))[:300], time.time())   # `by` comes from the token, never from the body
        return 200, {"decision": self._decide(r)}

    def get_check(self, qs):
        rows = self.store.q("select body from receipts where repo=? and commit_sha=? order by run_order desc, received desc limit 1", qs.get("repo"), qs.get("commit"))
        if not rows:
            return 200, {"conclusion": "action_required", "decision": "needs_acknowledgement", "reasons": [{"rule": "no_receipt", "outcome": "needs_acknowledgement", "acknowledged_by": None,
                                                                                                          "text": "No receipt was uploaded for this commit, so nothing was checked."}]}
        d = self._decide(json.loads(rows[0][0]))
        return 200, {"conclusion": d["conclusion"], "decision": d["decision"], "reasons": d["reasons"], "receipt_sha": d["receipt_sha"], "policy_sha": d["policy_sha"]}

    def get_audit(self, headers, qs):
        if not self._is_admin(headers):
            return 401, {"error": "admin token required"}
        out = []
        for rid, body, got in self.store.q("select id, body, received from receipts where repo=? order by received", qs.get("repo")):
            r = json.loads(body)
            d = self._decide(r)
            out.append({"receipt_sha": rid, "commit": r["commit"], "git_tree": r["git_tree"], "received": got, "decision": d["decision"], "reasons": [x["text"] for x in d["reasons"]],
                        "acknowledged_by": sorted({x["by"] for x in self._acks(rid)}), "reproducibility": r.get("reproducibility"), "not_reproduced": r.get("not_reproduced", [])})
        if qs.get("format") == "csv":
            buf = io.StringIO(); w = csv.writer(buf)
            w.writerow(["receipt_sha", "commit", "git_tree", "decision", "acknowledged_by", "reproducibility", "not_reproduced"])
            for x in out:
                w.writerow([_cell(v) for v in (x["receipt_sha"], x["commit"], x["git_tree"], x["decision"], ";".join(x["acknowledged_by"]), x["reproducibility"], ";".join(x["not_reproduced"]))])
            return 200, {"csv": buf.getvalue()}
        return 200, {"repo": qs.get("repo"), "records": out}


def serve(app: App, host="127.0.0.1", port=0):
    class H(BaseHTTPRequestHandler):
        def _do(self):
            n = int(self.headers.get("Content-Length") or 0)
            code, obj = app.handle(self.command, self.path, dict(self.headers), self.rfile.read(min(n, MAX_BODY + 1)))
            b = json.dumps(obj).encode()
            self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
        do_GET = do_POST = do_PUT = _do

        def log_message(self, *a):
            pass
    srv = ThreadingHTTPServer((host, port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv
