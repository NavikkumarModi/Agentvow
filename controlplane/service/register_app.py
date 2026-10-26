"""Register the GitHub App through GitHub's *manifest flow*, so that no secret is ever typed or downloaded by hand: this script serves one local page that posts the App's manifest to GitHub; after you
(signed in to GitHub) press "Create GitHub App", GitHub redirects back here with a one-time code, and the script exchanges it for the App id, private key and webhook secret and writes them to files only
you can read (mode 600). Nothing is printed except the App's name and address.

    python -m controlplane.service.register_app --tunnel https://x.trycloudflare.com --repo you/agentvow-live-test --out ~/agentvow-cp

Writes OUT/app.private-key.pem and OUT/cp.env (load it with `set -a; . OUT/cp.env; set +a`). Local use only: it listens on 127.0.0.1."""
import argparse
import html
import json
import os
import re
import secrets
import sys
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

PERMISSIONS = {"checks": "write", "contents": "read", "issues": "write", "pull_requests": "write", "metadata": "read"}
EVENTS = ["pull_request", "issue_comment"]
CONVERT = "https://api.github.com/app-manifests/{code}/conversions"


def manifest(name: str, home: str, tunnel: str, redirect: str) -> dict:
    return {"name": name[:34], "url": home, "hook_attributes": {"url": tunnel.rstrip("/") + "/v1/webhook", "active": True}, "redirect_url": redirect, "public": False,
            "default_permissions": PERMISSIONS, "default_events": EVENTS}


def convert(code: str) -> dict:
    req = urllib.request.Request(CONVERT.format(code=code), data=b"", method="POST", headers={"Accept": "application/vnd.github+json", "User-Agent": "agentvow-register-app"})
    with urllib.request.urlopen(req, timeout=20) as r:   # noqa: S310 (fixed https GitHub URL)
        return json.loads(r.read(200_000))


def write_private(path: str, text: str) -> None:
    """A fresh file, mode 600 from the first byte; an existing file or a link in its place is removed first (never written through)."""
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(text)


def save(out: str, repo: str, app: dict, audience: str, workflow_ref: str) -> str:
    os.makedirs(out, mode=0o700, exist_ok=True)
    os.chmod(out, 0o700)
    pem, env = os.path.join(out, "app.private-key.pem"), os.path.join(out, "cp.env")
    write_private(pem, app["pem"])
    write_private(env, "\n".join([f"AGENTVOW_CP_APP_ID={app['id']}", f"AGENTVOW_CP_PRIVATE_KEY_FILE={pem}", f"AGENTVOW_CP_WEBHOOK_SECRET={app['webhook_secret']}", f"AGENTVOW_CP_AUDIENCE={audience}",
                                  f"AGENTVOW_CP_TRUSTED_WORKFLOWS={workflow_ref}", f"AGENTVOW_CP_DB={os.path.join(out, 'cp.db')}", ""]))
    return env


def make_handler(page: str, state: str, on_app, allowed_hosts=()):
    class H(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype="text/html; charset=utf-8"):
            b = body.encode()
            self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(b))); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(b)

        def do_GET(self):
            if self.headers.get("Host", "") not in allowed_hosts:   # DNS rebinding: a page on another name must not reach this local server
                return self._send(403, "<p>Unexpected Host header.</p>")
            u = urlparse(self.path)
            if u.path == "/":
                return self._send(200, page)
            if u.path == "/callback":
                q = parse_qs(u.query)
                if q.get("state", [""])[0] != state or not q.get("code"):
                    return self._send(400, "<p>Unexpected callback; nothing was done.</p>")
                try:
                    msg = on_app(q["code"][0])
                except Exception as e:
                    return self._send(502, f"<p>Could not finish registration: {html.escape(type(e).__name__)}</p>")
                return self._send(200, f"<p>{html.escape(msg)}</p><p>You can close this tab.</p>")
            self._send(404, "<p>not found</p>")

        def log_message(self, *a):
            pass
    return H


def main(argv=None, convert_fn=convert, serve=True):
    ap = argparse.ArgumentParser(prog="register_app")
    ap.add_argument("--tunnel", required=True, help="public https address of this machine's service (webhook target)")
    ap.add_argument("--repo", required=True, help="the throwaway repository, owner/name")
    ap.add_argument("--out", required=True)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--audience", default="agentvow-control-plane")
    ap.add_argument("--workflow-sha", required=True, help="the 40-character commit sha of gate-service.yml that callers pin (the service refuses a tag or branch)")
    ap.add_argument("--name")
    a = ap.parse_args(argv)
    if not a.tunnel.startswith("https://"):
        ap.error("--tunnel must be an https address")
    if not re.fullmatch(r"[0-9a-f]{40}", a.workflow_sha):
        ap.error("--workflow-sha must be a full 40-character commit sha")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}", a.repo):
        ap.error("--repo must look like owner/name")
    owner = a.repo.split("/")[0]
    state = secrets.token_urlsafe(24)
    redirect = f"http://127.0.0.1:{a.port}/callback"
    m = manifest(a.name or f"agentvow-{owner}-test", f"https://github.com/{a.repo}", a.tunnel, redirect)
    page = ("<!doctype html><meta charset=utf-8><title>Register the Agentvow test App</title><p>Sending the App manifest to GitHub...</p>"
            f"<form id=f method=post action=\"https://github.com/settings/apps/new?state={html.escape(state)}\"><input type=hidden name=manifest value=\"{html.escape(json.dumps(m))}\"><noscript><button>Continue to GitHub</button></noscript></form>"
            "<script>document.getElementById('f').submit()</script>")
    done = {}

    def on_app(code):
        app = convert_fn(code)
        env = save(a.out, a.repo, app, a.audience, f"{a.repo}/.github/workflows/gate-service.yml@{a.workflow_sha}")
        done.update(app=app, env=env)
        return f"Registered {app.get('name')}. Install it on {a.repo}: {app.get('html_url')}/installations/new"
    if not serve:
        return make_handler, page, state, on_app, done, (f"127.0.0.1:{a.port}", f"localhost:{a.port}")
    srv = HTTPServer(("127.0.0.1", a.port), make_handler(page, state, on_app, (f"127.0.0.1:{a.port}", f"localhost:{a.port}")))
    print(f"Open http://127.0.0.1:{a.port}/ in the browser where you are signed in to GitHub, and press 'Create GitHub App'.", flush=True)
    while "app" not in done:
        srv.handle_request()
    app = done["app"]
    print(f"Registered: {app.get('name')} (slug {app.get('slug')}, id {app.get('id')}).\nInstall it on {a.repo}: https://github.com/apps/{app.get('slug')}/installations/new\nEnvironment file: {done['env']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
