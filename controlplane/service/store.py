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
        self.q("insert or replace into plans values(?,?,?)", repo, plan, until)

    def plan(self, repo) -> str:
        r = self.q("select plan, until from plans where repo=?", repo)
        return r[0][0] if r and (r[0][1] is None or r[0][1] > time.time()) else "free"

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

    def purge(self, older_than_days: int) -> int:
        cutoff = time.time() - older_than_days * 86400
        with self.lock:
            n = self.db.execute("delete from receipts where received < ?", (cutoff,)).rowcount
            self.db.execute("delete from acks where at < ?", (cutoff,))
            self.db.execute("delete from deliveries where at < ?", (cutoff,))
            return n
