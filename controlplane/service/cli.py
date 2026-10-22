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
    p = sub.add_parser("set-plan"); p.add_argument("repo"); p.add_argument("plan", choices=PLANS); p.add_argument("--days", type=int)   # must be 1 or more; omit for no end date
    k = sub.add_parser("issue-key"); k.add_argument("repo"); k.add_argument("--rotate", action="store_true", help="replace an existing key")
    sub.add_parser("purge").add_argument("days", type=int)
    sub.add_parser("unbind-repo").add_argument("repo")
    sub.add_parser("usage").add_argument("repo")
    a = ap.parse_args(argv)
    st = Store(a.db)
    if a.cmd == "set-plan":
        if a.days is not None and a.days < 1:
            ap.error("--days must be 1 or more (omit it for no end date)")
        st.set_plan(a.repo, a.plan, time.time() + a.days * 86400 if a.days is not None else None)
        print(f"{a.repo}: {a.plan}" + (f" for {a.days} days" if a.days is not None else ""))
    elif a.cmd == "issue-key":
        try:
            print(st.issue_key(a.repo, a.rotate))   # shown once; only its hash is stored
        except ValueError as e:
            ap.error(str(e))
    elif a.cmd == "unbind-repo":
        st.unbind_repo(a.repo)
        print(f"{a.repo}: numeric repository id forgotten; the next trusted receipt binds it again")
    elif a.cmd == "purge":
        print(f"removed {st.purge(a.days)} receipts older than {a.days} days")
    else:
        print("receipts, bytes this month:", st.usage(a.repo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
