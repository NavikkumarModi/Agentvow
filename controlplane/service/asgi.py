"""ASGI adapter (Starlette). Run: `uvicorn controlplane.service.asgi:app`. Configuration comes from environment variables (docs/CONTROLPLANE_PHASE1.md); the app refuses to start without them."""
import os

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
    for k in ("AGENTVOW_CP_APP_ID", "AGENTVOW_CP_PRIVATE_KEY", "AGENTVOW_CP_WEBHOOK_SECRET", "AGENTVOW_CP_TRUSTED_WORKFLOWS", "AGENTVOW_CP_AUDIENCE"):
        if not env.get(k):
            raise RuntimeError(f"missing environment variable {k}")
    cfg = Config(trusted_workflows=frozenset(x.strip() for x in env["AGENTVOW_CP_TRUSTED_WORKFLOWS"].split(",") if x.strip()), webhook_secret=env["AGENTVOW_CP_WEBHOOK_SECRET"].encode())
    return Service(cfg, OidcVerifier(env["AGENTVOW_CP_AUDIENCE"]), GitHub(env["AGENTVOW_CP_APP_ID"], env["AGENTVOW_CP_PRIVATE_KEY"].replace("\\n", "\n").encode()), Store(env.get("AGENTVOW_CP_DB", "/data/controlplane.db")))


def make_app(service: Service) -> Starlette:
    async def body(request: Request) -> bytes:
        data = b""
        async for chunk in request.stream():
            data += chunk
            if len(data) > 1_000_001:
                break
        return data

    def lower(request):
        return {k.lower(): v for k, v in request.headers.items()}

    async def receipts(request):
        code, obj = await run_in_threadpool(service.post_receipt, lower(request), await body(request))
        return JSONResponse(obj, status_code=code)

    async def webhook(request):
        code, obj = await run_in_threadpool(service.webhook, lower(request), await body(request))
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


def app(scope, receive, send):   # lazily built so that importing the module (tests, tooling) does not require configuration
    global _app
    if "_app" not in globals():
        globals()["_app"] = make_app(build_service())
    return _app(scope, receive, send)
