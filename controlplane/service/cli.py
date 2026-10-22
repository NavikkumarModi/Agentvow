"""Operator commands: python -m controlplane.service.cli --db PATH {set-plan REPO PLAN [--days N] | issue-key REPO | purge DAYS | usage REPO}. Run on the host that holds the database; there is no remote admin interface."""
import argparse
import sys
import time

from .store import Store

PLANS = ("free", "team", "business")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="controlplane")
    ap.add_argument("--db", default="/data/controlplane.db")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("set-plan"); p.add_argument("repo"); p.add_argument("plan", choices=PLANS); p.add_argument("--days", type=int)
    sub.add_parser("issue-key").add_argument("repo")
    sub.add_parser("purge").add_argument("days", type=int)
    sub.add_parser("usage").add_argument("repo")
    a = ap.parse_args(argv)
    st = Store(a.db)
    if a.cmd == "set-plan":
        st.set_plan(a.repo, a.plan, time.time() + a.days * 86400 if a.days else None)
        print(f"{a.repo}: {a.plan}" + (f" for {a.days} days" if a.days else ""))
    elif a.cmd == "issue-key":
        print(st.issue_key(a.repo))   # shown once; only its hash is stored
    elif a.cmd == "purge":
        print(f"removed {st.purge(a.days)} receipts older than {a.days} days")
    else:
        print("receipts, bytes this month:", st.usage(a.repo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
