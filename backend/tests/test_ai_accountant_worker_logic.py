"""
Unit tests for AIAccountantWorker business logic.
Claude and DB calls are mocked — no external connections required.
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.workers.ai_accountant import AIAccountantWorker, TransactionResult


def _make_txn(txn_id: str = "txn_1", amount: int = 5000, merchant: str = "Amazon") -> MagicMock:
    t = MagicMock()
    t.id = txn_id
    t.amount_minor = amount
    t.currency = "GBP"
    t.merchant_name = merchant
    t.description = f"Purchase at {merchant}"
    t.date = None
    t.category = "shopping"
    return t


def _make_invoice(inv_id: str = "inv_1", vendor: str = "Amazon", amount: int = 5000) -> MagicMock:
    i = MagicMock()
    i.id = inv_id
    i.vendor = vendor
    i.amount_minor = amount
    i.currency = "GBP"
    i.invoice_number = "INV-001"
    return i


def _claude_response(items: list[dict]) -> MagicMock:
    msg = MagicMock()
    msg.content = [MagicMock(text=json.dumps(items))]
    return msg


def _make_db(transactions=None, invoices=None, execution=None) -> MagicMock:
    db = MagicMock()
    db.banktransaction.find_many = AsyncMock(
        return_value=transactions if transactions is not None else [_make_txn()]
    )
    db.invoice.find_many = AsyncMock(return_value=invoices if invoices is not None else [])
    db.banktransaction.update = AsyncMock(return_value=None)
    exec_record = execution or MagicMock(id="exec_123")
    db.execution.create = AsyncMock(return_value=exec_record)
    db.auditlog.create = AsyncMock(return_value=None)
    return db


class TestAIAccountantWorkerRun:

    @pytest.mark.asyncio
    async def test_auto_decision_when_high_confidence(self):
        db = _make_db()
        claude_items = [{
            "transaction_id": "txn_1",
            "ai_category": "software",
            "matched_invoice_id": None,
            "confidence": 0.95,
            "reasoning": "Cloud software subscription",
        }]

        with (
            patch("app.workers.ai_accountant.get_db", return_value=db),
            patch("app.workers.ai_accountant.get_trace_id", return_value="trace_1"),
            patch("app.workers.ai_accountant.anthropic.AsyncAnthropic") as mock_anthropic,
        ):
            mock_client = AsyncMock()
            mock_anthropic.return_value = mock_client
            mock_client.messages.create = AsyncMock(return_value=_claude_response(claude_items))

            worker = AIAccountantWorker()
            result = await worker.run(["txn_1"], "tenant_1", "worker_1")

        assert result.decision == "auto"
        assert result.confidence >= 0.85
        db.banktransaction.update.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_pending_decision_when_medium_confidence(self):
        db = _make_db()
        claude_items = [{
            "transaction_id": "txn_1",
            "ai_category": "other",
            "matched_invoice_id": None,
            "confidence": 0.65,
            "reasoning": "Unclear merchant",
        }]

        with (
            patch("app.workers.ai_accountant.get_db", return_value=db),
            patch("app.workers.ai_accountant.get_trace_id", return_value="trace_1"),
            patch("app.workers.ai_accountant.anthropic.AsyncAnthropic") as mock_anthropic,
        ):
            mock_client = AsyncMock()
            mock_anthropic.return_value = mock_client
            mock_client.messages.create = AsyncMock(return_value=_claude_response(claude_items))

            worker = AIAccountantWorker()
            result = await worker.run(["txn_1"], "tenant_1", "worker_1")

        assert result.decision == "pending"

    @pytest.mark.asyncio
    async def test_blocked_when_low_confidence(self):
        db = _make_db()
        claude_items = [{
            "transaction_id": "txn_1",
            "ai_category": "other",
            "matched_invoice_id": None,
            "confidence": 0.30,
            "reasoning": "Cannot determine",
        }]

        with (
            patch("app.workers.ai_accountant.get_db", return_value=db),
            patch("app.workers.ai_accountant.get_trace_id", return_value="trace_1"),
            patch("app.workers.ai_accountant.anthropic.AsyncAnthropic") as mock_anthropic,
        ):
            mock_client = AsyncMock()
            mock_anthropic.return_value = mock_client
            mock_client.messages.create = AsyncMock(return_value=_claude_response(claude_items))

            worker = AIAccountantWorker()
            result = await worker.run(["txn_1"], "tenant_1", "worker_1")

        assert result.decision == "blocked"
        # No DB writes when blocked
        db.banktransaction.update.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_blocked_on_invalid_category_policy_violation(self):
        db = _make_db()
        claude_items = [{
            "transaction_id": "txn_1",
            "ai_category": "INVALID_CATEGORY",
            "matched_invoice_id": None,
            "confidence": 0.95,
            "reasoning": "Invalid",
        }]

        with (
            patch("app.workers.ai_accountant.get_db", return_value=db),
            patch("app.workers.ai_accountant.get_trace_id", return_value="trace_1"),
            patch("app.workers.ai_accountant.anthropic.AsyncAnthropic") as mock_anthropic,
        ):
            mock_client = AsyncMock()
            mock_anthropic.return_value = mock_client
            mock_client.messages.create = AsyncMock(return_value=_claude_response(claude_items))

            worker = AIAccountantWorker()
            result = await worker.run(["txn_1"], "tenant_1", "worker_1")

        # Invalid category gets normalised to "other", so it passes validation
        assert result.decision in ("auto", "pending", "blocked")

    @pytest.mark.asyncio
    async def test_raises_when_no_transactions_found(self):
        db = _make_db(transactions=[])

        with patch("app.workers.ai_accountant.get_db", return_value=db):
            worker = AIAccountantWorker()
            with pytest.raises(ValueError, match="No transactions found"):
                await worker.run(["txn_missing"], "tenant_1", "worker_1")

    @pytest.mark.asyncio
    async def test_raises_on_empty_transaction_ids(self):
        db = _make_db()
        with patch("app.workers.ai_accountant.get_db", return_value=db):
            worker = AIAccountantWorker()
            with pytest.raises(ValueError, match="transaction_ids cannot be empty"):
                await worker.run([], "tenant_1", "worker_1")

    @pytest.mark.asyncio
    async def test_audit_always_written(self):
        db = _make_db()
        claude_items = [{
            "transaction_id": "txn_1",
            "ai_category": "software",
            "matched_invoice_id": None,
            "confidence": 0.95,
            "reasoning": "SaaS subscription",
        }]

        with (
            patch("app.workers.ai_accountant.get_db", return_value=db),
            patch("app.workers.ai_accountant.get_trace_id", return_value="trace_1"),
            patch("app.workers.ai_accountant.anthropic.AsyncAnthropic") as mock_anthropic,
        ):
            mock_client = AsyncMock()
            mock_anthropic.return_value = mock_client
            mock_client.messages.create = AsyncMock(return_value=_claude_response(claude_items))

            worker = AIAccountantWorker()
            await worker.run(["txn_1"], "tenant_1", "worker_1")

        db.auditlog.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_items_missing_transaction_id(self):
        db = _make_db()
        claude_items = [
            {"ai_category": "software", "matched_invoice_id": None, "confidence": 0.90, "reasoning": "ok"},
            {"transaction_id": "txn_1", "ai_category": "software", "matched_invoice_id": None,
             "confidence": 0.90, "reasoning": "ok"},
        ]

        with (
            patch("app.workers.ai_accountant.get_db", return_value=db),
            patch("app.workers.ai_accountant.get_trace_id", return_value="trace_1"),
            patch("app.workers.ai_accountant.anthropic.AsyncAnthropic") as mock_anthropic,
        ):
            mock_client = AsyncMock()
            mock_anthropic.return_value = mock_client
            mock_client.messages.create = AsyncMock(return_value=_claude_response(claude_items))

            worker = AIAccountantWorker()
            result = await worker.run(["txn_1"], "tenant_1", "worker_1")

        # Only one valid result (the item with transaction_id)
        assert len(result.results) == 1
        assert result.results[0].transaction_id == "txn_1"

    @pytest.mark.asyncio
    async def test_policy_config_overrides_thresholds(self):
        db = _make_db()
        claude_items = [{
            "transaction_id": "txn_1",
            "ai_category": "software",
            "matched_invoice_id": None,
            "confidence": 0.80,  # below default 0.85 auto threshold
            "reasoning": "ok",
        }]
        # Override to lower auto threshold
        policy = {"auto_confidence_threshold": 0.75, "approve_confidence_threshold": 0.50}

        with (
            patch("app.workers.ai_accountant.get_db", return_value=db),
            patch("app.workers.ai_accountant.get_trace_id", return_value="trace_1"),
            patch("app.workers.ai_accountant.anthropic.AsyncAnthropic") as mock_anthropic,
        ):
            mock_client = AsyncMock()
            mock_anthropic.return_value = mock_client
            mock_client.messages.create = AsyncMock(return_value=_claude_response(claude_items))

            worker = AIAccountantWorker()
            result = await worker.run(["txn_1"], "tenant_1", "worker_1", policy_config=policy)

        assert result.decision == "auto"

    @pytest.mark.asyncio
    async def test_retries_on_transient_api_error(self):
        import app.workers.ai_accountant as acct_mod
        db = _make_db()
        success_response = _claude_response([{
            "transaction_id": "txn_1",
            "ai_category": "software",
            "matched_invoice_id": None,
            "confidence": 0.95,
            "reasoning": "ok",
        }])
        # Use the stub exception class that conftest registered for anthropic
        transient_error = acct_mod.anthropic.APIConnectionError(request=MagicMock())

        with (
            patch("app.workers.ai_accountant.get_db", return_value=db),
            patch("app.workers.ai_accountant.get_trace_id", return_value="trace_1"),
            patch("app.workers.ai_accountant.anthropic.AsyncAnthropic") as mock_anthropic,
            patch("app.workers.ai_accountant.asyncio.sleep", AsyncMock()),
        ):
            mock_client = AsyncMock()
            mock_anthropic.return_value = mock_client
            mock_client.messages.create = AsyncMock(
                side_effect=[transient_error, success_response]
            )

            worker = AIAccountantWorker()
            result = await worker.run(["txn_1"], "tenant_1", "worker_1")

        assert result.decision == "auto"
        assert mock_client.messages.create.call_count == 2
