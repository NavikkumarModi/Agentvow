"""SQLite storage. Every query is parameterised and scoped by repository: there is no query that reads across repositories except operator maintenance (purge). Receipts are content-addressed and immutable;
acknowledgements are separate rows bound to one receipt id. The service stores receipts only (verdicts, counts, category names), never source."""
import hashlib
import hmac
import json
import secrets
import sqlite3
import threading
import time

SCHEMA = """
create table if not exists receipts(id text not null, repo text not null, commit_sha text not null, pr integer, body text not null, received real not null, run_order integer not null, event text not null default '', primary key(repo, id));
create index if not exists receipts_commit on receipts(repo, commit_sha, run_order desc, received desc);
create table if not exists checks(repo text not null, commit_sha text not null, check_id integer not null, primary key(repo, commit_sha));
create table if not exists acks(repo text not null, receipt_id text not null, by text not null, note text, at real not null);
create index if not exists acks_receipt on acks(repo, receipt_id);
create table if not exists plans(repo text primary key, plan text not null, until real);
create table if not exists keys(repo text primary key, key_hash text not null);
create table if not exists published_policy(repo text not null, commit_sha text not null, psha text not null, primary key(repo, commit_sha));
create table if not exists notified(repo text not null, commit_sha text not null, key text not null, at real not null, primary key(repo, commit_sha, key));
create table if not exists meta(k text primary key, v text not null);
create table if not exists gone_since(repo text primary key, since real not null);
create table if not exists installs(installation_id integer primary key, account text not null, deleted_at real);
create table if not exists install_repos(repo text primary key, installation_id integer not null, removed_at real);
create table if not exists repo_ids(repo text primary key, repo_id text not null);
create table if not exists dirty(repo text not null, commit_sha text not null, primary key(repo, commit_sha));
create table if not exists deliveries(id text primary key, at real not null);
create table if not exists usage(repo text not null, month text not null, n integer not null, bytes integer not null, primary key(repo, month));
"""


