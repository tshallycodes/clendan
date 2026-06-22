"""Reconciliation Tool — matches BankTransaction against AccountingInvoice (AR) and AccountingBill (AP).
Unmatched items are reviewed by Claude. Policy flags runs where unmatched % exceeds threshold."""
from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime, timedelta
from typing import Literal

from anthropic import APIConnectionError, APIStatusError, AsyncAnthropic
from pydantic import BaseModel

from app.audit.logger import write_audit_log
from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.queue.pool import push_to_dlq
from app.tools.base import BaseTool, ToolOutput, ToolType

logger = get_logger(__name__)

_ACTOR = "tool:reconciliation:v1"
_MODEL_VERSION = "reconciliation-v1"



class _ToolPolicy(BaseModel):
    unmatched_pct_threshold: float = 0.20
    match_amount_tolerance_pct: float = 0.01
    match_date_window_days: int = 30
    # Retained for backward-compat with existing stored configs
    staleness_days: int = 30
    auto_match_confidence_min: float = 0.95
    partial_match_enabled: bool = True
    reconciliation_frequency: str = "daily"
    stale_open_item_days: int = 90
    period_lock_respect: bool = True
    segregation_of_duties_enforced: bool = True


class _TransactionRecord(BaseModel):
    id: str
    tenant_id: str
    account_id: str
    amount_minor: int
    currency: str
    merchant_name: str | None
    description: str | None
    date: datetime
    status: str


class _InvoiceRecord(BaseModel):
    id: str
    tenant_id: str
    contact_name: str | None
    outstanding_cents: int
    total_cents: int
    due_date: datetime | None
    status: str
    source: str | None


class _BillRecord(BaseModel):
    id: str
    tenant_id: str
    contact_name: str | None
    outstanding_cents: int
    total_cents: int
    due_date: datetime | None
    status: str
    source: str | None


class _ClaudeItemResult(BaseModel):
    item_id: str
    item_type: Literal["transaction", "invoice", "bill"]
    severity: Literal["low", "medium", "high"]
    action: Literal["ok", "review", "flag"]
    reasoning: str



def _parse_policy(config_json: dict) -> _ToolPolicy:
    raw = config_json.get("policy", config_json)
    return _ToolPolicy.model_validate({k: v for k, v in raw.items() if k in _ToolPolicy.model_fields})


def _amounts_match(txn_amount: int, outstanding_cents: int, tolerance_pct: float) -> bool:
    if outstanding_cents == 0:
        return txn_amount == 0
    return abs(txn_amount - outstanding_cents) <= int(outstanding_cents * tolerance_pct) + 1


def _dates_match(txn_date: datetime, due_date: datetime | None, window_days: int) -> bool:
    if due_date is None:
        return True
    return abs((txn_date.date() - due_date.date()).days) <= window_days



_CLAUDE_SYSTEM_PROMPT = (
    "You are a financial reconciliation model. Assess each unmatched item and return "
    "a JSON array — one object per item — with exactly these fields:\n"
    '  "item_id": string, "item_type": "transaction"|"invoice"|"bill",\n'
    '  "severity": "low"|"medium"|"high", "action": "ok"|"review"|"flag",\n'
    '  "reasoning": one concise sentence (include likely match suggestions where obvious).\n'
    "high=large/stale/duplicate; medium=moderate age; low=small/recent. "
    "flag=immediate; review=human needed; ok=auto-resolve. "
    "Return ONLY a valid JSON array. No markdown."
)


