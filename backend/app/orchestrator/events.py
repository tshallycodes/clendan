"""
Shared helper for emitting orchestrator events from any source:
HTTP API, webhooks, sync jobs, cron triggers.
Centralises execution record creation and queue dispatch.
"""
from prisma import Prisma

from app.core.logging import get_logger
from app.orchestrator.orchestrator import EVENT_TO_WORKER
from app.queue.pool import get_queue_pool

logger = get_logger(__name__)


async def enqueue_orchestrator_event(
    *,
    tenant_id: str,
    event_type: str,
    payload: dict,
    idempotency_key: str,
    db: Prisma,
) -> str | None:
    """
    Finds the active worker, creates an Execution record (status: queued),
    and enqueues run_orchestrator_job.

    Returns the execution_id.
    Returns None if no active worker is deployed for this event type.
    Idempotent: if a non-failed execution with this key already exists, returns its id.
    """
    worker_type = EVENT_TO_WORKER.get(event_type)
    if worker_type is None:
        logger.error("unknown_event_type", extra={"event_type": event_type})
        return None

    worker = await db.worker.find_first(
        where={"tenant_id": tenant_id, "type": worker_type.value, "status": "active"}
    )
    if not worker:
        logger.warning(
            "no_active_worker_for_event",
            extra={"tenant_id": tenant_id, "event_type": event_type, "worker_type": worker_type.value},
        )
        return None

    existing = await db.execution.find_first(
        where={"tenant_id": tenant_id, "input_ref": idempotency_key}
    )
    if existing and existing.status != "failed":
        return existing.id

    execution = await db.execution.create(data={
        "tenant_id": tenant_id,
        "worker_id": worker.id,
        "input_ref": idempotency_key,
        "decision": "pending",
        "confidence": 0.0,
        "status": "queued",
    })

    pool = await get_queue_pool()
    await pool.enqueue_job(
        "run_orchestrator_job",
        execution_id=execution.id,
        tenant_id=tenant_id,
        worker_id=worker.id,
        event_type=event_type,
        payload=payload,
    )

    logger.info(
        "orchestrator_event_enqueued",
        extra={"execution_id": execution.id, "event_type": event_type, "tenant_id": tenant_id},
    )

    return execution.id
