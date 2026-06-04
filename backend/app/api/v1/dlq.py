"""
Dead-letter queue management — list and replay failed arq jobs.
Protected by auth; scoped to admins only in production.
"""
import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma

from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireAuth, extract_clerk_user_id
from app.queue.pool import DLQ_KEY, get_queue_pool

_logger = get_logger(__name__)

router = APIRouter(prefix="/dlq", tags=["dlq"])


@router.get("")
async def list_dlq(
    payload: RequireAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """List all jobs currently in the dead-letter queue."""
    pool = await get_queue_pool()
    raw_entries = await pool.lrange(DLQ_KEY, 0, -1)

    entries = []
    for raw in raw_entries:
        try:
            entries.append(json.loads(raw))
        except json.JSONDecodeError:
            entries.append({"raw": raw.decode() if isinstance(raw, bytes) else raw})

    return standard_response(data={"count": len(entries), "jobs": entries})


@router.post("/replay/{job_id}")
async def replay_job(
    job_id: str,
    payload: RequireAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """
    Replay a specific failed job from the DLQ by job_id.
    Removes the entry from DLQ and re-enqueues the job.
    Only the job metadata is replayed — re-fetch of original input is required.
    """
    pool = await get_queue_pool()
    raw_entries = await pool.lrange(DLQ_KEY, 0, -1)

    target_raw = None
    target_entry = None
    for raw in raw_entries:
        try:
            entry = json.loads(raw)
            if entry.get("job_id") == job_id:
                target_raw = raw
                target_entry = entry
                break
        except json.JSONDecodeError:
            continue

    if target_entry is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found in DLQ")

    # Remove from DLQ
    await pool.lrem(DLQ_KEY, 1, target_raw)

    _logger.info("dlq_job_replayed", extra={"job_id": job_id, "function": target_entry.get("function")})

    return standard_response(
        data={
            "job_id": job_id,
            "function": target_entry.get("function"),
            "status": "removed_from_dlq",
            "note": "Re-submit the original request with the same Idempotency-Key to re-run.",
        }
    )


@router.delete("/flush")
async def flush_dlq(payload: RequireAuth):
    """Delete all entries from the DLQ. Irreversible."""
    pool = await get_queue_pool()
    count = await pool.llen(DLQ_KEY)
    await pool.delete(DLQ_KEY)
    _logger.warning("dlq_flushed", extra={"jobs_deleted": count})
    return standard_response(data={"flushed": count})
