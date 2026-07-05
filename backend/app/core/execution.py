"""
Shared execution completion — called by every tool job runner.
Applies autonomy override, writes Execution, creates Approval if needed.
"""
from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _apply_autonomy_override(decision: str, autonomy_level: str) -> str:
    """Override policy decision based on tool autonomy level. blocked is never changed."""
    if decision == "blocked":
        return decision
    if autonomy_level == "auto" and decision == "approval_required":
        return "auto_approved"
    if autonomy_level == "approve" and decision == "auto_approved":
        return "approval_required"
    return decision


async def complete_execution(
    *,
    db,
    execution_id: str,
    tool_id: str,
    tenant_id: str,
    decision: str,
    confidence: float,
    duration_ms: int,
) -> str:
    """
    Apply autonomy override, write Execution as completed, create Approval if needed.
    Returns the final (possibly overridden) decision.
    Every tool job runner calls this instead of writing Execution directly.
    """
    tool = await db.tool.find_first(where={"id": tool_id, "tenant_id": tenant_id})
    autonomy_level = tool.autonomy_level if tool else "approve"
    final = _apply_autonomy_override(decision, autonomy_level)

    if final != decision:
        logger.info(
            "autonomy_override_applied",
            extra={
                "execution_id": execution_id,
                "tool_id": tool_id,
                "original": decision,
                "overridden": final,
                "autonomy_level": autonomy_level,
            },
        )

    await db.execution.update(
        where={"id": execution_id},
        data={
            "status": "completed",
            "decision": final,
            "confidence": confidence,
            "duration_ms": duration_ms,
        },
    )

    if final == "approval_required":
        settings = get_settings()
        existing = await db.approval.find_first(where={"execution_id": execution_id})
        if not existing:
            await db.approval.create(data={
                "tenant_id": tenant_id,
                "execution_id": execution_id,
                "expires_at": datetime.now(UTC) + timedelta(seconds=settings.approval_ttl_seconds),
            })

    return final
