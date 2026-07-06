from contextlib import asynccontextmanager
from datetime import datetime, UTC
import os
import time
import uuid

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response

from app.core.config import get_settings
from app.core.db import connect_db, disconnect_db
from app.core.logging import get_logger, set_trace_id
from app.core.metrics import metrics_payload, observe_request
from app.core.rate_limit import RateLimitMiddleware
from app.core.responses import standard_response

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            traces_sample_rate=0.1,
        )
    await connect_db()
    logger.info(
        "Startup complete env=%s frontend_url=%s backend_base_url=%s raw_FRONTEND_URL=%s",
        settings.environment,
        settings.frontend_url,
        settings.backend_base_url,
        os.environ.get("FRONTEND_URL", "<not set>"),
    )
    yield
    await disconnect_db()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Clendan API",
        version="1.0.0",
        description=(
            "Clendan AI Financial Agent OS — REST API.\n\n"
            "All dashboard endpoints require a Clerk JWT in the `Authorization: Bearer` header. "
            "Agent execution endpoints require `X-Tenant-ID` and `Idempotency-Key` headers. "
            "Every response follows the shape `{data, error, trace_id, timestamp}`."
        ),
        contact={"name": "Clendan Support", "email": "api@clendan.com"},
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_tags=[
            {"name": "health", "description": "Liveness and readiness probes."},
            {"name": "onboarding", "description": "Create tenant and user on first sign-in."},
            {"name": "dashboard", "description": "Aggregated stats, executions, approvals, audit trail, and tools."},
            {"name": "agents", "description": "Trigger agent tools. Idempotent via `Idempotency-Key`."},
            {"name": "approvals", "description": "Respond to pending human-approval requests."},
            {"name": "integrations", "description": "Manage Plaid, Xero, and QuickBooks connections."},
            {"name": "tenants", "description": "Tenant and tool configuration."},
        ],
    )

    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def inject_trace_id(request: Request, call_next):
        trace_id = request.headers.get("X-Trace-ID") or str(uuid.uuid4())
        set_trace_id(trace_id)
        logger.info(
            "http_request",
            extra={"method": request.method, "path": request.url.path, "trace_id": trace_id},
        )
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:
            logger.error(
                "http_unhandled_exception",
                extra={"method": request.method, "path": request.url.path, "error": str(exc)},
                exc_info=True,
            )
            raise
        finally:
            # Label by matched route template (low cardinality), not the raw URL.
            route = request.scope.get("route")
            path_template = getattr(route, "path", None) or request.url.path
            observe_request(request.method, path_template, status_code, time.perf_counter() - start)
        response.headers["X-Trace-ID"] = trace_id
        logger.info(
            "http_response",
            extra={"method": request.method, "path": request.url.path, "status": response.status_code},
        )
        return response

    @app.get("/", include_in_schema=False)
    async def root():
        s = get_settings()
        return HTMLResponse(content=f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>Clendan API</title>
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Syne:wght@700;800&display=swap" rel="stylesheet"/>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#0a0a0a;color:#f0f0f0;font-family:'IBM Plex Mono',monospace;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:32px}}
    .wrap{{max-width:640px;width:100%}}
    .logo{{display:flex;align-items:center;gap:10px;margin-bottom:48px}}
    .logo svg{{width:28px;height:28px}}
    .logo-text{{font-family:'Syne',sans-serif;font-weight:800;font-size:20px;color:#f0f0f0;letter-spacing:-0.5px}}
    h1{{font-family:'Syne',sans-serif;font-weight:800;font-size:32px;color:#f0f0f0;margin-bottom:8px;letter-spacing:-1px}}
    .sub{{font-size:13px;color:#5d6b7a;margin-bottom:40px;line-height:1.6}}
    .status{{display:inline-flex;align-items:center;gap:6px;font-size:11px;color:#00C853;background:rgba(0,200,83,0.08);border:1px solid rgba(0,200,83,0.2);padding:4px 10px;border-radius:2px;margin-bottom:40px}}
    .dot{{width:6px;height:6px;border-radius:50%;background:#00C853;animation:pulse 2s infinite}}
    @keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:0.4}}}}
    .links{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:40px}}
    .link{{display:block;padding:16px;background:#111111;border:1px solid #2c2c2c;color:#f0f0f0;text-decoration:none;transition:border-color 0.15s}}
    .link:hover{{border-color:#00C853}}
    .link-label{{font-size:11px;color:#5d6b7a;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px}}
    .link-title{{font-size:13px;font-weight:500;color:#f0f0f0}}
    .meta{{border-top:1px solid #1a1a1a;padding-top:24px;display:flex;flex-direction:column;gap:8px}}
    .meta-row{{display:flex;justify-content:space-between;font-size:11px}}
    .meta-key{{color:#5d6b7a}}
    .meta-val{{color:#f0f0f0;font-family:'IBM Plex Mono',monospace}}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="logo">
      <svg viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M14 2L4 7V14C4 19.5 8.5 24.7 14 26C19.5 24.7 24 19.5 24 14V7L14 2Z" stroke="#00C853" stroke-width="1.5" stroke-linejoin="round"/>
        <path d="M10 14L13 17L18 11" stroke="#00C853" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      <span class="logo-text">clendan.</span>
    </div>
    <h1>Clendan API</h1>
    <p class="sub">AI Financial Agent OS — REST API v1.0.0<br/>All responses follow <code style="color:#00C853">{{data, error, trace_id, timestamp}}</code></p>
    <div class="status"><span class="dot"></span>operational &nbsp;·&nbsp; {s.environment}</div>
    <div class="links">
      <a class="link" href="/docs">
        <div class="link-label">Interactive</div>
        <div class="link-title">Swagger UI →</div>
      </a>
      <a class="link" href="/redoc">
        <div class="link-label">Reference</div>
        <div class="link-title">ReDoc →</div>
      </a>
      <a class="link" href="/health">
        <div class="link-label">Endpoint</div>
        <div class="link-title">Health check →</div>
      </a>
      <a class="link" href="/ready">
        <div class="link-label">Endpoint</div>
        <div class="link-title">Readiness →</div>
      </a>
    </div>
    <div class="meta">
      <div class="meta-row"><span class="meta-key">base url</span><span class="meta-val">{s.backend_base_url}</span></div>
      <div class="meta-row"><span class="meta-key">dashboard</span><span class="meta-val">{s.frontend_url}/dashboard</span></div>
      <div class="meta-row"><span class="meta-key">support</span><span class="meta-val">api@clendan.com</span></div>
    </div>
  </div>
</body>
</html>""")

    @app.get("/metrics", include_in_schema=False)
    async def metrics():
        payload, content_type = metrics_payload()
        return Response(content=payload, media_type=content_type)

    @app.get("/.well-known/security.txt", include_in_schema=False)
    async def security_txt():
        # RFC 9116 — the canonical copy lives on the primary domain; this makes
        # the API host advertise the same disclosure contact.
        body = (
            "Contact: mailto:security@clendan.com\n"
            "Expires: 2027-07-06T00:00:00.000Z\n"
            "Preferred-Languages: en\n"
            "Canonical: https://clendan.com/.well-known/security.txt\n"
            "Policy: https://clendan.com/security-policy\n"
        )
        return Response(content=body, media_type="text/plain; charset=utf-8")

    @app.get("/health", tags=["health"])
    async def health():
        s = get_settings()
        return standard_response(data={
            "status": "ok",
            "environment": s.environment,
            "frontend_url": s.frontend_url,
            "backend_base_url": s.backend_base_url,
        })

    @app.get("/ready", tags=["health"])
    async def ready():
        checks: dict = {}

        # DB check
        try:
            from app.core.db import get_db
            db = get_db()
            await db.execute_raw("SELECT 1")
            checks["db"] = "ok"
        except Exception as exc:
            checks["db"] = f"error: {type(exc).__name__}"

        # Redis check
        try:
            from app.queue.pool import get_queue_pool
            pool = await get_queue_pool()
            await pool.ping()
            checks["redis"] = "ok"
        except Exception as exc:
            checks["redis"] = f"error: {type(exc).__name__}"

        all_ok = all(v == "ok" for v in checks.values())
        return standard_response(
            data={
                "status": "ready" if all_ok else "degraded",
                "checks": checks,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

    from app.api.v1.router import v1_router  # noqa: E402 — imported here to avoid circular deps
    app.include_router(v1_router)

    return app


app = create_app()
