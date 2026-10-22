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
create table if not exists receipts(id text not null, repo text not null, commit_sha text not null, pr integer, body text not null, received real not null, run_order integer not null, primary key(repo, id));
create index if not exists receipts_commit on receipts(repo, commit_sha, run_order desc, received desc);
create table if not exists checks(repo text not null, commit_sha text not null, check_id integer not null, primary key(repo, commit_sha));
create table if not exists acks(repo text not null, receipt_id text not null, by text not null, note text, at real not null);
create index if not exists acks_receipt on acks(repo, receipt_id);
create table if not exists plans(repo text primary key, plan text not null, until real);
create table if not exists keys(repo text primary key, key_hash text not null);
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

    # ---- receipts
    def add_receipt(self, repo, rid, commit, pr, body: dict, run_order: int) -> bool:
        """-> True when new, False when this exact receipt was already stored."""
        raw = json.dumps(body, sort_keys=True)
        with self.lock:
            cur = self.db.execute("insert or ignore into receipts values(?,?,?,?,?,?,?)", (rid, repo, commit, pr, raw, time.time(), run_order))
            return cur.rowcount == 1

    def latest_receipt(self, repo, commit):
        r = self.q("select id, body from receipts where repo=? and commit_sha=? order by run_order desc, received desc limit 1", repo, commit)
        return (r[0][0], json.loads(r[0][1])) if r else (None, None)

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

    def issue_key(self, repo) -> str:
        key = "avk_" + secrets.token_urlsafe(32)
        self.q("insert or replace into keys values(?,?)", repo, hashlib.sha256(key.encode()).hexdigest())
        return key

    def key_ok(self, repo, presented: str) -> bool:
        r = self.q("select key_hash from keys where repo=?", repo)
        return bool(r) and hmac.compare_digest(r[0][0], hashlib.sha256(str(presented).encode()).hexdigest())

    def count_usage(self, repo, nbytes) -> tuple:
        """-> (receipts this month, bytes this month) after adding one."""
        m = time.strftime("%Y-%m")
        self.q("insert into usage values(?,?,1,?) on conflict(repo, month) do update set n = n + 1, bytes = bytes + excluded.bytes", repo, m, nbytes)
        n, b = self.q("select n, bytes from usage where repo=? and month=?", repo, m)[0]
        return n, b

    def usage(self, repo):
        r = self.q("select n, bytes from usage where repo=? and month=?", repo, time.strftime("%Y-%m"))
        return r[0] if r else (0, 0)

    def purge(self, older_than_days: int) -> int:
        cutoff = time.time() - older_than_days * 86400
        with self.lock:
            n = self.db.execute("delete from receipts where received < ?", (cutoff,)).rowcount
            self.db.execute("delete from acks where at < ?", (cutoff,))
            return n
