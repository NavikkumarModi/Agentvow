"""ASGI adapter (Starlette). Run: `uvicorn controlplane.service.asgi:app`. Configuration comes from environment variables (docs/CONTROLPLANE_PHASE1.md); the app refuses to start without them."""
import os
from pathlib import Path

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route

from .core import Config, Service
from .github import GitHub
from .oidc import OidcVerifier
from .store import Store


def build_service(env=os.environ) -> Service:
    for k in ("AGENTVOW_CP_APP_ID", "AGENTVOW_CP_WEBHOOK_SECRET", "AGENTVOW_CP_TRUSTED_WORKFLOWS", "AGENTVOW_CP_AUDIENCE"):
        if not env.get(k):
            raise RuntimeError(f"missing environment variable {k}")
    pem = env.get("AGENTVOW_CP_PRIVATE_KEY") or (Path(env["AGENTVOW_CP_PRIVATE_KEY_FILE"]).read_text() if env.get("AGENTVOW_CP_PRIVATE_KEY_FILE") else "")
    if not pem:
        raise RuntimeError("missing environment variable AGENTVOW_CP_PRIVATE_KEY (or AGENTVOW_CP_PRIVATE_KEY_FILE, preferred: the key is then not in the process environment)")
    cfg = Config(trusted_workflows=frozenset(x.strip() for x in env["AGENTVOW_CP_TRUSTED_WORKFLOWS"].split(",") if x.strip()), webhook_secret=env["AGENTVOW_CP_WEBHOOK_SECRET"].encode())
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

    async def receipts(request):
        data = await body(request, service.cfg.max_body)
        if data is None:
            return JSONResponse({"error": "receipt too large"}, status_code=413)
        code, obj = await run_in_threadpool(service.post_receipt, lower(request), data)
        return JSONResponse(obj, status_code=code)

    async def webhook(request):
        data = await body(request, 1_000_000)
        if data is None:
            return JSONResponse({"error": "payload too large"}, status_code=413)
        code, obj = await run_in_threadpool(service.webhook, lower(request), data)
        return JSONResponse(obj, status_code=code)

    async def check(request):
        code, obj = await run_in_threadpool(service.check, request.query_params.get("repo", ""), request.query_params.get("commit", ""), lower(request))
        return JSONResponse(obj, status_code=code)

    async def audit(request):
        code, obj = await run_in_threadpool(service.audit, request.query_params.get("repo", ""), lower(request), request.query_params.get("format", "json"))
        return JSONResponse(obj, status_code=code)

    async def health(request):
        return PlainTextResponse("ok")

    return Starlette(routes=[Route("/v1/receipts", receipts, methods=["POST"]), Route("/v1/webhook", webhook, methods=["POST"]), Route("/v1/check", check), Route("/v1/audit", audit), Route("/healthz", health)])


def create_app() -> Starlette:
    """Application factory (`uvicorn --factory controlplane.service.asgi:create_app`). Built eagerly, so a missing setting stops the process at start-up instead of failing every request."""
    return make_app(build_service())
