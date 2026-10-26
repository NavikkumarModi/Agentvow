"""Configuration check, run BEFORE pointing GitHub at the service: `python -m controlplane.service.smoke`. It builds the service from the environment (so a missing variable fails here), signs an App JWT with your
private key and asks GitHub who the App is (GET /app). It prints the App's name, its granted permissions and subscribed events and says which required ones are missing. It sends no customer data and changes nothing."""
import os
import sys

from .asgi import build_service

REQUIRED_PERMISSIONS = {"checks": "write", "contents": "read", "pull_requests": "write", "issues": "write", "metadata": "read"}
REQUIRED_EVENTS = {"pull_request", "issue_comment"}
RECOMMENDED_EVENTS = {"push": "without it, open pull requests keep their old decision when the policy file changes, until the next receipt"}
RANK = {"read": 1, "write": 2, "admin": 3}


def problems(app: dict) -> list:
    out = []
    perms = app.get("permissions") or {}
    for name, level in REQUIRED_PERMISSIONS.items():
        if RANK.get(perms.get(name), 0) < RANK[level]:
            out.append(f"permission `{name}` must be at least `{level}` (it is `{perms.get(name, 'none')}`)")
    for ev in sorted(REQUIRED_EVENTS - set(app.get("events") or [])):
        out.append(f"event `{ev}` is not subscribed")
    return out


def main(env=os.environ, out=sys.stdout) -> int:
    try:
        svc = build_service(env)
    except Exception as e:
        print(f"CONFIG: {type(e).__name__}: {e}", file=out)
        return 2
    st, app = svc.gh._call("GET", "/app", svc.gh._app_jwt(), auth="bearer")
    if st != 200:
        print(f"GitHub refused the App credentials (HTTP {st}): check AGENTVOW_CP_APP_ID and the private key.", file=out)
        return 2
    print(f"App: {app.get('name')} (slug {app.get('slug')}, id {app.get('id')}, owner {(app.get('owner') or {}).get('login')})", file=out)
    print(f"Permissions: {app.get('permissions')}\nEvents: {app.get('events')}", file=out)
    for ev, why in RECOMMENDED_EVENTS.items():
        if ev not in (app.get("events") or []):
            print(f"NOTE: event `{ev}` is not subscribed: {why}.", file=out)
    bad = problems(app)
    for b in bad:
        print("PROBLEM:", b, file=out)
    print("OK: the App has what the service needs." if not bad else "Fix the problems above in the App's settings, then run this again.", file=out)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
