"""
Shared approval resolution.

Applies an approve/reject decision to a pending approval and cascades it consistently:
the linked execution decision, any linked journal entry, and the source document are all
updated together, then the action is written to the immutable audit log.

Used by both the human respond endpoint (app/api/v1/approvals/respond.py) and the expiry
cron (expire_stale_approvals in app/tool.py) so the two can never drift apart.
"""
from datetime import UTC, datetime

from app.audit.logger import write_audit_log
from app.core.logging import get_logger

logger = get_logger(__name__)


async def resolve_approval(
    *,
    db,
    approval,
    action: str,
    actor: str,
    responder_id: str | None = None,
) -> None:
    """Resolve a pending approval and cascade the decision.

    Args:
        db: Prisma client.
        approval: the pending Approval record (caller has verified status == "pending").
        action: "approve" or "reject".
        actor: audit actor, e.g. "user:clerk_xxx" or "system:approval_expiry".
        responder_id: internal User id of a human responder, if any.

    Callers own their own guards (existence, ownership, expiry). This helper does not
    re-check them - it just applies the decision.
    """
    now = datetime.now(UTC)
    is_approve = action == "approve"
    new_status = "approved" if is_approve else "rejected"
    new_decision = "approved" if is_approve else "rejected"

    approval_update: dict = {"status": new_status, "responded_at": now}
    if responder_id:
        approval_update["responder_id"] = responder_id
    await db.approval.update(where={"id": approval.id}, data=approval_update)  # type: ignore[arg-type]

    execution = await db.execution.find_unique(where={"id": approval.execution_id})
    await db.execution.update(
        where={"id": approval.execution_id},
        data={"decision": new_decision},
    )

    # Cascade to a linked journal entry, if this approval gates one.
    if execution and execution.input_ref and execution.input_ref.startswith("journal_entry:"):
        parts = execution.input_ref.split(":")
        if len(parts) >= 2:
            je_id = parts[1]
            await db.journalentry.update_many(
                where={"id": je_id, "tenant_id": approval.tenant_id, "status": "pending_approval"},
                data={"status": "approved" if is_approve else "rejected"},
            )
            logger.info(
                "journal_entry_approval_cascaded",
                extra={
                    "journal_entry_id": je_id,
                    "new_status": new_status,
                    "approval_id": approval.id,
                    "tenant_id": approval.tenant_id,
                },
            )

    # Cascade to the source document so the Documents tab reflects the outcome.
    await db.document.update_many(
        where={"execution_id": approval.execution_id, "tenant_id": approval.tenant_id},
        data={"decision": "auto_approved" if is_approve else "blocked"},
    )

    # Audit last - must succeed for the operation to be considered complete.
    await write_audit_log(
        tenant_id=approval.tenant_id,
        actor=actor,
        action=f"approval_{new_status}",
        reasoning_trace={
            "approval_id": approval.id,
            "execution_id": approval.execution_id,
            "action": action,
        },
        model_version="human" if actor.startswith("user:") else "system",
        execution_id=approval.execution_id,
    )

    # Post the now-approved journal entry to the connected ERP (dry-run unless erp_write_live).
    # Best-effort: a posting failure must not undo the approval, which is already audited above.
    if is_approve and execution and execution.input_ref and execution.input_ref.startswith("journal_entry:"):
        parts = execution.input_ref.split(":")
        je_id = parts[1] if len(parts) >= 2 else ""
        if je_id:
            try:
                entry = await db.journalentry.find_first(
                    where={"id": je_id, "tenant_id": approval.tenant_id},
                )
                if entry and entry.status == "approved":
                    from app.core.erp_writer import post_journal_entry
                    await post_journal_entry(db, approval.tenant_id, entry)
            except Exception as exc:
                logger.error(
                    "journal_entry_erp_post_failed",
                    extra={"journal_entry_id": je_id, "error": type(exc).__name__},
                )
