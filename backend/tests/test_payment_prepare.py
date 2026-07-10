"""
Tests for the money-PREPARATION rail in app/core/agent_actions.py.

prepare_payment PROPOSES with an account-changed flag and EXECUTES prepare-only: it records
payment intent (a SCHEDULED PaymentRun) and remembers the confirmed destination account
(VendorBankDetail). It must NEVER disburse - there is deliberately no disbursement path, so the
execute test asserts no payout/approve path is hit and no run is transitioned to paid. The Prisma
client, audit, and payouts are mocked; nothing touches a DB or moves money.
"""
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _prepare_action(params, status="proposed", expires_in=900):
    m = MagicMock()
    m.id = "act1"
    m.tenant_id = "t1"
    m.kind = "prepare_payment"
    m.capability = "money"
    m.params = params
    m.status = status
    m.execution_id = None
    m.expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
    return m


def _vendor_detail(account="sortcode:1111"):
    m = MagicMock()
    m.account_identifier = account
    m.currency = "GBP"
    return m


# ---- propose: account-change detection -------------------------------------

@pytest.mark.asyncio
async def test_propose_flags_new_account_when_none_on_file():
    db = MagicMock()
    db.vendorbankdetail.find_first = AsyncMock(return_value=None)  # first payment to this supplier
    db.agentaction.create = AsyncMock(return_value=_prepare_action({}))
    from app.core.agent_actions import propose_action
    res = await propose_action(db, "t1", kind="prepare_payment",
                               params={"vendor": "Acme Ltd", "amount_minor": 20000, "currency": "GBP",
                                       "account_identifier": "sortcode:2222"}, proposed_by="u1")
    assert res["capability"] == "money"
    d = res["details"]
    assert d["account_changed"] is True
    assert d["payee"] == "Acme Ltd" and d["amount_minor"] == 20000
    assert d["account_identifier"] == "sortcode:2222"
    # the persisted params carry the flag so the confirm sheet is durable
    data = db.agentaction.create.await_args.kwargs["data"]
    assert data["capability"] == "money" and data["params"]["account_changed"] is True


@pytest.mark.asyncio
async def test_propose_same_account_not_flagged():
    db = MagicMock()
    db.vendorbankdetail.find_first = AsyncMock(return_value=_vendor_detail("sortcode:2222"))
    db.agentaction.create = AsyncMock(return_value=_prepare_action({}))
    from app.core.agent_actions import propose_action
    res = await propose_action(db, "t1", kind="prepare_payment",
                               params={"vendor": "Acme Ltd", "amount_minor": 20000, "currency": "GBP",
                                       "account_identifier": "sortcode:2222"}, proposed_by="u1")
    assert res["details"]["account_changed"] is False


@pytest.mark.asyncio
async def test_propose_changed_account_flagged_and_in_preview():
    db = MagicMock()
    db.vendorbankdetail.find_first = AsyncMock(return_value=_vendor_detail("sortcode:1111"))
    db.agentaction.create = AsyncMock(return_value=_prepare_action({}))
    from app.core.agent_actions import propose_action
    res = await propose_action(db, "t1", kind="prepare_payment",
                               params={"vendor": "Acme Ltd", "amount_minor": 20000, "currency": "GBP",
                                       "account_identifier": "sortcode:9999"}, proposed_by="u1")
    assert res["details"]["account_changed"] is True
    assert "changed" in res["preview"]


@pytest.mark.asyncio
async def test_propose_from_bill_resolves_payee_amount_and_vendor_ref():
    bill = MagicMock(contact_name="Beta Supplies", contact_id="c-9",
                     outstanding_cents=7500, total_cents=7500, currency="GBP")
    db = MagicMock()
    db.accountingbill.find_first = AsyncMock(return_value=bill)
    db.vendorbankdetail.find_first = AsyncMock(return_value=None)
    db.agentaction.create = AsyncMock(return_value=_prepare_action({}))
    from app.core.agent_actions import propose_action
    res = await propose_action(db, "t1", kind="prepare_payment",
                               params={"bill_id": "bill1", "account_identifier": "iban:GB123"},
                               proposed_by="u1")
    assert res["details"]["payee"] == "Beta Supplies" and res["details"]["amount_minor"] == 7500
    # the ERP contact id is used as the vendor key for change-detection
    where = db.vendorbankdetail.find_first.await_args.kwargs["where"]
    assert where["vendor_ref"] == "c-9" and where["tenant_id"] == "t1"


@pytest.mark.asyncio
async def test_propose_requires_account_when_none_available():
    db = MagicMock()
    db.vendorbankdetail.find_first = AsyncMock(return_value=None)
    from app.core.agent_actions import propose_action, AgentActionError
    with pytest.raises(AgentActionError, match="account"):
        await propose_action(db, "t1", kind="prepare_payment",
                             params={"vendor": "Acme", "amount_minor": 100, "currency": "GBP"},
                             proposed_by="u1")


