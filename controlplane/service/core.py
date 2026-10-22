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
ACK_RE = re.compile(r"^\s*/agentvow\s+acknowledge(?:\s+([0-9a-f]{8,64}))?(?![0-9A-Za-z])(.*)$", re.I | re.S)
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
    def __init__(self, limit: int, window: float = 60.0, now=time.time, max_keys: int = 10000):
        self.limit, self.window, self.now, self.max_keys, self.hits, self.lock = limit, window, now, max_keys, {}, threading.Lock()

    def ok(self, key: str) -> bool:
        with self.lock:
            t = self.now()
            if len(self.hits) > self.max_keys:   # bounded memory: drop every key with no recent hit
                self.hits = {k: q for k, q in self.hits.items() if q and q[-1] >= t - self.window}
                if len(self.hits) > self.max_keys:
                    return False
            q = self.hits.setdefault(key, deque())
            while q and q[0] < t - self.window:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(t)
            return True


def _clean(x, n=200) -> str:
    return re.sub(r"[^\w .,;:()'/%+=-]", "", str(x))[:n]


REPO_RE = re.compile(r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}")


def _repo_ok(repo) -> bool:
    return isinstance(repo, str) and bool(REPO_RE.fullmatch(repo)) and ".." not in repo


class Service:
    def __init__(self, cfg: Config, verifier, github, store, now=time.time):
        self.cfg, self.oidc, self.gh, self.store, self.now = cfg, verifier, github, store, now
        self.limiter = RateLimiter(cfg.per_minute, now=now)
        self.locks = [threading.RLock() for _ in range(64)]   # one publisher at a time per (repository, commit)

    # ------------------------------------------------------------------ receipts
    def post_receipt(self, headers: dict, body: bytes) -> tuple:
        auth = str(headers.get("authorization", ""))
        if not auth.startswith("Bearer "):
            return 401, {"error": "a GitHub Actions OIDC token is required"}
        if len(body) > self.cfg.max_body:
            return 413, {"error": "receipt too large"}
        # The token must have been issued for THIS body: the gate asks GitHub for audience "<audience>:<sha256 of the receipt>". A token sent anywhere else (a different service URL, a pull
        # request's own workflow input) can then be replayed only with the very receipt it was issued for.
        try:
            claims = self.oidc.verify(auth[7:], audience=f"{self.oidc.audience}:{hashlib.sha256(body).hexdigest()}")
        except OidcError as e:
            return 401, {"error": f"token refused: {e}"}
        except Exception:
            return 503, {"error": "could not verify the token right now"}
        try:
            r = json.loads(body)
        except (ValueError, RecursionError):
            return 400, {"error": "not JSON"}
        bad = P.validate_receipt(r)
        if bad:
            return 422, {"error": f"malformed receipt: {bad}"}
        repo = r["repo"]
        if not _repo_ok(repo) or claims.get("repository") != repo:
            return 403, {"error": "the token is for another repository than the receipt claims"}
        if str(claims.get("job_workflow_ref", "")) not in self.cfg.trusted_workflows:
            return 403, {"error": "receipts are accepted only from the exact trusted gate workflow at its pinned ref"}
        event = claims.get("event_name")
        if event not in self.cfg.events:
            return 403, {"error": "the token comes from an event the service does not accept"}
        if event == "pull_request":
            if not r.get("pr") or claims.get("ref") != f"refs/pull/{r['pr']}/merge":
                return 403, {"error": "the token's pull request is not the receipt's pull request"}
        elif claims.get("sha") != r["commit"]:
            return 403, {"error": "the token's commit is not the receipt's commit"}
        if not self.limiter.ok("repo:" + repo):
            return 429, {"error": "too many receipts for this repository; try again in a minute"}
        if not claims.get("repository_id") or not self.store.bind_repo_id(repo, claims["repository_id"]):   # only after every trust check, so an untrusted token cannot claim a name
            return 403, {"error": "this repository name belongs to a different repository than the one first seen"}
        self.reconcile()
        try:
            info = self.gh.repo_info(repo)
            plan = self.store.plan(repo)
            if info["private"] and plan == "free":
                return self._refuse(repo, r["commit"], "A paid plan is required for private repositories.", 402)
            if self.gh.commit_tree(repo, r["commit"]) != r["git_tree"]:
                return 422, {"error": "the receipt's content hash does not match the commit as GitHub has it"}
            if r.get("pr"):
                pr = self.gh.pr_info(repo, r["pr"])
                if not pr or pr["head_sha"] != r["commit"]:
                    return 422, {"error": "the receipt's commit is not the head of that pull request"}
        except GitHubError as e:
            return 502, {"error": f"GitHub could not confirm the receipt ({_clean(e)})"}
        rid = P.sha(r)
        run_order = int(claims.get("run_id") or 0) * 1000 + int(claims.get("run_attempt") or 0)
        got = self.store.add_receipt(repo, rid, r["commit"], r.get("pr"), r, run_order, self.cfg.monthly_receipts.get(plan, self.cfg.monthly_receipts["free"]), self.cfg.monthly_bytes, event)
        if got == "over":
            return self._refuse(repo, r["commit"], "This month's receipt allowance for the plan is used up.", 429)
        # The check shows the worst result among the latest receipts of each kind of run (pull_request, push, ...) for this commit: a later run of one kind never hides another kind's receipt.
        try:
            result, cid = self._refresh(repo, r["commit"], info["default_branch"])
        except GitHubError as e:
            return 502, {"error": f"the receipt was stored but the check run could not be set; it will be retried ({_clean(e)})", "id": rid}
        except Exception:
            self.store.mark_dirty(repo, r["commit"])
            self._fail_closed(repo, r["commit"])
            return 500, {"error": "internal error; the check was set to failure", "id": rid}
        return 200, {"id": rid, "decision": result, "check_id": cid}

    _RANK = {"allow": 0, "needs_acknowledgement": 1, "block": 2}

    def decide(self, repo, commit, branch, policy=None):
        """The combined decision for a commit, or None when there is no receipt: the worst of the latest receipt of each kind of run."""
        rs = self.store.latest_receipts(repo, commit)
        if not rs:
            return None
        policy = policy or self.policy_for(repo, branch)
        results = [self.evaluate(repo, r, rid, branch, policy) for rid, r in rs]
        worst = max(results, key=lambda x: self._RANK.get(x["decision"], 2))
        out = dict(worst)
        out["reasons"] = list(worst["reasons"]) + [x for res in results if res is not worst for x in res["reasons"]]
        out["receipts"] = [rid for rid, _ in rs]
        return out

    def _refresh(self, repo, commit, branch, policy=None):
        """Read the receipts, decide and publish as ONE step per (repository, commit): a slow thread can no longer publish an older result over a newer one. A failed publish is remembered and retried."""
        with self.locks[hash((repo, commit)) % len(self.locks)]:
            result = self.decide(repo, commit, branch, policy)
            if result is None:
                return None, None
            try:
                cid = self._publish(repo, commit, result)
            except GitHubError:
                self.store.mark_dirty(repo, commit)
                raise
            self.store.clear_dirty(repo, commit)
            return result, cid

    def reconcile(self) -> None:
        """Re-publish check runs whose last publish failed (best effort; called on every receipt and webhook and by the background loop)."""
        try:
            for repo, commit in self.store.dirty():
                try:
                    self._refresh(repo, commit, self.gh.repo_info(repo)["default_branch"])
                except Exception:
                    continue
        except Exception:
            pass

    def _fail_closed(self, repo, commit):
        try:
            self._check(repo, commit, "completed", "failure", "Agentvow: internal error", "The service failed while evaluating this commit; nothing was allowed.")
        except Exception:
            pass

    def _refuse(self, repo, commit, why, status):
        try:
            self._check(repo, commit, "completed", "action_required", "Agentvow: needs attention", why)
        except GitHubError:
            pass
        return status, {"error": why}

    def policy_for(self, repo, branch):
        """-> (policy dict or None, error text or None). The policy is read from the repository's DEFAULT branch at its current commit, through GitHub's API: never from the change being judged, and not
        from a branch the pull request's author chose as its base. A branch that cannot be resolved is an error, not 'no policy'."""
        try:
            text = self.gh.file_at(repo, self.cfg.policy_path, self.gh.branch_sha(repo, branch))
        except GitHubError as e:
            return None, f"The policy could not be read from the default branch ({_clean(e)}); nothing was allowed."
        if text is None:
            return {}, None
        try:
            pol = json.loads(text)
        except ValueError:
            return None, "The policy file in the default branch is not valid JSON; nothing was allowed."
        bad = P.validate_policy(pol)
        return (None, f"The policy file in the default branch is invalid ({_clean(bad)}); nothing was allowed.") if bad else (pol, None)

    def evaluate(self, repo, receipt, rid, branch, policy=None):
        pol, err = policy or self.policy_for(repo, branch)
        if err:
            res = P.evaluate(receipt, {"schema": "unreadable"})
            res["reasons"] = [{"rule": "policy_unreadable", "outcome": "block", "text": err, "acknowledged_by": None}]
            return res
        return P.evaluate(receipt, pol, self.store.acks(repo, rid))

    def _check(self, repo, commit, status, conclusion, title, summary) -> int:
        lock = self.locks[hash((repo, commit)) % len(self.locks)]
        with lock:
            cid = self.gh.set_check(repo, commit, CHECK_NAME, status, conclusion, title, summary, self.store.check_id(repo, commit))
            self.store.set_check_id(repo, commit, cid)
        return cid

    def _publish(self, repo, commit, result) -> int:
        lines = [f"- **{_clean(x['rule'])}** ({_clean(x['outcome'])}{', acknowledged by ' + _clean(x['acknowledged_by']) if x.get('acknowledged_by') else ''}): {_clean(x['text'], 300)}" for x in result["reasons"]]
        summary = "\n".join(lines) + "\n\nA pass here is evidence to weigh, not verification: the pull request's own code wrote the test output. To acknowledge an UNKNOWN result, a listed acknowledger comments `/agentvow acknowledge <receipt id>` on the pull request."
        return self._check(repo, commit, "completed", CONCLUSIONS[result["conclusion"]], f"Agentvow: {result['decision']}", summary)

    # ------------------------------------------------------------------ webhooks
    def webhook(self, headers: dict, body: bytes) -> tuple:
        sig = str(headers.get("x-hub-signature-256", ""))
        want = "sha256=" + hmac.new(self.cfg.webhook_secret, body, hashlib.sha256).hexdigest()
        if not self.cfg.webhook_secret or not hmac.compare_digest(sig.encode("utf-8", "replace"), want.encode()):
            return 401, {"error": "bad webhook signature"}
        if len(body) > 1_000_000:
            return 413, {"error": "payload too large"}
        try:
            p = json.loads(body)
        except ValueError:
            return 400, {"error": "not JSON"}
        ev = str(headers.get("x-github-event", ""))
        self.reconcile()
        try:
            if not isinstance(p, dict) or not _repo_ok((p.get("repository") or {}).get("full_name")):
                return (200, {"ignored": ev}) if ev not in ("pull_request", "issue_comment") else (400, {"error": "unexpected payload"})
            if ev == "pull_request" and p.get("action") in ("opened", "reopened", "synchronize", "ready_for_review"):
                return self._pr_event(p)
            if ev == "issue_comment" and p.get("action") == "created" and "pull_request" in (p.get("issue") or {}):
                did = str(headers.get("x-github-delivery", "")) or hashlib.sha256(body).hexdigest()
                if self.store.delivery_seen(did):
                    return 200, {"ignored": "delivery already processed"}
                code, obj = self._comment_event(p)
                if code == 200:   # recorded only after success, so a redelivery of a failed one is processed
                    self.store.record_delivery(did)
                return code, obj
        except GitHubError as e:
            return 502, {"error": f"GitHub error ({_clean(e)})"}
        except (KeyError, TypeError, ValueError, AttributeError):
            return 400, {"error": "unexpected payload"}
        return 200, {"ignored": ev}

    def _pr_event(self, p):
        repo, sha = p["repository"]["full_name"], str(p["pull_request"]["head"]["sha"])
        with self.locks[hash((repo, sha)) % len(self.locks)]:
            if self.store.latest_receipts(repo, sha):   # a receipt already exists for this commit (reopened, ready for review): show its result, never reset it to pending
                result, cid = self._refresh(repo, sha, self.gh.repo_info(repo)["default_branch"])
                return 200, {"check": cid}
            cid = self._check(repo, sha, "in_progress", None, "Agentvow: waiting for the gate", "No receipt has been posted for this commit yet. The required check stays pending until the Agentvow gate workflow runs and posts one.")
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
        current = self.store.latest_receipts(repo, pr["head_sha"])
        if not current:
            self.gh.comment(repo, number, "Agentvow: there is no receipt for the current commit of this pull request yet, so there is nothing to acknowledge.")
            return 200, {"refused": "no receipt"}
        ids = ", ".join(f"`{x[:12]}`" for x, _ in current)
        if not m.group(1):   # an acknowledgement names the receipt the person looked at; it never lands on whatever is newest
            self.gh.comment(repo, number, f"Agentvow: name the receipt you reviewed: `/agentvow acknowledge <id>` with one of {ids}.")
            return 200, {"refused": "receipt id required"}
        hits = [x for x, _ in current if x.startswith(m.group(1).lower())]
        if len(hits) != 1:
            self.gh.comment(repo, number, f"Agentvow: that receipt id does not match exactly one current receipt ({ids}). Acknowledge a current one.")
            return 200, {"refused": "receipt id mismatch"}
        rid = hits[0]
        info = self.gh.repo_info(repo)
        pol, err = self.policy_for(repo, info["default_branch"])
        if err:
            self.gh.comment(repo, number, f"Agentvow: {err}")
            return 200, {"refused": "policy unreadable"}
        full = {**P.DEFAULT_POLICY, **pol}
        if login.lower() not in {a.lower() for a in full["acknowledgers"]}:
            self.gh.comment(repo, number, f"Agentvow: @{_clean(login, 39)} is not a listed acknowledger in this repository's policy.")
            return 200, {"refused": "not a listed acknowledger"}
        if login.lower() == pr.get("user", "").lower() and login.lower() != repo.split("/")[0].lower():
            self.gh.comment(repo, number, f"Agentvow: @{_clean(login, 39)} opened this pull request and is not the repository owner, so someone else must acknowledge it.")
            return 200, {"refused": "author cannot acknowledge own pull request"}
        if self.gh.permission(repo, login) not in WRITE:
            self.gh.comment(repo, number, f"Agentvow: @{_clean(login, 39)} does not have write access to this repository.")
            return 200, {"refused": "no write access"}
        with self.locks[hash((repo, pr["head_sha"])) % len(self.locks)]:
            self.store.add_ack(repo, rid, login, m.group(2).strip())
            result, _ = self._refresh(repo, pr["head_sha"], info["default_branch"], (pol, None))
        self.gh.comment(repo, number, f"Agentvow: acknowledged by @{_clean(login, 39)} for receipt `{rid[:12]}`. Decision: **{result['decision']}**.")
        return 200, {"decision": result["decision"]}

    # ------------------------------------------------------------------ reading
    def _key_ok(self, repo, headers) -> bool:
        auth = str((headers or {}).get("authorization", ""))
        return auth.startswith("Bearer ") and self.store.key_ok(repo, auth[7:])

    def check(self, repo: str, commit: str, headers: dict | None = None) -> tuple:
        if headers is not None and not self._key_ok(repo, headers):   # HTTP callers need the repository's key; internal callers pass None
            return 401, {"error": "this repository's audit key is required"}
        try:
            res = self.decide(repo, commit, self.gh.repo_info(repo)["default_branch"])
        except GitHubError as e:
            return 502, {"error": f"GitHub error ({_clean(e)})"}
        if res is None:
            return 200, {"conclusion": "action_required", "decision": "needs_acknowledgement", "reasons": [{"rule": "no_receipt", "text": "No receipt was uploaded for this commit, so nothing was checked."}]}
        return 200, {"conclusion": res["conclusion"], "decision": res["decision"], "reasons": res["reasons"], "receipts": res["receipts"], "evaluated": "under the policy in force now; the published check may reflect an earlier policy until the next receipt or webhook"}

    def audit(self, repo: str, headers: dict, fmt: str = "json") -> tuple:
        if not self._key_ok(repo, headers):
            return 401, {"error": "this repository's audit key is required"}
        try:
            branch = self.gh.repo_info(repo)["default_branch"]
            policy = self.policy_for(repo, branch)   # fetched ONCE for the whole export; every decision below is "under the policy in force now", not "as it was then"
            rows = []
            for rid, r, at in self.store.receipts(repo):
                res = self.evaluate(repo, r, rid, branch, policy)
                rows.append({"receipt_sha": rid, "commit": r["commit"], "git_tree": r["git_tree"], "pr": r.get("pr"), "received": at, "decision_under_current_policy": res["decision"], "reasons": [x["text"] for x in res["reasons"]],
                             "acknowledged_by": sorted({x["acknowledged_by"] for x in res["reasons"] if x.get("acknowledged_by")}),   # only acknowledgements the current policy counts
                              "reproducibility": r.get("reproducibility"), "not_reproduced": r.get("not_reproduced", [])})
        except GitHubError as e:
            return 502, {"error": f"GitHub error ({_clean(e)})"}
        if fmt == "csv":
            import csv
            import io
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(["receipt_sha", "commit", "git_tree", "pr", "decision_under_current_policy", "acknowledged_by", "reproducibility", "not_reproduced"])
            for x in rows:
                w.writerow([self._cell(v) for v in (x["receipt_sha"], x["commit"], x["git_tree"], x["pr"], x["decision_under_current_policy"], ";".join(x["acknowledged_by"]), x["reproducibility"], ";".join(x["not_reproduced"]))])
            return 200, {"csv": buf.getvalue()}
        return 200, {"repo": repo, "records": rows}

    @staticmethod
    def _cell(v) -> str:
        t = str(v if v is not None else "")
        return "'" + t if t[:1] in ("=", "+", "-", "@", "\t", "\r") else t
