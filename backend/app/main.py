from contextlib import asynccontextmanager
from datetime import datetime, UTC
import uuid

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.db import connect_db, disconnect_db
from app.core.logging import get_logger, set_trace_id
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
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
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

    @app.get("/health")
    async def health():
        return standard_response(data={"status": "ok"})

    @app.get("/ready")
    async def ready():
        return standard_response(
            data={"status": "ready", "timestamp": datetime.now(UTC).isoformat()}
        )

    return app


app = create_app()

from app.api.v1.router import v1_router  # noqa: E402
app.include_router(v1_router, prefix="/v1")
