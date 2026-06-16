import json
from typing import Optional

from arq import create_pool
from arq.connections import RedisSettings, ArqRedis

from app.core.config import get_settings
from app.core.logging import get_logger

_logger = get_logger(__name__)

DLQ_KEY = "clendan:dlq"

_pool: Optional[ArqRedis] = None


def _redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(get_settings().redis_public_url)


async def get_queue_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        _pool = await create_pool(_redis_settings())
    return _pool


async def close_queue_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def push_to_dlq(job_id: str, function_name: str, error: str) -> None:
    """Store a failed job in the dead-letter queue for later inspection or replay."""
    pool = await get_queue_pool()
    entry = json.dumps({"job_id": job_id, "function": function_name, "error": error})
    await pool.rpush(DLQ_KEY, entry)
    _logger.error(
        "job_moved_to_dlq",
        extra={"job_id": job_id, "function": function_name, "error": error},
    )
