from contextlib import asynccontextmanager
from datetime import datetime, UTC
import uuid

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.db import connect_db, disconnect_db
from app.core.logging import get_logger, set_trace_id
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
    logger.info("Startup complete")
    yield
    await disconnect_db()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()
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

    logger.info("cors_allowed_origins frontend_url=%s cors_origins=%s", settings.frontend_url, settings.cors_origins)

    _allowed_origins = [settings.frontend_url] if settings.frontend_url else []
    if settings.cors_origins:
        _allowed_origins.extend(
            o.strip() for o in settings.cors_origins.split(",") if o.strip()
        )

    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins or ["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def inject_trace_id(request: Request, call_next):
        trace_id = request.headers.get("X-Trace-ID") or str(uuid.uuid4())
        set_trace_id(trace_id)
        response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id
        return response

    @app.get("/health", tags=["health"])
    async def health():
        return standard_response(data={"status": "ok"})

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
    app.include_router(v1_router, prefix="/v1")

    return app


app = create_app()
