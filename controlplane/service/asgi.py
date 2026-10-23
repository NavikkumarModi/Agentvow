"""ASGI adapter (Starlette). Run: `uvicorn controlplane.service.asgi:app`. Configuration comes from environment variables (docs/CONTROLPLANE_PHASE1.md); the app refuses to start without them."""
import os
import threading
import time
from pathlib import Path

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, PlainTextResponse
from starlette.routing import Route

import logging

from .core import Config, Service
from .github import GitHub
from .oidc import OidcVerifier
from .store import Store


def build_service(env=os.environ) -> Service:
    for k in ("AGENTVOW_CP_APP_ID", "AGENTVOW_CP_TRUSTED_WORKFLOWS", "AGENTVOW_CP_AUDIENCE"):
        if not env.get(k):
            raise RuntimeError(f"missing environment variable {k}")
    secret = env.get("AGENTVOW_CP_WEBHOOK_SECRET") or (Path(env["AGENTVOW_CP_WEBHOOK_SECRET_FILE"]).read_text().strip() if env.get("AGENTVOW_CP_WEBHOOK_SECRET_FILE") else "")
    if not secret:
        raise RuntimeError("missing environment variable AGENTVOW_CP_WEBHOOK_SECRET (or AGENTVOW_CP_WEBHOOK_SECRET_FILE)")
    pem = env.get("AGENTVOW_CP_PRIVATE_KEY") or (Path(env["AGENTVOW_CP_PRIVATE_KEY_FILE"]).read_text() if env.get("AGENTVOW_CP_PRIVATE_KEY_FILE") else "")
    if not pem:
        raise RuntimeError("missing environment variable AGENTVOW_CP_PRIVATE_KEY (or AGENTVOW_CP_PRIVATE_KEY_FILE, preferred: the key is then not in the process environment)")
    cfg = Config(policy_path=env.get("AGENTVOW_CP_POLICY_PATH", ".agentvow/policy.json"), trusted_workflows=frozenset(x.strip() for x in env["AGENTVOW_CP_TRUSTED_WORKFLOWS"].split(",") if x.strip()), webhook_secret=secret.encode())
    return Service(cfg, OidcVerifier(env["AGENTVOW_CP_AUDIENCE"]), GitHub(env["AGENTVOW_CP_APP_ID"], pem.replace("\\n", "\n").encode()), Store(env.get("AGENTVOW_CP_DB", "/data/controlplane.db")))


def make_app(service: Service) -> Starlette:
    async def body(request: Request, limit: int) -> bytes | None:
        """The request body, or None when it is larger than `limit` (refused from Content-Length when declared, and never read past the limit)."""
        try:
            if int(request.headers.get("content-length", "0") or 0) > limit:
                return None
        except ValueError:
            return None
        data = b""
        async for chunk in request.stream():
            data += chunk
            if len(data) > limit:
                return None
        return data

    def lower(request):
        return {k.lower(): v for k, v in request.headers.items()}

    log = logging.getLogger("agentvow.controlplane")

    def answer(route, code, obj):
        if code >= 300:   # the reason only (never a token or a receipt body): this is what a live test reads
            log.warning("%s -> %s %s", route, code, str(obj.get("error") or obj.get("refused") or obj.get("ignored") or "")[:200])
        return JSONResponse(obj, status_code=code)

    async def receipts(request):
        data = await body(request, service.cfg.max_body)
        if data is None:
            return JSONResponse({"error": "receipt too large"}, status_code=413)
        code, obj = await run_in_threadpool(service.post_receipt, lower(request), data)
        return answer("receipts", code, obj)

    async def webhook(request):
        data = await body(request, 1_000_000)
        if data is None:
            return JSONResponse({"error": "payload too large"}, status_code=413)
        code, obj = await run_in_threadpool(service.webhook, lower(request), data)
        return answer("webhook", code, obj)

    async def check(request):
        code, obj = await run_in_threadpool(service.check, request.query_params.get("repo", ""), request.query_params.get("commit", ""), lower(request))
        return JSONResponse(obj, status_code=code)

    async def audit(request):
        code, obj = await run_in_threadpool(service.audit, request.query_params.get("repo", ""), lower(request), request.query_params.get("format", "json"))
        return JSONResponse(obj, status_code=code)

    FORM = ("<!doctype html><meta charset=utf-8><title>Agentvow receipts</title><body style='font:14px system-ui;margin:2rem'><h1>Agentvow receipts</h1>"
            "<form method=post action=/dashboard><p><label>Repository (owner/name)<br><input name=repo size=40 required></label></p>"
            "<p><label>Audit key<br><input name=key type=password size=40 required autocomplete=off></label></p><button>Show receipts</button></form>")
    SECURITY = {"Cache-Control": "no-store", "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"}

    async def dashboard_form(request):
        return HTMLResponse(FORM, headers=SECURITY)

    async def dashboard(request):
        from urllib.parse import parse_qs
        data = await body(request, 4096)   # the key travels in the POST body, never in a URL
        if data is None:
            return HTMLResponse("<p>too large</p>", status_code=413, headers=SECURITY)
        q = parse_qs(data.decode("utf-8", "replace"))
        code, page = await run_in_threadpool(service.dashboard, (q.get("repo") or [""])[0].strip(), (q.get("key") or [""])[0])
        return HTMLResponse(page, status_code=code, headers=SECURITY)

    async def health(request):
        return PlainTextResponse("ok")

    return Starlette(routes=[Route("/v1/receipts", receipts, methods=["POST"]), Route("/v1/webhook", webhook, methods=["POST"]), Route("/v1/check", check), Route("/v1/audit", audit), Route("/healthz", health), Route("/dashboard", dashboard_form), Route("/dashboard", dashboard, methods=["POST"])])


def create_app() -> Starlette:
    """Application factory (`uvicorn --factory controlplane.service.asgi:create_app`). Built eagerly, so a missing setting stops the process at start-up instead of failing every request."""
    service = build_service()

    ticks = [0]

    def loop():
        while True:
            time.sleep(60)
            service.reconcile()
            ticks[0] += 1
            if ticks[0] % 1440 == 0:   # daily
                service.maintain()
    threading.Thread(target=loop, daemon=True).start()   # retries check runs whose publish failed
    return make_app(service)
