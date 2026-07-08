"""
Shared execution completion - called by every tool job runner.
Writes the Execution and creates an Approval when the decision requires one.

Each tool's decision is final: it comes straight from that tool's policy thresholds
(spend limits, confidence minimums, VAT rules, etc.). There is no tool-wide autonomy
override - thresholds are the single source of truth for auto-approve vs. approval vs.
block.
"""
from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


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
    Write the Execution as completed and create an Approval if the decision requires one.
    Returns the final decision (the tool's own policy decision, unchanged).
    Every tool job runner calls this instead of writing Execution directly.
    """
    final = decision

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

    # Auto-advance to the next tool in the workflow if the connection is enabled.
    # Event-based (never a direct tool call) and never raises - see core/workflow.py.
    from app.core.workflow import advance_workflow
    await advance_workflow(
        db=db,
        tenant_id=tenant_id,
        tool_id=tool_id,
        from_execution_id=execution_id,
        final_decision=final,
    )

    return final
