"""
Worker stub smoke tests — Phase 1.
Verifies that all four new workers instantiate, accept minimal valid input,
and return a correctly shaped WorkerOutput without touching any external API.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.workers.base import WorkerOutput


# ---------------------------------------------------------------------------
# ReconciliationWorker
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reconciliation_worker_returns_worker_output():
    from app.workers.reconciliation import ReconciliationWorker

    worker = ReconciliationWorker()
    result = await worker.execute(
        input_data={
            "source_dataset": [],
            "target_dataset": [],
            "period_start": date(2025, 1, 1),
            "period_end": date(2025, 1, 31),
        },
        tenant_id="tenant_001",
    )

    assert isinstance(result, WorkerOutput)
    assert isinstance(result.confidence, float)
    assert 0.0 <= result.confidence <= 1.0
    assert isinstance(result.reasoning, str) and result.reasoning
    assert isinstance(result.actions_taken, list)


# ---------------------------------------------------------------------------
# ExpenseControlWorker
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_expense_control_worker_returns_worker_output():
    from app.workers.expense_control import ExpenseControlWorker

    worker = ExpenseControlWorker()
    result = await worker.execute(
        input_data={
            "expense_claim_id": "claim_001",
            "amount_minor": 5000,
            "currency": "GBP",
            "category": "travel",
            "receipt_document_ref": "ref_001",
            "submitted_by": "user_001",
            "policy_rules": {},
        },
        tenant_id="tenant_001",
    )

    assert isinstance(result, WorkerOutput)
    assert isinstance(result.confidence, float)
    assert 0.0 <= result.confidence <= 1.0
    assert isinstance(result.reasoning, str) and result.reasoning
    assert isinstance(result.actions_taken, list)


# ---------------------------------------------------------------------------
# CollectionsWorker
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_collections_worker_returns_worker_output():
    from app.workers.collections import CollectionsWorker

    worker = CollectionsWorker()
    result = await worker.execute(
        input_data={
            "invoice_id": "inv_001",
            "vendor": "Acme Corp",
            "amount_minor": 100000,
            "currency": "GBP",
            "due_date": date(2025, 1, 1),
            "days_overdue": 14,
            "previous_reminders_sent": 1,
            "customer_payment_history": {},
        },
        tenant_id="tenant_001",
    )

    assert isinstance(result, WorkerOutput)
    assert isinstance(result.confidence, float)
    assert 0.0 <= result.confidence <= 1.0
    assert isinstance(result.reasoning, str) and result.reasoning
    assert isinstance(result.actions_taken, list)


# ---------------------------------------------------------------------------
# FraudDetectionWorker
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fraud_detection_worker_returns_worker_output():
    from app.workers.fraud_detection import FraudDetectionWorker

    worker = FraudDetectionWorker()
    result = await worker.execute(
        input_data={
            "transaction_id": "txn_001",
            "amount_minor": 25000,
            "currency": "GBP",
            "counterparty": "Trusted Vendor",
            "transaction_type": "payment",
            "timestamp": datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            "metadata": {},
        },
        tenant_id="tenant_001",
    )

    assert isinstance(result, WorkerOutput)
    assert isinstance(result.confidence, float)
    assert 0.0 <= result.confidence <= 1.0
    assert isinstance(result.reasoning, str) and result.reasoning
    assert isinstance(result.actions_taken, list)