@pytest.mark.asyncio
async def test_propose_missing_bill_raises():
    db = MagicMock()
    db.accountingbill.find_first = AsyncMock(return_value=None)
    from app.core.agent_actions import propose_action, AgentActionError
    with pytest.raises(AgentActionError, match="Bill not found"):
        await propose_action(db, "t1", kind="prepare_payment",
                             params={"bill_id": "missing", "account_identifier": "iban:GB1"},
                             proposed_by="u1")


# ---- execute: PREPARE ONLY, never disburse ---------------------------------

@pytest.mark.asyncio
async def test_execute_prepares_only_and_never_disburses():
    params = {"bill_id": "bill1", "vendor_ref": "c-9", "payee": "Beta Supplies",
              "amount_minor": 7500, "currency": "GBP",
              "account_identifier": "iban:GB123", "account_changed": True}
    action = _prepare_action(params)
    db = MagicMock()
    db.agentaction.find_first = AsyncMock(return_value=action)
    db.agentaction.update = AsyncMock()
    db.vendorbankdetail.upsert = AsyncMock()
    db.paymentrun.create = AsyncMock(return_value=MagicMock(id="run1"))
    db.paymentrun.update = AsyncMock()
    db.accountingbill.update = AsyncMock()
    db.accountingbill.update_many = AsyncMock()
    with (
        patch("app.core.agent_actions.write_audit_log", AsyncMock()) as audit,
        patch("app.core.payouts._execute_payout", AsyncMock()) as disburse,
        patch("app.core.payouts.approve_payment_run", AsyncMock()) as approve,
    ):
        from app.core.agent_actions import execute_action
        res = await execute_action(db, "t1", "act1", confirmed_by="u1")
    assert res["executed"] is True

    # PREPARE: a scheduled run recorded (intent), and the confirmed account remembered
    db.paymentrun.create.assert_awaited_once()
    run = db.paymentrun.create.await_args.kwargs["data"]
    assert run["status"] == "scheduled" and run["total_amount_cents"] == 7500
    assert run["bill_ids"] == ["bill1"]
    db.vendorbankdetail.upsert.assert_awaited_once()
    up = db.vendorbankdetail.upsert.await_args.kwargs
    assert up["data"]["create"]["account_identifier"] == "iban:GB123"
    assert up["data"]["update"]["account_identifier"] == "iban:GB123"

    # PREPARE-ONLY: no disbursement path exists, no run marked paid, no bills marked paid
    disburse.assert_not_awaited()
    approve.assert_not_awaited()
    db.paymentrun.update.assert_not_awaited()
    db.accountingbill.update_many.assert_not_awaited()

    # audit-first (prepare_payment audit) plus the generic execute audit
    assert audit.await_count >= 2


@pytest.mark.asyncio
async def test_execute_prepare_without_bill_records_intent_with_no_bill_ids():
    params = {"bill_id": None, "vendor_ref": "acme ltd", "payee": "Acme Ltd",
              "amount_minor": 5000, "currency": "GBP",
              "account_identifier": "sortcode:2222", "account_changed": True}
    action = _prepare_action(params)
    db = MagicMock()
    db.agentaction.find_first = AsyncMock(return_value=action)
    db.agentaction.update = AsyncMock()
    db.vendorbankdetail.upsert = AsyncMock()
    db.paymentrun.create = AsyncMock(return_value=MagicMock(id="run1"))
    with (
        patch("app.core.agent_actions.write_audit_log", AsyncMock()),
        patch("app.core.payouts._execute_payout", AsyncMock()) as disburse,
    ):
        from app.core.agent_actions import execute_action
        await execute_action(db, "t1", "act1", confirmed_by="u1")
    run = db.paymentrun.create.await_args.kwargs["data"]
    assert run["bill_ids"] == [] and run["bill_count"] == 0
    disburse.assert_not_awaited()


# ---- clen tool wrapper -----------------------------------------------------

@pytest.mark.asyncio
async def test_clen_prepare_payment_returns_money_proposal():
    db = MagicMock()
    db.vendorbankdetail.find_first = AsyncMock(return_value=None)
    db.agentaction.create = AsyncMock(return_value=_prepare_action({}))
    from app.clen.tools import execute_tool
    res = await execute_tool("prepare_payment",
                             {"vendor": "Acme", "amount_minor": 5000, "currency": "GBP",
                              "account_identifier": "sortcode:5555"}, "t1", "u1", db)
    assert "proposed_action" in res
    assert res["proposed_action"]["capability"] == "money"
    assert res["proposed_action"]["details"]["account_changed"] is True
