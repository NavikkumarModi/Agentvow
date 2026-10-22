"""The service logic, independent of HTTP: every method takes bytes and headers and returns (status, dict), so it is tested without a server. Principles: fail closed (no receipt, a policy that cannot be
read, GitHub unreachable: the check stays failing or action-required, never success); identity comes only from verified tokens and signed webhooks, never from request bodies; every query is scoped by repository."""
import hashlib
import hmac
import json
import re
import threading
import time
from collections import deque
from dataclasses import dataclass, field

from agentvow import policy as P

from .github import GitHubError
from .oidc import OidcError

CHECK_NAME = "agentvow/evidence"
ACK_RE = re.compile(r"^\s*/agentvow\s+acknowledge(?:\s+([0-9a-f]{8,64}))?\b(.*)$", re.I | re.S)
WRITE = ("write", "admin", "maintain")
CONCLUSIONS = {"success": "success", "failure": "failure", "action_required": "action_required"}   # neutral and skipped would PASS a required check: never used


@dataclass
class Config:
    trusted_workflows: frozenset = frozenset()          # exact job_workflow_ref values, each with its pinned ref
    events: frozenset = frozenset({"pull_request", "push", "workflow_dispatch"})
    webhook_secret: bytes = b""
    policy_path: str = ".agentvow/policy.json"
    max_body: int = 64 * 1024
    monthly_receipts: dict = field(default_factory=lambda: {"free": 30, "team": 3000, "business": 30000})
    monthly_bytes: int = 200 * 1024 * 1024
    per_minute: int = 30


class RateLimiter:
    def __init__(self, limit: int, window: float = 60.0, now=time.time):
        self.limit, self.window, self.now, self.hits, self.lock = limit, window, now, {}, threading.Lock()

    def ok(self, key: str) -> bool:
        with self.lock:
            q = self.hits.setdefault(key, deque())
            t = self.now()
            while q and q[0] < t - self.window:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(t)
            return True


def _clean(x, n=200) -> str:
    return re.sub(r"[^\w .,;:()'/%+=-]", "", str(x))[:n]


