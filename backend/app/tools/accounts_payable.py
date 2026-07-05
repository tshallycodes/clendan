"""
Accounts Payable Tool — sub-agent tool. Called by Financial Orchestrator as a tool.
Classifies AP bills, detects duplicates, routes approvals, and recommends pay/block actions.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from anthropic import APIConnectionError, APIStatusError, AsyncAnthropic
from pydantic import BaseModel

from app.audit.logger import write_audit_log
from app.core.config import get_settings
from app.core.db import get_db
from app.core.execution import complete_execution
from app.core.logging import get_logger
from app.queue.pool import push_to_dlq
from app.tools.base import BaseTool, ToolOutput, ToolType

logger = get_logger(__name__)

_ACTOR = "tool:accounts_payable:v1"
_MODEL_VERSION = "accounts_payable-v1"
TOOL_TYPE = ToolType.RECONCILIATION


class _ToolPolicy(BaseModel):
    auto_pay_limit_cents: int = 50_000
    approval_threshold_cents: int = 100_000
    duplicate_window_days: int = 30


class _BillRecord(BaseModel):
    id: str
    vendor_id: str | None
    contact_name: str | None
    total_cents: int
    outstanding_cents: int
    issue_date: date | None
    due_date: date | None
    status: str
    payment_terms: str | None = None
    purchase_order_ref: str | None = None
    is_duplicate: bool = False
    requires_approval: bool = False
    early_payment_discount_available: bool = False
    early_payment_discount_pct: float = 0.0
    early_payment_discount_cents: int = 0


class _ClaudeBillResult(BaseModel):
    bill_id: str
    classification: Literal["routine", "suspicious", "duplicate", "approval_required"]
    recommendation: Literal["auto_pay", "request_approval", "flag_duplicate", "block", "batch_pay"]
    reasoning: str
    missing_po: bool = False


def _parse_policy(config_json: dict) -> _ToolPolicy:
    raw = config_json.get("policy", config_json)
    return _ToolPolicy(
        auto_pay_limit_cents=raw.get("auto_pay_limit_cents", 50_000),
        approval_threshold_cents=raw.get("approval_threshold_cents", 100_000),
        duplicate_window_days=raw.get("duplicate_window_days", 30),
    )


def _detect_duplicates(bills: list[_BillRecord], window_days: int) -> None:
    """Mark bills as duplicate in-place: same contact + total + issue_date within window."""
    seen: dict[str, list[_BillRecord]] = {}
    for bill in bills:
        key = f"{bill.contact_name}|{bill.total_cents}"
        seen.setdefault(key, []).append(bill)

    for group in seen.values():
        if len(group) < 2:
            continue
        sorted_group = sorted(group, key=lambda b: b.issue_date or date.min)
        for i, bill in enumerate(sorted_group):
            for other in sorted_group[i + 1:]:
                if bill.issue_date and other.issue_date:
                    delta = abs((other.issue_date - bill.issue_date).days)
                    if delta <= window_days:
                        bill.is_duplicate = True
                        other.is_duplicate = True


_DISCOUNT_PATTERN = re.compile(r"(\d+(?:\.\d+)?)/(\d+)", re.IGNORECASE)


def _detect_early_payment_discounts(bills: list[_BillRecord]) -> None:
    """Parse payment_terms for early payment discounts (e.g. '2/10 net 30') and annotate bills in-place."""
    today = date.today()
    for bill in bills:
        if not bill.payment_terms or not bill.issue_date:
            continue
        match = _DISCOUNT_PATTERN.search(bill.payment_terms)
        if not match:
            continue
        discount_pct = float(match.group(1))
        discount_days = int(match.group(2))
        days_since_issue = (today - bill.issue_date).days
        if days_since_issue <= discount_days:
            bill.early_payment_discount_available = True
            bill.early_payment_discount_pct = discount_pct
            bill.early_payment_discount_cents = round(bill.outstanding_cents * discount_pct / 100)


def _group_by_supplier(bills: list[_BillRecord]) -> list[dict]:
    """Return supplier groups where a vendor has multiple outstanding bills."""
    groups: dict[str, list[_BillRecord]] = {}
    for bill in bills:
        key = bill.vendor_id or bill.contact_name or bill.id
        groups.setdefault(key, []).append(bill)
    return [
        {
            "supplier_id": key,
            "bill_ids": [b.id for b in group],
            "bill_count": len(group),
            "supplier_total_minor": sum(b.outstanding_cents for b in group),
        }
        for key, group in groups.items()
        if len(group) > 1
    ]


def _build_prompt(bills: list[_BillRecord], supplier_groups: list[dict]) -> str:
    bill_data = [
        {
            "bill_id": b.id, "vendor_id": b.vendor_id, "contact_name": b.contact_name,
            "total_cents": b.total_cents, "outstanding_cents": b.outstanding_cents,
            "issue_date": b.issue_date.isoformat() if b.issue_date else None,
            "due_date": b.due_date.isoformat() if b.due_date else None,
            "status": b.status, "purchase_order_ref": b.purchase_order_ref,
            "early_payment_discount_available": b.early_payment_discount_available,
            "early_payment_discount_pct": b.early_payment_discount_pct,
            "pre_flagged_duplicate": b.is_duplicate,
            "pre_flagged_approval_required": b.requires_approval,
        }
        for b in bills
    ]
    supplier_ctx = (
        f"\n\nSupplier groups (multiple bills from same supplier):\n{json.dumps(supplier_groups, indent=2)}"
        if supplier_groups else ""
    )
    return (
        "You are an accounts payable specialist. Analyse the bills below and return a JSON array "
        "— one object per bill — with exactly these fields:\n"
        '  "bill_id": string, "classification": "routine"|"suspicious"|"duplicate"|"approval_required",\n'
        '  "recommendation": "auto_pay"|"request_approval"|"flag_duplicate"|"block"|"batch_pay",\n'
        '  "reasoning": string, "missing_po": boolean\n\n'
        "Rules:\n"
        "- pre_flagged_duplicate=true → classification duplicate, recommendation flag_duplicate\n"
        "- pre_flagged_approval_required=true → classification approval_required, recommendation request_approval\n"
        "- early_payment_discount_available=true → prioritise for same-day payment; use auto_pay if within limit\n"
        "- Multiple bills with same vendor_id → recommend batch_pay to reduce transaction costs\n"
        "- Bill without purchase_order_ref → set missing_po=true\n"
        "- Suspicious signals: round amounts, new/unknown vendors, mismatched dates\n"
        "Return ONLY a valid JSON array. No markdown, no prose."
        + supplier_ctx
        + f"\n\nBills:\n{json.dumps(bill_data, indent=2)}"
    )


async def _call_claude(bills: list[_BillRecord], supplier_groups: list[dict], settings_obj) -> list[_ClaudeBillResult]:
    client = AsyncAnthropic(api_key=settings_obj.anthropic_api_key)
    prompt = _build_prompt(bills, supplier_groups)
    last_exc: Exception | None = None
    for attempt in range(settings_obj.max_agent_attempts):
        try:
            msg = await client.messages.create(model=settings_obj.claude_model, max_tokens=2048, messages=[{"role": "user", "content": prompt}])
            parsed = json.loads(msg.content[0].text.strip())
            if not isinstance(parsed, list):
                raise ValueError("Claude response is not a JSON array")
            return [_ClaudeBillResult(**item) for item in parsed]
        except (APIStatusError, APIConnectionError) as exc:
            last_exc = exc
            logger.error("claude_api_error", extra={"attempt": attempt + 1, "error": str(exc)})
            if attempt < settings_obj.max_agent_attempts - 1:
                await asyncio.sleep(settings_obj.backoff_seconds * (attempt + 1))
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            raise RuntimeError(f"Claude returned unparseable response: {exc}") from exc
    raise RuntimeError(f"Claude API failed after {settings_obj.max_agent_attempts} attempts: {last_exc}")


async def _execute(tenant_id: str, tool_id: str, execution_id: str, payload: dict) -> dict:
    settings_obj = get_settings()
    db = get_db()

    tool = await db.tool.find_first(where={"id": tool_id, "tenant_id": tenant_id})
    if tool is None:
        raise ValueError(f"Tool {tool_id} not found for tenant {tenant_id}")

    policy = _parse_policy(tool.config_json if isinstance(tool.config_json, dict) else {})

    raw = await db.accountingbill.find_many(
        where={
            "tenant_id": tenant_id,
            "status": {"not_in": ["paid", "void"]},
        },
        order={"due_date": "asc"},
    )

    if not raw:
        await write_audit_log(tenant_id=tenant_id, actor=_ACTOR, action="accounts_payable:no_action",
                              reasoning_trace={"reason": "no_outstanding_bills"}, model_version=_MODEL_VERSION, execution_id=execution_id)
        return {"decision": "no_action", "confidence": 1.0, "reasoning": "No outstanding bills found.", "actions_taken": [], "output_data": {"bill_count": 0}}

    def _to_date(val):
        return val.date() if isinstance(val, datetime) else val

    bills: list[_BillRecord] = [
        _BillRecord(
            id=b.id,
            vendor_id=getattr(b, "vendor_id", None) or getattr(b, "contact_id", None),
            contact_name=getattr(b, "contact_name", None),
            total_cents=b.total_cents, outstanding_cents=b.outstanding_cents,
            issue_date=_to_date(b.issue_date), due_date=_to_date(b.due_date),
            status=b.status, payment_terms=getattr(b, "payment_terms", None),
            purchase_order_ref=getattr(b, "purchase_order_ref", None),
            requires_approval=b.total_cents > policy.approval_threshold_cents,
        )
        for b in raw
    ]

    _detect_duplicates(bills, policy.duplicate_window_days)
    _detect_early_payment_discounts(bills)

    supplier_groups = _group_by_supplier(bills)
    claude_results = await _call_claude(bills, supplier_groups, settings_obj)
    claude_map = {r.bill_id: r for r in claude_results}

    # Policy check: never auto_pay above limit
    policy_overrides: list[str] = []
    for result in claude_results:
        if result.recommendation in ("auto_pay", "batch_pay"):
            bill = next((b for b in bills if b.id == result.bill_id), None)
            if bill and bill.total_cents > policy.auto_pay_limit_cents:
                result.recommendation = "request_approval"
                policy_overrides.append(
                    f"auto_pay blocked for bill {result.bill_id} "
                    f"(total {bill.total_cents} > limit {policy.auto_pay_limit_cents})"
                )

    has_block = any(r.recommendation == "block" for r in claude_results)
    has_approval = any(r.recommendation == "request_approval" for r in claude_results)
    has_duplicate = any(r.recommendation == "flag_duplicate" for r in claude_results)

    if has_block:
        overall = "blocked"
    elif has_approval:
        overall = "approval_required"
    elif has_duplicate:
        overall = "duplicates_flagged"
    else:
        overall = "auto_approved"

    confidence = 0.95 if overall == "auto_approved" else 0.85

    total_discount_available_minor = sum(b.early_payment_discount_cents for b in bills)
    bills_with_discount_count = sum(1 for b in bills if b.early_payment_discount_available)
    bills_missing_po_count = sum(1 for r in claude_results if r.missing_po)
    recommended_batch_payments = [
        {
            "supplier_id": g["supplier_id"],
            "bill_ids": g["bill_ids"],
            "total_minor": g["supplier_total_minor"],
        }
        for g in supplier_groups
    ]

    reasoning_trace = {
        "overall_decision": overall,
        "bill_count": len(bills),
        "total_discount_available_minor": total_discount_available_minor,
        "bills_with_discount_count": bills_with_discount_count,
        "bills_missing_po_count": bills_missing_po_count,
        "recommended_batch_payments": recommended_batch_payments,
        "policy": policy.model_dump(),
        "policy_overrides": policy_overrides,
        "per_bill": [
            {**claude_map[b.id].model_dump(), "is_duplicate": b.is_duplicate}
            if b.id in claude_map else {"bill_id": b.id, "classification": "unscored"}
            for b in bills
        ],
    }

    await write_audit_log(tenant_id=tenant_id, actor=_ACTOR, action=f"accounts_payable:{overall}",
                          reasoning_trace=reasoning_trace, model_version=_MODEL_VERSION, execution_id=execution_id)

    duplicate_count = sum(1 for b in bills if b.is_duplicate)
    actions_taken = [f"assessed {len(bills)} bill(s)"]
    if policy_overrides:
        actions_taken.extend(policy_overrides)
    if duplicate_count:
        actions_taken.append(f"flagged {duplicate_count} duplicate bill(s)")
    if bills_with_discount_count:
        actions_taken.append(f"identified {bills_with_discount_count} bill(s) with early payment discounts totalling {total_discount_available_minor} minor units")
    if bills_missing_po_count:
        actions_taken.append(f"flagged {bills_missing_po_count} bill(s) missing PO reference")
    if recommended_batch_payments:
        actions_taken.append(f"recommended {len(recommended_batch_payments)} batch payment(s)")

    return {
        "decision": overall,
        "confidence": confidence,
        "reasoning": json.dumps(reasoning_trace),
        "actions_taken": actions_taken,
        "output_data": reasoning_trace,
    }


async def run_accounts_payable_job(ctx: dict, *, execution_id: str, tenant_id: str, tool_id: str, payload: dict, policy_config: dict) -> dict:
    db = get_db()
    settings_obj = get_settings()
    start_ms = int(time.time() * 1000)
    try:
        result = await _execute(tenant_id, tool_id, execution_id, payload)
        duration_ms = int(time.time() * 1000) - start_ms
        await complete_execution(
            db=db, execution_id=execution_id, tool_id=tool_id,
            tenant_id=tenant_id, decision=result["decision"],
            confidence=result["confidence"], duration_ms=duration_ms,
        )
        return result
    except Exception as exc:
        try:
            await db.execution.update(where={"id": execution_id}, data={"status": "failed", "decision": "failed"})
        except Exception:
            pass
        if ctx.get("job_try", 1) >= 3:
            await push_to_dlq(job_id=str(ctx.get("job_id", "unknown")), function_name="run_accounts_payable_job", error=str(exc))
        raise


class AccountsPayableTool(BaseTool):
    TOOL_TYPE = ToolType.RECONCILIATION
    VERSION = 1

    async def execute(self, input_data: dict, tenant_id: str) -> ToolOutput:
        result = await _execute(tenant_id, input_data["tool_id"], input_data["execution_id"], input_data.get("payload", {}))
        return ToolOutput(
            tool_type=self.TOOL_TYPE, decision=result["decision"], confidence=result["confidence"],
            reasoning=result["reasoning"], actions_taken=result["actions_taken"], output_data=result["output_data"],
        )
