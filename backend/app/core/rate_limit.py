"""
Redis sliding-window rate limiter middleware.
Applied globally - parse endpoints get a tighter limit than general API.
"""
import asyncio
import hashlib
import time
from typing import Callable

import redis.asyncio as aioredis
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.core.logging import get_logger, get_trace_id

_logger = get_logger(__name__)

# Reuse a single Redis client (and its connection pool) across requests rather
# than constructing one per request - building a client per call churns
# connections and adds latency on every request.
_redis_client: aioredis.Redis | None = None


def _get_redis_client() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            get_settings().redis_public_url,
            socket_connect_timeout=2,
            socket_timeout=2,
            retry_on_timeout=False,
        )
    return _redis_client

# Exact paths exempt from rate limiting
_EXEMPT = {"/health", "/ready"}

# Path prefixes also exempt
_EXEMPT_PREFIXES = ("/integrations", "/webhooks")

# (requests, window_seconds) per path prefix - first match wins
_LIMITS: list[tuple[str, int, int]] = [
    ("/parse/",   20,  60),   # 20 req/min  - Claude vision is expensive
    ("/agents/",  30,  60),   # 30 req/min  - queue submissions
    ("/execute",  60,  60),   # 60 req/min  - agent executions (each triggers a job)
    ("/",        200,  60),   # 200 req/min - all other endpoints
]


def _get_limit(path: str) -> tuple[int, int]:
    for prefix, limit, window in _LIMITS:
        if path.startswith(prefix):
            return limit, window
    return 1000, 60  # default


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding-window rate limiter backed by Redis.
    Key: rate:<identifier>:<path_bucket>
    Identifier: X-Tenant-ID header or client IP.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        if path in _EXEMPT or path.startswith(_EXEMPT_PREFIXES):
            return await call_next(request)

        auth = request.headers.get("Authorization", "")
        if auth.startswith("ck_live_"):
            identifier = f"apikey:{hashlib.sha256(auth.encode()).hexdigest()[:16]}"
        else:
            identifier = (
                request.headers.get("X-Tenant-ID")
                or (request.client.host if request.client else "unknown")
            )

        limit, window = _get_limit(path)
        bucket = path.split("/")[2] if len(path.split("/")) > 2 else "root"
        redis_key = f"rate:{identifier}:{bucket}"

        try:
            client = _get_redis_client()

            now = int(time.time())
            window_start = now - window

            async def _check():
                pipe = client.pipeline()
                pipe.zremrangebyscore(redis_key, 0, window_start)
                pipe.zadd(redis_key, {str(now): now})
                pipe.zcard(redis_key)
                pipe.expire(redis_key, window)
                return await pipe.execute()

            results = await asyncio.wait_for(_check(), timeout=3.0)
            count = results[2]

            if count > limit:
                _logger.warning(
                    "rate_limit_exceeded",
                    extra={"identifier": identifier, "path": path, "count": count, "limit": limit},
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "data": None,
                        "error": f"Rate limit exceeded. Max {limit} requests per {window}s.",
                        "trace_id": get_trace_id(),
                        "timestamp": str(now),
                    },
                    headers={"Retry-After": str(window)},
                )
        except Exception as exc:
            # Rate limiter failure must never block a request
            _logger.error("rate_limit_check_failed", extra={"error": str(exc)})

        return await call_next(request)