async def _call_claude(
    unmatched_txns: list[_TransactionRecord],
    unmatched_invs: list[_InvoiceRecord],
    unmatched_bills: list[_BillRecord],
    settings_obj,
) -> list[_ClaudeItemResult]:
    client = AsyncAnthropic(api_key=settings_obj.anthropic_api_key)
    payload = json.dumps(
        {
            "unmatched_transactions": [
                {"item_id": t.id, "item_type": "transaction", "amount_minor": t.amount_minor,
                 "currency": t.currency, "merchant_name": t.merchant_name,
                 "description": t.description, "date": t.date.isoformat(), "status": t.status}
                for t in unmatched_txns
            ],
            "unmatched_invoices": [
                {"item_id": i.id, "item_type": "invoice", "outstanding_cents": i.outstanding_cents,
                 "total_cents": i.total_cents, "contact_name": i.contact_name,
                 "due_date": i.due_date.isoformat() if i.due_date else None,
                 "status": i.status, "source": i.source}
                for i in unmatched_invs
            ],
            "unmatched_bills": [
                {"item_id": b.id, "item_type": "bill", "outstanding_cents": b.outstanding_cents,
                 "total_cents": b.total_cents, "contact_name": b.contact_name,
                 "due_date": b.due_date.isoformat() if b.due_date else None,
                 "status": b.status, "source": b.source}
                for b in unmatched_bills
            ],
        },
        default=str,
    )
    prompt = f"{_CLAUDE_SYSTEM_PROMPT}\n\nUnmatched items:\n{payload}"
    last_exc: Exception | None = None

    for attempt in range(settings_obj.max_agent_attempts):
        try:
            message = await client.messages.create(
                model=settings_obj.claude_model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = message.content[0].text.strip()
            parsed = json.loads(raw_text)
            if not isinstance(parsed, list):
                raise ValueError("Claude response is not a JSON array")
            return [_ClaudeItemResult(**item) for item in parsed]
        except (APIStatusError, APIConnectionError) as exc:
            last_exc = exc
            logger.error(
                "claude_api_error",
                extra={"attempt": attempt + 1, "error": str(exc)},
            )
            if attempt < settings_obj.max_agent_attempts - 1:
                await asyncio.sleep(settings_obj.backoff_seconds * (attempt + 1))
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            raise RuntimeError(f"Claude returned unparseable response: {exc}") from exc

    raise RuntimeError(
        f"Claude API failed after {settings_obj.max_agent_attempts} attempts: {last_exc}"
    )



async def _execute_reconciliation(
    tenant_id: str,
    tool_id: str,
    execution_id: str,
    period_days: int = 90,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
    account_id: str | None = None,
) -> dict:
    settings_obj = get_settings()
    db = get_db()

    if period_end is None:
        period_end = datetime.now(UTC)
    if period_start is None:
        period_start = period_end - timedelta(days=period_days)

    tool = await db.tool.find_first(where={"id": tool_id, "tenant_id": tenant_id})
    if tool is None:
        raise ValueError(f"Tool {tool_id} not found for tenant {tenant_id}")
    policy = _parse_policy(tool.config_json if isinstance(tool.config_json, dict) else {})

    txn_where: dict = {
        "tenant_id": tenant_id,
        "status": {"not": "reconciled"},
        "date": {"gte": period_start, "lte": period_end},
    }
    if account_id:
        txn_where["account_id"] = account_id
    raw_txns = await db.banktransaction.find_many(where=txn_where)
    transactions = [
        _TransactionRecord(
            id=t.id,
            tenant_id=t.tenant_id,
            account_id=t.account_id,
            amount_minor=t.amount_minor,
            currency=t.currency,
            merchant_name=t.merchant_name,
            description=t.description,
            date=t.date,
            status=t.status,
        )
        for t in raw_txns
    ]

    raw_invs = await db.accountinginvoice.find_many(
        where={
            "tenant_id": tenant_id,
            "status": {"in": ["sent", "viewed", "partial"]},
        }
    )
    invoices = [
        _InvoiceRecord(
            id=i.id,
            tenant_id=i.tenant_id,
            contact_name=i.contact_name,
            outstanding_cents=i.outstanding_cents,
            total_cents=i.total_cents,
            due_date=i.due_date,
            status=i.status,
            source=i.source,
        )
        for i in raw_invs
    ]

    raw_bills = await db.accountingbill.find_many(
        where={
            "tenant_id": tenant_id,
            "status": {"not_in": ["paid", "void"]},
        }
    )
    bills = [
        _BillRecord(
            id=b.id,
            tenant_id=b.tenant_id,
            contact_name=b.contact_name,
            outstanding_cents=b.outstanding_cents,
            total_cents=b.total_cents,
            due_date=b.due_date,
            status=b.status,
            source=b.source,
        )
        for b in raw_bills
    ]

    matched_txn_ids: set[str] = set()
    matched_inv_ids: set[str] = set()
    matched_bill_ids: set[str] = set()
    match_map: dict[str, dict] = {}

    for txn in transactions:
        for invoice in invoices:
            if invoice.id in matched_inv_ids:
                continue
            if (
                _amounts_match(txn.amount_minor, invoice.outstanding_cents, policy.match_amount_tolerance_pct)
                and _dates_match(txn.date, invoice.due_date, policy.match_date_window_days)
            ):
                matched_txn_ids.add(txn.id)
                matched_inv_ids.add(invoice.id)
                match_map[txn.id] = {"type": "invoice", "id": invoice.id}
                break

        if txn.id in matched_txn_ids:
            continue
        for bill in bills:
            if bill.id in matched_bill_ids:
                continue
            if (
                _amounts_match(txn.amount_minor, bill.outstanding_cents, policy.match_amount_tolerance_pct)
                and _dates_match(txn.date, bill.due_date, policy.match_date_window_days)
            ):
                matched_txn_ids.add(txn.id)
                matched_bill_ids.add(bill.id)
                match_map[txn.id] = {"type": "bill", "id": bill.id}
                break

    unmatched_txns = [t for t in transactions if t.id not in matched_txn_ids]
    unmatched_invs = [i for i in invoices if i.id not in matched_inv_ids]
    unmatched_bills = [b for b in bills if b.id not in matched_bill_ids]

    total_txns = len(transactions)
    unmatched_pct = len(unmatched_txns) / total_txns if total_txns > 0 else 0.0
    policy_breach = unmatched_pct > policy.unmatched_pct_threshold

    claude_results: list[_ClaudeItemResult] = []
    if unmatched_txns or unmatched_invs or unmatched_bills:
        claude_results = await _call_claude(
            unmatched_txns, unmatched_invs, unmatched_bills, settings_obj
        )

    has_flag = any(r.action == "flag" for r in claude_results) or policy_breach
    has_review = any(r.action == "review" for r in claude_results)

    if has_flag:
        overall_decision = "flagged"
    elif has_review:
        overall_decision = "approval_required"
    else:
        overall_decision = "auto_approved"

    total_items = len(transactions) + len(invoices) + len(bills)
    matched_count = len(matched_txn_ids) + len(matched_inv_ids) + len(matched_bill_ids)
    confidence = round(matched_count / total_items, 4) if total_items > 0 else 1.0

    reasoning_trace: dict = {
        "overall_decision": overall_decision,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "policy": policy.model_dump(),
        "transaction_count": len(transactions),
        "invoice_count": len(invoices),
        "bill_count": len(bills),
        "matched_transactions": len(matched_txn_ids),
        "matched_invoices": len(matched_inv_ids),
        "matched_bills": len(matched_bill_ids),
        "unmatched_transactions": len(unmatched_txns),
        "unmatched_invoices": len(unmatched_invs),
        "unmatched_bills": len(unmatched_bills),
        "unmatched_pct": round(unmatched_pct, 4),
        "policy_breach": policy_breach,
        "claude_assessments": [r.model_dump() for r in claude_results],
    }

    # Audit log BEFORE any DB updates — operation fails if audit fails
    await write_audit_log(
        tenant_id=tenant_id,
        actor=_ACTOR,
        action=f"reconciliation:{overall_decision}",
        reasoning_trace=reasoning_trace,
        model_version=_MODEL_VERSION,
        execution_id=execution_id,
    )

    if matched_txn_ids:
        await db.banktransaction.update_many(
            where={"id": {"in": list(matched_txn_ids)}, "tenant_id": tenant_id},
            data={"status": "reconciled"},
        )

    for txn_id, match_info in match_map.items():
        update_data: dict = {}
        if match_info["type"] == "invoice":
            update_data["matched_invoice_id"] = match_info["id"]
        else:
            update_data["matched_bill_id"] = match_info["id"]
        await db.banktransaction.update(
            where={"id": txn_id, "tenant_id": tenant_id},
            data=update_data,
        )

    await db.reconciliationrun.create(data={
        "tenant_id": tenant_id,
        "execution_id": execution_id,
        "period_start": period_start,
        "period_end": period_end,
        "status": "completed",
        "matched_count": len(matched_txn_ids),
        "unmatched_count": len(unmatched_txns),
        "flagged_count": sum(1 for r in claude_results if r.action == "flag"),
        "review_count": sum(1 for r in claude_results if r.action == "review"),
        "total_txn_count": len(transactions),
        "total_inv_count": len(invoices),
        "details_json": {
            "claude_assessments": [r.model_dump() for r in claude_results],
            "unmatched_transaction_ids": [t.id for t in unmatched_txns],
            "unmatched_invoice_ids": [i.id for i in unmatched_invs],
            "unmatched_bill_ids": [b.id for b in unmatched_bills],
            "policy_breach": policy_breach,
            "unmatched_pct": round(unmatched_pct, 4),
        },
    })

    actions_taken: list[str] = []
    if matched_txn_ids:
        actions_taken.append(f"reconciled {len(matched_txn_ids)} transaction(s)")
    if matched_inv_ids:
        actions_taken.append(f"matched {len(matched_inv_ids)} invoice(s)")
    if matched_bill_ids:
        actions_taken.append(f"matched {len(matched_bill_ids)} bill(s)")
    if unmatched_txns:
        actions_taken.append(f"{len(unmatched_txns)} transaction(s) unmatched — pending review")
    if policy_breach:
        actions_taken.append(
            f"policy breach: {unmatched_pct:.1%} unmatched exceeds "
            f"{policy.unmatched_pct_threshold:.1%} threshold"
        )
    if not actions_taken:
        actions_taken.append("no pending items found — nothing to reconcile")

    return {
        "decision": overall_decision,
        "confidence": confidence,
        "reasoning": json.dumps(reasoning_trace),
        "actions_taken": actions_taken,
        "output_data": reasoning_trace,
    }



async def run_reconciliation_job(
    ctx: dict,
    *,
    execution_id: str,
    tenant_id: str,
    tool_id: str,
    period_days: int = 90,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
    account_id: str | None = None,
) -> dict:
    db = get_db()
    settings_obj = get_settings()
    start_ms = int(time.time() * 1000)

    try:
        result = await _execute_reconciliation(
            tenant_id, tool_id, execution_id, period_days,
            period_start=period_start, period_end=period_end,
            account_id=account_id,
        )
        duration_ms = int(time.time() * 1000) - start_ms
        await db.execution.update(
            where={"id": execution_id},
            data={
                "status": "completed",
                "decision": result["decision"],
                "confidence": result["confidence"],
                "duration_ms": duration_ms,
            },
        )
        if result["decision"] == "approval_required":
            await db.approval.create(
                data={
                    "tenant_id": tenant_id,
                    "execution_id": execution_id,
                    "expires_at": datetime.now(UTC)
                    + timedelta(seconds=settings_obj.approval_ttl_seconds),
                }
            )
        return result
    except Exception as exc:
        try:
            await db.execution.update(
                where={"id": execution_id},
                data={"status": "failed", "decision": "failed"},
            )
        except Exception:
            pass
        if ctx.get("job_try", 1) >= 3:
            await push_to_dlq(
                job_id=str(ctx.get("job_id", "unknown")),
                function_name="run_reconciliation_job",
                error=str(exc),
            )
        raise



class ReconciliationTool(BaseTool):
    TOOL_TYPE = ToolType.RECONCILIATION
    VERSION = 1

    async def execute(self, input_data: dict, tenant_id: str) -> ToolOutput:
        execution_id: str = input_data["execution_id"]
        tool_id: str = input_data["tool_id"]
        period_days: int = input_data.get("period_days", 90)
        period_start: datetime | None = input_data.get("period_start")
        period_end: datetime | None = input_data.get("period_end")

        result = await _execute_reconciliation(
            tenant_id, tool_id, execution_id, period_days,
            period_start=period_start, period_end=period_end,
        )
        return ToolOutput(
            tool_type=self.TOOL_TYPE,
            decision=result["decision"],
            confidence=result["confidence"],
            reasoning=result["reasoning"],
            actions_taken=result["actions_taken"],
            output_data=result["output_data"],
        )