class Service:
    def __init__(self, cfg: Config, verifier, github, store, now=time.time):
        self.cfg, self.oidc, self.gh, self.store, self.now = cfg, verifier, github, store, now
        self.limiter = RateLimiter(cfg.per_minute, now=now)

    # ------------------------------------------------------------------ receipts
    def post_receipt(self, headers: dict, body: bytes) -> tuple:
        auth = str(headers.get("authorization", ""))
        if not auth.startswith("Bearer "):
            return 401, {"error": "a GitHub Actions OIDC token is required"}
        try:
            claims = self.oidc.verify(auth[7:])
        except OidcError as e:
            return 401, {"error": f"token refused: {e}"}
        except Exception:
            return 503, {"error": "could not verify the token right now"}
        if len(body) > self.cfg.max_body:
            return 413, {"error": "receipt too large"}
        try:
            r = json.loads(body)
        except (ValueError, RecursionError):
            return 400, {"error": "not JSON"}
        bad = P.validate_receipt(r)
        if bad:
            return 422, {"error": f"malformed receipt: {bad}"}
        repo = r["repo"]
        if claims.get("repository") != repo:
            return 403, {"error": "the token is for another repository than the receipt claims"}
        if str(claims.get("job_workflow_ref", "")) not in self.cfg.trusted_workflows:
            return 403, {"error": "receipts are accepted only from the exact trusted gate workflow at its pinned ref"}
        if claims.get("event_name") not in self.cfg.events:
            return 403, {"error": "the token comes from an event the service does not accept"}
        if not self.limiter.ok("repo:" + repo):
            return 429, {"error": "too many receipts for this repository; try again in a minute"}
        try:
            info = self.gh.repo_info(repo)
            plan = self.store.plan(repo)
            if info["private"] and plan == "free":
                return self._refuse(repo, r["commit"], "A paid plan is required for private repositories.", 402)
            if self.gh.commit_tree(repo, r["commit"]) != r["git_tree"]:
                return 422, {"error": "the receipt's content hash does not match the commit as GitHub has it"}
            base_ref = info["default_branch"]
            if r.get("pr"):
                pr = self.gh.pr_info(repo, r["pr"])
                if not pr or pr["head_sha"] != r["commit"]:
                    return 422, {"error": "the receipt's commit is not the head of that pull request"}
                base_ref = pr["base_ref"] or base_ref
        except GitHubError as e:
            return 502, {"error": f"GitHub could not confirm the receipt ({_clean(e)})"}
        rid = P.sha(r)
        n, nbytes = self.store.count_usage(repo, len(body)) if self.store.receipt(repo, rid) is None else self.store.usage(repo)
        if n > self.cfg.monthly_receipts.get(plan, self.cfg.monthly_receipts["free"]) or nbytes > self.cfg.monthly_bytes:
            return self._refuse(repo, r["commit"], "This month's receipt allowance for the plan is used up.", 429)
        self.store.add_receipt(repo, rid, r["commit"], r.get("pr"), r, int(claims.get("run_id") or 0) * 1000 + int(claims.get("run_attempt") or 0))
        result = self.evaluate(repo, r, rid, base_ref)
        try:
            cid = self._publish(repo, r["commit"], result)
        except GitHubError as e:
            return 502, {"error": f"the receipt was stored but the check run could not be set ({_clean(e)})", "id": rid, "decision": result}
        return 200, {"id": rid, "decision": result, "check_id": cid}

    def _refuse(self, repo, commit, why, status):
        result = {"decision": "needs_acknowledgement", "conclusion": "action_required", "reasons": [{"rule": "service", "outcome": "needs_acknowledgement", "text": why, "acknowledged_by": None}], "policy_sha": "", "receipt_sha": ""}
        try:
            self._publish(repo, commit, result)
        except GitHubError:
            pass
        return status, {"error": why}

    def policy_for(self, repo, base_ref):
        """-> (policy dict or None, error text or None). The policy comes from the BASE branch through GitHub's API, never from the change being judged."""
        try:
            text = self.gh.file_at(repo, self.cfg.policy_path, base_ref)
        except GitHubError as e:
            return None, f"The policy could not be read from the base branch ({_clean(e)}); nothing was allowed."
        if text is None:
            return {}, None
        try:
            pol = json.loads(text)
        except ValueError:
            return None, "The policy file in the base branch is not valid JSON; nothing was allowed."
        bad = P.validate_policy(pol)
        return (None, f"The policy file in the base branch is invalid ({_clean(bad)}); nothing was allowed.") if bad else (pol, None)

    def evaluate(self, repo, receipt, rid, base_ref):
        pol, err = self.policy_for(repo, base_ref)
        if err:
            res = P.evaluate(receipt, {"schema": "unreadable"})
            res["reasons"] = [{"rule": "policy_unreadable", "outcome": "block", "text": err, "acknowledged_by": None}]
            return res
        return P.evaluate(receipt, pol, self.store.acks(repo, rid))

    def _publish(self, repo, commit, result) -> int:
        lines = [f"- **{_clean(x['rule'])}** ({_clean(x['outcome'])}{', acknowledged by ' + _clean(x['acknowledged_by']) if x.get('acknowledged_by') else ''}): {_clean(x['text'], 300)}" for x in result["reasons"]]
        summary = "\n".join(lines) + "\n\nA pass here is evidence to weigh, not verification: the pull request's own code wrote the test output. To acknowledge an UNKNOWN result, a listed acknowledger comments `/agentvow acknowledge` on the pull request."
        cid = self.gh.set_check(repo, commit, CHECK_NAME, "completed", CONCLUSIONS[result["conclusion"]], f"Agentvow: {result['decision']}", summary, self.store.check_id(repo, commit))
        self.store.set_check_id(repo, commit, cid)
        return cid

    # ------------------------------------------------------------------ webhooks
    def webhook(self, headers: dict, body: bytes) -> tuple:
        sig = str(headers.get("x-hub-signature-256", ""))
        want = "sha256=" + hmac.new(self.cfg.webhook_secret, body, hashlib.sha256).hexdigest()
        if not self.cfg.webhook_secret or not hmac.compare_digest(sig, want):
            return 401, {"error": "bad webhook signature"}
        if len(body) > 1_000_000:
            return 413, {"error": "payload too large"}
        try:
            p = json.loads(body)
        except ValueError:
            return 400, {"error": "not JSON"}
        ev = str(headers.get("x-github-event", ""))
        try:
            if ev == "pull_request" and p.get("action") in ("opened", "reopened", "synchronize", "ready_for_review"):
                return self._pr_event(p)
            if ev == "issue_comment" and p.get("action") == "created" and "pull_request" in (p.get("issue") or {}):
                return self._comment_event(p)
        except GitHubError as e:
            return 502, {"error": f"GitHub error ({_clean(e)})"}
        return 200, {"ignored": ev}

    def _pr_event(self, p):
        repo, sha = p["repository"]["full_name"], p["pull_request"]["head"]["sha"]
        cid = self.gh.set_check(repo, sha, CHECK_NAME, "in_progress", None, "Agentvow: waiting for the gate",
                                "No receipt has been posted for this commit yet. The required check stays pending until the Agentvow gate workflow runs and posts one.", self.store.check_id(repo, sha))
        self.store.set_check_id(repo, sha, cid)
        return 200, {"pending_check": cid}

    def _comment_event(self, p):
        m = ACK_RE.match(str((p.get("comment") or {}).get("body", "")))
        if not m:
            return 200, {"ignored": "not an acknowledgement"}
        repo, number = p["repository"]["full_name"], int(p["issue"]["number"])
        user = p["comment"]["user"]
        login = str(user.get("login", ""))
        if user.get("type") != "User" or not login:
            return 200, {"ignored": "not a person"}
        if not self.limiter.ok("user:" + login.lower()):
            return 429, {"error": "slow down"}
        pr = self.gh.pr_info(repo, number)
        if not pr:
            return 200, {"ignored": "pull request not found"}
        rid, receipt = self.store.latest_receipt(repo, pr["head_sha"])
        if not rid:
            self.gh.comment(repo, number, "Agentvow: there is no receipt for the current commit of this pull request yet, so there is nothing to acknowledge.")
            return 200, {"refused": "no receipt"}
        if m.group(1) and not rid.startswith(m.group(1).lower()):
            self.gh.comment(repo, number, f"Agentvow: that receipt id does not match the current one (`{rid[:12]}`). Acknowledge the current one.")
            return 200, {"refused": "receipt id mismatch"}
        pol, err = self.policy_for(repo, pr["base_ref"] or "main")
        if err:
            self.gh.comment(repo, number, f"Agentvow: {err}")
            return 200, {"refused": "policy unreadable"}
        full = {**P.DEFAULT_POLICY, **pol}
        if login.lower() not in {a.lower() for a in full["acknowledgers"]}:
            self.gh.comment(repo, number, f"Agentvow: @{_clean(login, 39)} is not a listed acknowledger in this repository's policy.")
            return 200, {"refused": "not a listed acknowledger"}
        if self.gh.permission(repo, login) not in WRITE:
            self.gh.comment(repo, number, f"Agentvow: @{_clean(login, 39)} does not have write access to this repository.")
            return 200, {"refused": "no write access"}
        self.store.add_ack(repo, rid, login, m.group(2).strip())
        result = self.evaluate(repo, receipt, rid, pr["base_ref"] or "main")
        self._publish(repo, pr["head_sha"], result)
        self.gh.comment(repo, number, f"Agentvow: acknowledged by @{_clean(login, 39)} for receipt `{rid[:12]}`. Decision: **{result['decision']}**.")
        return 200, {"decision": result["decision"]}

    # ------------------------------------------------------------------ reading
    def check(self, repo: str, commit: str, headers: dict | None = None) -> tuple:
        if headers is not None:   # HTTP callers need the repository's key; internal callers pass None
            auth = str(headers.get("authorization", ""))
            if not auth.startswith("Bearer ") or not self.store.key_ok(repo, auth[7:]):
                return 401, {"error": "this repository's audit key is required"}
        rid, r = self.store.latest_receipt(repo, commit)
        if not rid:
            return 200, {"conclusion": "action_required", "decision": "needs_acknowledgement", "reasons": [{"rule": "no_receipt", "text": "No receipt was uploaded for this commit, so nothing was checked."}]}
        info = self.gh.repo_info(repo)
        res = self.evaluate(repo, r, rid, info["default_branch"])
        return 200, {"conclusion": res["conclusion"], "decision": res["decision"], "reasons": res["reasons"], "receipt_sha": rid}

    def audit(self, repo: str, headers: dict, fmt: str = "json") -> tuple:
        auth = str(headers.get("authorization", ""))
        if not auth.startswith("Bearer ") or not self.store.key_ok(repo, auth[7:]):
            return 401, {"error": "this repository's audit key is required"}
        info = self.gh.repo_info(repo)
        rows = []
        for rid, r, at in self.store.receipts(repo):
            res = self.evaluate(repo, r, rid, info["default_branch"])
            rows.append({"receipt_sha": rid, "commit": r["commit"], "git_tree": r["git_tree"], "pr": r.get("pr"), "received": at, "decision": res["decision"], "reasons": [x["text"] for x in res["reasons"]],
                         "acknowledged_by": sorted({a["by"] for a in self.store.acks(repo, rid)}), "reproducibility": r.get("reproducibility"), "not_reproduced": r.get("not_reproduced", [])})
        if fmt == "csv":
            import csv
            import io
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(["receipt_sha", "commit", "git_tree", "pr", "decision", "acknowledged_by", "reproducibility", "not_reproduced"])
            for x in rows:
                w.writerow([self._cell(v) for v in (x["receipt_sha"], x["commit"], x["git_tree"], x["pr"], x["decision"], ";".join(x["acknowledged_by"]), x["reproducibility"], ";".join(x["not_reproduced"]))])
            return 200, {"csv": buf.getvalue()}
        return 200, {"repo": repo, "records": rows}

    @staticmethod
    def _cell(v) -> str:
        t = str(v if v is not None else "")
        return "'" + t if t[:1] in ("=", "+", "-", "@", "\t", "\r") else t
