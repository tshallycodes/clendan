"""
Thin wrapper kept for backward compatibility with integration syncs and webhooks.
All calls route directly to the correct arq job via core.dispatch — no orchestrator hop.
"""
from prisma import Prisma
from prisma.errors import UniqueViolationError

from app.core.dispatch import EVENT_TYPE_TO_TOOL_TYPE, enqueue_for_event
from app.core.logging import get_logger
from app.queue.pool import get_queue_pool

logger = get_logger(__name__)


async def enqueue_orchestrator_event(
    *,
    tenant_id: str,
    event_type: str,
    payload: dict,
    idempotency_key: str,
    db: Prisma,
    triggered_by_email: str | None = None,
) -> str | None:
    """
    Find the active tool for event_type, create Execution, enqueue job directly.
    Returns execution_id or None if no active tool is deployed.
    Idempotent via DB unique constraint on (tenant_id, input_ref).
    """
    tool_type = EVENT_TYPE_TO_TOOL_TYPE.get(event_type)
    if tool_type is None:
        logger.error("unknown_event_type", extra={"event_type": event_type})
        return None

    tool = await db.tool.find_first(
        where={"tenant_id": tenant_id, "type": tool_type, "status": "active"}
    )
    if not tool:
        logger.warning(
            "no_active_tool_for_event",
            extra={"tenant_id": tenant_id, "event_type": event_type, "tool_type": tool_type},
        )
        return None

    try:
        execution = await db.execution.create(data={
            "tenant_id": tenant_id,
            "tool_id": tool.id,
            "input_ref": idempotency_key,
            "decision": "pending",
            "confidence": 0.0,
            "status": "queued",
            **({"triggered_by_email": triggered_by_email} if triggered_by_email else {}),
        })
    except UniqueViolationError:
        existing = await db.execution.find_first(
            where={"tenant_id": tenant_id, "input_ref": idempotency_key}
        )
        logger.info(
            "execution_deduplicated",
            extra={"idempotency_key": idempotency_key, "event_type": event_type},
        )
        return existing.id if existing else None

    pool = await get_queue_pool()
    await enqueue_for_event(
        pool=pool,
        event_type=event_type,
        execution_id=execution.id,
        tenant_id=tenant_id,
        tool_id=tool.id,
        payload=payload,
    )

    logger.info(
        "event_enqueued",
        extra={"execution_id": execution.id, "event_type": event_type, "tenant_id": tenant_id},
    )
    return execution.id
