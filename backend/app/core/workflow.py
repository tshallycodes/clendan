"""Workflow auto-advance — the toggleable connections between tools in a workflow.

When an upstream tool completes a fully-automatic (``auto_approved``) run and the
connection to the next tool is enabled and that tool is active, the downstream tool
is triggered. Crucially this goes through the event bus (``enqueue_event``) — a tool
never calls another tool directly (a hard anti-pattern). The event/dispatch layer
finds the downstream tool, creates its own Execution, policy-checks, and audits it
exactly as any other trigger would.

Edges are a DAG (AP: doc-intel → spend → payment; Close: recon → tax → reporting),
so a single upstream run can cascade at most one hop per tool with no cycles.
"""
from app.core.logging import get_logger

logger = get_logger(__name__)

# from_tool_type -> (to_tool_type, downstream event_type used to trigger it)
WORKFLOW_EDGES: dict[str, tuple[str, str]] = {
    "document_intelligence": ("spend_control", "spend_control_run"),
    "spend_control":         ("payment_run", "payment_run_requested"),
    "reconciliation":        ("tax_compliance", "tax_compliance_run"),
    "tax_compliance":        ("financial_reporting", "financial_report_run"),
}

# Only advance on a fully-automatic success — never off an approval-gated or blocked run.
_ADVANCE_ON_DECISION = "auto_approved"


async def advance_workflow(
    *,
    db,
    tenant_id: str,
    tool_id: str,
    from_execution_id: str,
    final_decision: str,
) -> str | None:
    """Trigger the downstream tool if this tool's connection is enabled and active.

    Returns the downstream execution_id if one was enqueued, else None. Never raises —
    a chaining failure must not fail the upstream tool's own completion.
    """
    try:
        if final_decision != _ADVANCE_ON_DECISION:
            return None

        tool = await db.tool.find_first(where={"id": tool_id, "tenant_id": tenant_id})
        if not tool:
            return None

        edge = WORKFLOW_EDGES.get(tool.type)
        if not edge:
            return None
        to_type, event_type = edge

        # Connection state: a missing row means enabled (default on).
        conn = await db.workflowconnection.find_first(
            where={"tenant_id": tenant_id, "from_type": tool.type, "to_type": to_type}
        )
        if conn and not conn.enabled:
            logger.info(
                "workflow_advance_disabled",
                extra={"tenant_id": tenant_id, "from_type": tool.type, "to_type": to_type},
            )
            return None

        # Downstream must be deployed and active, or there is nothing to advance to.
        downstream = await db.tool.find_first(
            where={"tenant_id": tenant_id, "type": to_type, "status": "active"}
        )
        if not downstream:
            logger.info(
                "workflow_advance_skipped_downstream_inactive",
                extra={"tenant_id": tenant_id, "from_type": tool.type, "to_type": to_type},
            )
            return None

        # Lazy import avoids an import cycle (events → dispatch → queue) at module load.
        from app.events.enqueue import enqueue_event

        idempotency_key = f"chain:{tool.type}->{to_type}:{from_execution_id}"
        downstream_execution_id = await enqueue_event(
            tenant_id=tenant_id,
            event_type=event_type,
            payload={"source": "workflow_chain", "from_execution_id": from_execution_id},
            idempotency_key=idempotency_key,
            db=db,
        )

        logger.info(
            "workflow_advanced",
            extra={
                "tenant_id": tenant_id,
                "from_type": tool.type,
                "to_type": to_type,
                "from_execution_id": from_execution_id,
                "downstream_execution_id": downstream_execution_id,
            },
        )
        return downstream_execution_id

    except Exception as exc:  # noqa: BLE001 — chaining must never break completion
        logger.error(
            "workflow_advance_failed",
            extra={"tenant_id": tenant_id, "tool_id": tool_id, "error": type(exc).__name__},
        )
        return None