class Store:
    def __init__(self, path: str = ":memory:"):
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.lock = threading.Lock()
        with self.lock:
            self.db.execute("pragma journal_mode=wal")
            self.db.executescript(SCHEMA)

    def q(self, sql, *a):
        with self.lock:
            return self.db.execute(sql, a).fetchall()

    # ---- identity of a repository (names can be renamed or recycled; the numeric id cannot)
    def bind_repo_id(self, repo, repo_id) -> bool:
        """-> True when `repo` is new or already bound to this id; False when the name now belongs to a different repository."""
        with self.lock:
            self.db.execute("insert or ignore into repo_ids values(?,?)", (repo, str(repo_id)))
            return self.db.execute("select repo_id from repo_ids where repo=?", (repo,)).fetchone()[0] == str(repo_id)

    # ---- receipts
    def add_receipt(self, repo, rid, commit, pr, body: dict, run_order: int, max_receipts: int = 10**9, max_bytes: int = 10**12, event: str = "") -> str:
        """Store and count in ONE step. -> "added", "duplicate" (same receipt again: only its run order can move forward, nothing is counted) or "over" (the month's allowance is used up;
        nothing is stored or counted)."""
        raw = json.dumps(body, sort_keys=True)
        m = time.strftime("%Y-%m")
        with self.lock:
            if self.db.execute("select 1 from receipts where repo=? and id=?", (repo, rid)).fetchone():
                self.db.execute("update receipts set run_order = max(run_order, ?) where repo=? and id=?", (run_order, repo, rid))
                return "duplicate"
            n, b = self.db.execute("select coalesce(sum(n),0), coalesce(sum(bytes),0) from usage where repo=? and month=?", (repo, m)).fetchone()
            if n + 1 > max_receipts or b + len(raw) > max_bytes:
                return "over"
            self.db.execute("begin")
            try:
                self.db.execute("insert into receipts values(?,?,?,?,?,?,?,?)", (rid, repo, commit, pr, raw, time.time(), run_order, event))
                self.db.execute("insert into usage values(?,?,1,?) on conflict(repo, month) do update set n = n + 1, bytes = bytes + excluded.bytes", (repo, m, len(raw)))
                self.db.execute("commit")
            except BaseException:
                self.db.execute("rollback")
                raise
            return "added"

    def delivery_seen(self, delivery_id: str) -> bool:
        return bool(self.q("select 1 from deliveries where id=?", str(delivery_id)[:80]))

    def record_delivery(self, delivery_id: str) -> None:
        """Recorded only AFTER a delivery was handled successfully, so GitHub's redelivery of one that failed is processed, not dropped."""
        self.q("insert or ignore into deliveries values(?,?)", str(delivery_id)[:80], time.time())

    def unbind_repo(self, repo) -> None:
        self.q("delete from repo_ids where repo=?", repo)

    # ---- check runs that could not be published (retried by reconcile)
    def mark_dirty(self, repo, commit): self.q("insert or ignore into dirty values(?,?)", repo, commit)
    def clear_dirty(self, repo, commit): self.q("delete from dirty where repo=? and commit_sha=?", repo, commit)
    def dirty(self): return self.q("select repo, commit_sha from dirty limit 50")

    def latest_receipts(self, repo, commit):
        """-> [(id, body)]: for each triggering event (pull_request, push, ...) the receipt of the latest run for this commit. A run of one kind never hides another kind's receipt."""
        out, seen = [], set()
        for rid, body, ev in self.q("select id, body, event from receipts where repo=? and commit_sha=? order by run_order desc, received desc", repo, commit):
            if ev not in seen:
                seen.add(ev); out.append((rid, json.loads(body)))
        return out

    def receipt(self, repo, rid):
        r = self.q("select body from receipts where repo=? and id=?", repo, rid)
        return json.loads(r[0][0]) if r else None

    def receipts(self, repo):
        return [(rid, json.loads(b), at) for rid, b, at in self.q("select id, body, received from receipts where repo=? order by received", repo)]

    # ---- acknowledgements
    def add_ack(self, repo, rid, by, note):
        self.q("insert into acks values(?,?,?,?,?)", repo, rid, by, str(note)[:300], time.time())

    def acks(self, repo, rid):
        from agentvow import policy as P
        return [{"schema": P.ACK, "receipt_sha": rid, "by": b, "note": n, "at": str(a)} for b, n, a in self.q("select by, note, at from acks where repo=? and receipt_id=?", repo, rid)]

    # ---- check runs
    def check_id(self, repo, commit):
        r = self.q("select check_id from checks where repo=? and commit_sha=?", repo, commit)
        return r[0][0] if r else None

    def set_check_id(self, repo, commit, cid):
        self.q("insert or replace into checks values(?,?,?)", repo, commit, cid)

    # ---- plans, keys, usage
    def set_plan(self, repo, plan, until=None):
        self.q("insert or replace into plans values(?,?,?)", str(repo).lower(), plan, until)   # GitHub logins are case-insensitive

    def plan(self, repo) -> str:
        """The plan of the repository, else of its owner account (`set_plan("owner", ...)` covers every repository of that account), else free. An ended plan counts as free."""
        for key in (str(repo).lower(), str(repo).split("/")[0].lower()):
            r = self.q("select plan, until from plans where repo=?", key)
            if r and (r[0][1] is None or r[0][1] > time.time()):
                return r[0][0]
        return "free"

    def retention_plan(self, repo) -> str:
        """The plan whose retention applies to stored data: the best plan the repository or its owner EVER had (rows are kept after they end), so a lapsed subscription, a late invoice or a typo in
        `--days` never deletes an audit trail; data leaves only by the plan's own retention while it was paid, by `erase`, or after the App is uninstalled."""
        order = {"free": 0, "team": 1, "business": 2}
        best = "free"
        for key in (str(repo).lower(), str(repo).split("/")[0].lower()):
            for (plan,) in self.q("select plan from plans where repo=?", key):
                if order.get(plan, 0) > order.get(best, 0):
                    best = plan
        return best

    def issue_key(self, repo, rotate: bool = False) -> str:
        if not rotate and self.q("select 1 from keys where repo=?", repo):
            raise ValueError("a key already exists for this repository; rotate it explicitly")
        key = "avk_" + secrets.token_urlsafe(32)
        self.q("insert or replace into keys values(?,?)", repo, hashlib.sha256(key.encode()).hexdigest())
        return key

    def key_ok(self, repo, presented: str) -> bool:
        r = self.q("select key_hash from keys where repo=?", repo)
        return bool(r) and hmac.compare_digest(r[0][0], hashlib.sha256(str(presented).encode()).hexdigest())

    def usage(self, repo):
        r = self.q("select n, bytes from usage where repo=? and month=?", repo, time.strftime("%Y-%m"))
        return r[0] if r else (0, 0)

    # ---- installations of the GitHub App (a tenant's lifecycle)
    def record_install(self, iid: int, account: str, repos) -> None:
        with self.lock:
            self.db.execute("insert or replace into installs values(?,?,NULL)", (int(iid), str(account)[:100]))
            for r in repos:
                self.db.execute("insert or replace into install_repos values(?,?,NULL)", (r, int(iid), ))

    def add_install_repos(self, iid: int, repos) -> None:
        with self.lock:
            for r in repos:
                self.db.execute("insert or replace into install_repos values(?,?,NULL)", (r, int(iid)))

    def remove_install_repos(self, iid: int, repos) -> None:
        with self.lock:
            for r in repos:
                self.db.execute("update install_repos set removed_at=? where repo=? and installation_id=? and removed_at is null", (time.time(), r, int(iid)))

    def remove_install(self, iid: int) -> None:
        with self.lock:
            now = time.time()
            self.db.execute("update installs set deleted_at=? where installation_id=?", (now, int(iid)))
            self.db.execute("update install_repos set removed_at=? where installation_id=? and removed_at is null", (now, int(iid)))

    def erase_repo(self, repo) -> None:
        """Everything stored about one repository (receipts, acknowledgements, check ids, key, plan, counters, binding, install record), in one transaction. Used after the App is gone from it and on request.
        (Deleted rows stay in SQLite's free pages and in earlier backups until overwritten.)"""
        with self.lock:
            self.db.execute("begin")
            try:
                for t in ("receipts", "checks", "acks", "plans", "keys", "usage", "repo_ids", "dirty", "install_repos", "gone_since"):
                    self.db.execute(f"delete from {t} where repo=?", (repo,))
                self.db.execute("delete from notified where repo=?", (repo,))
                self.db.execute("delete from published_policy where repo=?", (repo,))
                self.db.execute("delete from plans where repo=?", (repo.lower(),))
                self.db.execute("commit")
            except BaseException:
                self.db.execute("rollback")
                raise

    def repos_with_data(self):
        return [r for (r,) in self.q("select repo from receipts union select repo from keys union select repo from install_repos") if "/" in r]

    def note_installed(self, repo, installed: bool, grace_days: int) -> bool:
        """Record what GitHub says about the App on this repository. -> True when the App has been gone for longer than the grace period (time to erase)."""
        with self.lock:
            if installed:
                self.db.execute("delete from gone_since where repo=?", (repo,)); self.db.execute("update install_repos set removed_at=NULL where repo=?", (repo,))
                return False
            self.db.execute("insert or ignore into gone_since values(?,?)", (repo, time.time()))
            since = self.db.execute("select since from gone_since where repo=?", (repo,)).fetchone()[0]
            return since < time.time() - grace_days * 86400

    def record_published(self, repo, commit, psha) -> None:
        """Which policy the check published for this commit was decided under (per commit, so one pull request's fresh decision never hides that another still shows an older one)."""
        self.q("insert or replace into published_policy values(?,?,?)", repo, commit, psha)

    def stale_commits(self, repo, psha, days=45, limit=2000) -> list:
        """Commits with a pull-request receipt received within `days` whose published decision was NOT made under policy `psha` (or never recorded), newest first."""
        return [c for (c,) in self.q("select r.commit_sha from receipts r where r.repo=? and r.pr is not null and r.received > ? "
                                     "and not exists (select 1 from published_policy p where p.repo=r.repo and p.commit_sha=r.commit_sha and p.psha=?) "
                                     "group by r.commit_sha order by max(r.received) desc limit ?", repo, time.time() - days * 86400, psha, int(limit))]

    def was_notified(self, repo, commit, key) -> bool:
        return bool(self.q("select 1 from notified where repo=? and commit_sha=? and key=?", repo, commit, key))

    def mark_notified(self, repo, commit, key) -> None:
        self.q("insert or ignore into notified values(?,?,?,?)", repo, commit, key, time.time())

    def get_meta(self, k, default=None):
        r = self.q("select v from meta where k=?", k)
        return r[0][0] if r else default

    def set_meta(self, k, v):
        self.q("insert or replace into meta values(?,?)", k, str(v))

    def prune_deliveries(self, older_than_days: int = 14) -> int:
        with self.lock:
            return self.db.execute("delete from deliveries where at < ?", (time.time() - older_than_days * 86400,)).rowcount

    def purge_expired(self, days_by_plan: dict, default_days: int) -> int:
        """Delete receipts (and their acknowledgements) older than the retention of each repository's plan. -> number of receipts removed."""
        removed = 0
        for (repo,) in self.q("select distinct repo from receipts"):
            days = days_by_plan.get(self.retention_plan(repo), default_days)
            cutoff = time.time() - days * 86400
            with self.lock:
                ids = [i for (i,) in self.db.execute("select id from receipts where repo=? and received < ?", (repo, cutoff)).fetchall()]
                for i in ids:
                    self.db.execute("delete from acks where repo=? and receipt_id=?", (repo, i))
                    self.db.execute("delete from receipts where repo=? and id=?", (repo, i))
                self.db.execute("delete from published_policy where repo=? and commit_sha not in (select commit_sha from receipts where repo=?)", (repo, repo))
                self.db.execute("delete from notified where repo=? and at < ?", (repo, time.time() - 400 * 86400))
                removed += len(ids)
        return removed

    def backup(self, path: str) -> None:
        """A consistent copy of the database (SQLite's online backup, safe while the service runs)."""
        import sqlite3 as _s
        dest = _s.connect(path)
        try:
            with self.lock:
                self.db.backup(dest)
        finally:
            dest.close()

    def stats(self) -> dict:
        one = lambda sql: self.q(sql)[0][0]
        return {"repositories": one("select count(distinct repo) from receipts"), "receipts": one("select count(*) from receipts"), "acknowledgements": one("select count(*) from acks"),
                "installations": one("select count(*) from installs where deleted_at is null"), "paid_accounts": one("select count(*) from plans where plan != 'free'")}

    def purge(self, older_than_days: int) -> int:
        cutoff = time.time() - older_than_days * 86400
        with self.lock:
            n = self.db.execute("delete from receipts where received < ?", (cutoff,)).rowcount
            self.db.execute("delete from acks where at < ?", (cutoff,))
            self.db.execute("delete from deliveries where at < ?", (cutoff,))
            return n
