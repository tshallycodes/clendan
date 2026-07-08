"""
Tests for shared approval resolution (app/core/approvals.resolve_approval) and the
expiry cron (app/tool.expire_stale_approvals). No DB - the Prisma client is mocked.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _mock_db(execution=None):
    db = MagicMock()
    db.approval.update = AsyncMock()
    db.execution.find_unique = AsyncMock(return_value=execution)
    db.execution.update = AsyncMock()
    db.document.update_many = AsyncMock()
    db.journalentry.update_many = AsyncMock()
    return db


class TestResolveApproval:
    @pytest.mark.asyncio
    async def test_reject_cascades_and_audits(self):
        approval = MagicMock(id="a1", execution_id="e1", tenant_id="t1")
        db = _mock_db(execution=MagicMock(input_ref=None))

        with patch("app.core.approvals.write_audit_log", AsyncMock()) as audit:
            from app.core.approvals import resolve_approval
            await resolve_approval(
                db=db, approval=approval, action="reject", actor="system:approval_expiry",
            )

        assert db.approval.update.await_args.kwargs["data"]["status"] == "rejected"
        assert db.execution.update.await_args.kwargs["data"]["decision"] == "rejected"
        assert db.document.update_many.await_args.kwargs["data"]["decision"] == "blocked"
        audit.assert_awaited_once()
        # system actor -> non-human model_version in the audit trail
        assert audit.await_args.kwargs["model_version"] == "system"

    @pytest.mark.asyncio
    async def test_approve_sets_auto_approved(self):
        approval = MagicMock(id="a1", execution_id="e1", tenant_id="t1")
        db = _mock_db(execution=MagicMock(input_ref=None))

        with patch("app.core.approvals.write_audit_log", AsyncMock()):
            from app.core.approvals import resolve_approval
            await resolve_approval(
                db=db, approval=approval, action="approve", actor="user:clerk_123",
            )

        assert db.approval.update.await_args.kwargs["data"]["status"] == "approved"
        assert db.execution.update.await_args.kwargs["data"]["decision"] == "approved"
        assert db.document.update_many.await_args.kwargs["data"]["decision"] == "auto_approved"

    @pytest.mark.asyncio
    async def test_cascades_to_linked_journal_entry(self):
        approval = MagicMock(id="a1", execution_id="e1", tenant_id="t1")
        db = _mock_db(execution=MagicMock(input_ref="journal_entry:je_42:extra"))

        with patch("app.core.approvals.write_audit_log", AsyncMock()):
            from app.core.approvals import resolve_approval
            await resolve_approval(
                db=db, approval=approval, action="reject", actor="user:clerk_123",
            )

        db.journalentry.update_many.assert_awaited_once()
        je_call = db.journalentry.update_many.await_args.kwargs
        assert je_call["where"]["id"] == "je_42"
        assert je_call["data"]["status"] == "rejected"


class TestExpireStaleApprovals:
    @pytest.mark.asyncio
    async def test_auto_rejects_each_stale_approval(self):
        stale = [
            MagicMock(id="a1", tenant_id="t1", execution_id="e1"),
            MagicMock(id="a2", tenant_id="t1", execution_id="e2"),
        ]
        db = MagicMock()
        db.approval.find_many = AsyncMock(return_value=stale)
        resolve = AsyncMock()

        with (
            patch("app.tool.get_db", return_value=db),
            patch("app.core.approvals.resolve_approval", resolve),
        ):
            from app.tool import expire_stale_approvals
            await expire_stale_approvals({})

        # only pending + already-expired rows are selected
        where = db.approval.find_many.await_args.kwargs["where"]
        assert where["status"] == "pending"
        assert "lt" in where["expires_at"]

        assert resolve.await_count == 2
        assert all(c.kwargs["action"] == "reject" for c in resolve.await_args_list)
        assert all(c.kwargs["actor"] == "system:approval_expiry" for c in resolve.await_args_list)

    @pytest.mark.asyncio
    async def test_one_failure_does_not_stop_the_rest(self):
        stale = [MagicMock(id="a1", tenant_id="t1", execution_id="e1"),
                 MagicMock(id="a2", tenant_id="t1", execution_id="e2")]
        db = MagicMock()
        db.approval.find_many = AsyncMock(return_value=stale)
        resolve = AsyncMock(side_effect=[RuntimeError("boom"), None])

        with (
            patch("app.tool.get_db", return_value=db),
            patch("app.core.approvals.resolve_approval", resolve),
        ):
            from app.tool import expire_stale_approvals
            await expire_stale_approvals({})  # must not raise

        assert resolve.await_count == 2
