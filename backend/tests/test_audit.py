import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_db(record_id: str = "audit-123", fail: bool = False):
    db = MagicMock()
    db.auditlog = MagicMock()
    if fail:
        db.auditlog.create = AsyncMock(side_effect=Exception("DB connection lost"))
    else:
        mock_record = MagicMock()
        mock_record.id = record_id
        db.auditlog.create = AsyncMock(return_value=mock_record)
    return db


@pytest.mark.asyncio
async def test_write_audit_log_returns_id():
    db = _make_db()
    with patch("app.audit.logger.get_db", return_value=db):
        from app.audit.logger import write_audit_log
        result = await write_audit_log(
            tenant_id="tenant-1",
            actor="tool:invoice_processing:v1",
            action="invoice_processed",
            reasoning_trace={"decision": "auto_approved"},
            model_version="invoice_processing-v1",
            execution_id="exec-1",
        )
    assert result == "audit-123"


@pytest.mark.asyncio
async def test_write_audit_log_appends_only():
    """Verify create is called (not update or upsert) — enforces append-only."""
    db = _make_db()
    with patch("app.audit.logger.get_db", return_value=db):
        from app.audit.logger import write_audit_log
        await write_audit_log(
            tenant_id="tenant-1",
            actor="user:u1",
            action="approval_approved",
            reasoning_trace={},
            model_version="human",
        )
    db.auditlog.create.assert_called_once()
    # update must never be called — audit logs are append-only
    db.auditlog.update = MagicMock()
    db.auditlog.update.assert_not_called()


@pytest.mark.asyncio
async def test_write_audit_log_passes_correct_fields():
    db = _make_db()
    with patch("app.audit.logger.get_db", return_value=db):
        from app.audit.logger import write_audit_log
        await write_audit_log(
            tenant_id="t1",
            actor="tool:x",
            action="test_action",
            reasoning_trace={"key": "value"},
            model_version="v1",
            execution_id="exec-abc",
        )
    data = db.auditlog.create.call_args.kwargs["data"]
    assert data["tenant_id"] == "t1"
    assert data["actor"] == "tool:x"
    assert data["action"] == "test_action"
    assert data["reasoning_trace_json"] == {"key": "value"}
    assert data["model_version"] == "v1"
    assert data["execution_id"] == "exec-abc"


@pytest.mark.asyncio
async def test_write_audit_log_raises_on_db_failure():
    """If DB write fails, the caller's operation must also fail — no silent success."""
    db = _make_db(fail=True)
    with patch("app.audit.logger.get_db", return_value=db):
        from app.audit.logger import write_audit_log
        with pytest.raises(RuntimeError, match="Audit log write failed"):
            await write_audit_log(
                tenant_id="t1",
                actor="tool:x",
                action="action",
                reasoning_trace={},
                model_version="v1",
            )


@pytest.mark.asyncio
async def test_write_audit_log_without_execution_id():
    db = _make_db()
    with patch("app.audit.logger.get_db", return_value=db):
        from app.audit.logger import write_audit_log
        await write_audit_log(
            tenant_id="t1",
            actor="system",
            action="startup",
            reasoning_trace={},
            model_version="system",
        )
    data = db.auditlog.create.call_args.kwargs["data"]
    assert data["execution_id"] is None
