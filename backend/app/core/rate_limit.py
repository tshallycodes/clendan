"""
Redis sliding-window rate limiter middleware.
Applied globally — parse endpoints get a tighter limit than general API.
"""
import time
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import get_logger, get_trace_id

_logger = get_logger(__name__)

# Paths exempt from rate limiting
_EXEMPT = {"/health", "/ready"}

# (requests, window_seconds) per path prefix
_LIMITS: list[tuple[str, int, int]] = [
    ("/v1/parse/", 20, 60),    # 20 req/min — Claude vision is expensive
    ("/v1/agents/", 30, 60),   # 30 req/min — queue submissions
    ("/v1/", 200, 60),         # 200 req/min — all other v1 endpoints
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

        if path in _EXEMPT:
            return await call_next(request)

        identifier = (
            request.headers.get("X-Tenant-ID")
            or (request.client.host if request.client else "unknown")
        )

        limit, window = _get_limit(path)
        bucket = path.split("/")[2] if len(path.split("/")) > 2 else "root"
        redis_key = f"rate:{identifier}:{bucket}"

        try:
            from app.queue.pool import get_queue_pool
            pool = await get_queue_pool()

            now = int(time.time())
            window_start = now - window

            pipe = pool.pipeline()
            pipe.zremrangebyscore(redis_key, 0, window_start)
            pipe.zadd(redis_key, {str(now): now})
            pipe.zcard(redis_key)
            pipe.expire(redis_key, window)
            results = await pipe.execute()

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
