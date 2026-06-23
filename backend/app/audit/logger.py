import json
from typing import Any, Optional

from app.core.db import get_db
from app.core.logging import get_logger

_logger = get_logger(__name__)


async def write_audit_log(
    *,
    tenant_id: str,
    actor: str,
    action: str,
    reasoning_trace: dict[str, Any],
    model_version: str,
    execution_id: Optional[str] = None,
) -> str:
    """
    Append-only audit log write.
    Raises RuntimeError on any failure — the caller's operation must fail
    if the audit cannot be recorded. Never silently succeeds.
    """
    db = get_db()
    try:
        # Round-trip through json to sanitize any non-serializable Python types
        safe_trace = json.loads(json.dumps(reasoning_trace, default=str))
        record = await db.auditlog.create(
            data={
                "tenant_id": tenant_id,
                "execution_id": execution_id,
                "actor": actor,
                "action": action,
                "reasoning_trace_json": safe_trace,
                "model_version": model_version,
            }
        )
        return record.id
    except Exception as exc:
        _logger.error("audit_write_failed", extra={"error": str(exc), "tenant_id": tenant_id})
        raise RuntimeError(f"Audit log write failed — operation cannot complete: {exc}") from exc
