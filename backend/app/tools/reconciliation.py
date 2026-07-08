"""Reconciliation Tool - matches BankTransaction against AccountingInvoice (AR) and AccountingBill (AP).
Unmatched items are reviewed by Claude. Policy flags runs where unmatched % exceeds threshold."""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from datetime import UTC, datetime, timedelta
from typing import Literal

from anthropic import APIConnectionError, APIStatusError, AsyncAnthropic
from prisma import Json as PrismaJson
from pydantic import BaseModel

from app.audit.logger import write_audit_log
from app.core.config import get_settings
from app.core.db import get_db
from app.core.execution import complete_execution
from app.core.logging import get_logger
from app.queue.pool import push_to_dlq
from app.tools.base import BaseTool, ToolOutput, ToolType

logger = get_logger(__name__)

_ACTOR = "tool:bank_reconciliation:v1"
_MODEL_VERSION = "bank_reconciliation-v1"



class _ToolPolicy(BaseModel):
    unmatched_pct_threshold: float = 0.20
    match_amount_tolerance_minor: int = 150
    match_date_window_days: int = 5
    staleness_days: int = 30  # retained for backward-compat
    reconciliation_frequency: str = "daily"
    stale_open_item_days: int = 90
    unmatched_alert_days: int = 5
    include_reconciled: bool = False


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
    currency: str


class _BillRecord(BaseModel):
    id: str
    tenant_id: str
    contact_name: str | None
    outstanding_cents: int
    total_cents: int
    due_date: datetime | None
    status: str
    source: str | None
    currency: str


class _ClaudeItemResult(BaseModel):
    item_id: str
    item_type: Literal["transaction", "invoice", "bill"]
    severity: Literal["low", "medium", "high"]
    action: Literal["ok", "review", "flag"]
    reasoning: str



def _parse_policy(config_json: dict, overrides: dict | None = None) -> _ToolPolicy:
    raw = config_json.get("policy", config_json)
    merged = {k: v for k, v in raw.items() if k in _ToolPolicy.model_fields}
    # Frontend key → backend field remapping
    if "amount_tolerance_minor_units" in raw:
        merged["match_amount_tolerance_minor"] = int(raw["amount_tolerance_minor_units"])
    if "date_tolerance_days" in raw:
        merged["match_date_window_days"] = int(raw["date_tolerance_days"])
    # unmatched_pct_threshold stored as percentage (e.g. 20) → convert to fraction (0.20)
    if "unmatched_pct_threshold" in raw:
        val = float(raw["unmatched_pct_threshold"])
        merged["unmatched_pct_threshold"] = val / 100 if val > 1 else val
    if overrides:
        merged.update({k: v for k, v in overrides.items() if k in _ToolPolicy.model_fields})
    return _ToolPolicy.model_validate(merged)


def _amounts_match(txn_amount: int, outstanding_cents: int, tolerance_minor: int = 150) -> bool:
    if outstanding_cents == 0:
        return txn_amount == 0
    return abs(txn_amount - outstanding_cents) <= tolerance_minor


def _dates_match(txn_date: datetime, due_date: datetime | None, window_days: int) -> bool:
    if due_date is None:
        return True
    return abs((txn_date.date() - due_date.date()).days) <= window_days


def _currency_matches(txn_currency: str | None, item_currency: str | None) -> bool:
    """Never reconcile across currencies - a GBP transaction must not match a EUR
    invoice/bill even if the minor-unit amounts coincidentally fall within tolerance."""
    return (txn_currency or "").upper() == (item_currency or "").upper()



_CLAUDE_SYSTEM_PROMPT = (
    "You are a financial reconciliation model. Assess each unmatched item and classify it.\n"
    "You MUST respond with ONLY a raw JSON array (no markdown, no code fences, no explanation).\n"
    "Each element must have exactly: "
    '"item_id" (string), "item_type" ("transaction"|"invoice"|"bill"), '
    '"severity" ("low"|"medium"|"high"), "action" ("ok"|"review"|"flag"), '
    '"reasoning" (one sentence).\n'
    "Rules: high/flag=large amount or stale >90d or duplicate; "
    "medium/review=moderate; low/ok=small or recent.\n"
    "If the input list is empty, return an empty array: []"
)


_BATCH_SIZE = 20
_AUTO_OK_THRESHOLD_MINOR = 1500   # < £15: always auto-ok
_MAX_CLAUDE_TXN_ITEMS = 40        # cap: only top-N by amount go to Claude, rest auto-ok

_CACHE_TTL_SECONDS = 172800       # 48 hours - covers daily and weekly run cadences
_CACHE_KEY_PREFIX = "recon:assess:v1"


def _item_fingerprint(*parts: str | None) -> str:
    payload = ":".join(str(p or "") for p in parts)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


async def _call_claude_with_cache(
    tenant_id: str,
    unmatched_txns: list[_TransactionRecord],
    unmatched_invs: list[_InvoiceRecord],
    unmatched_bills: list[_BillRecord],
    settings_obj,
) -> list[_ClaudeItemResult]:
    """
    Claude assessment with Redis-backed per-item caching.

    Items whose data hasn't changed since the last run return cached results and
    bypass Claude entirely. Fingerprint is derived from the item's mutable fields;
    any data change causes a cache miss and a fresh Claude assessment.

    Falls back silently to a full uncached Claude call if Redis is unavailable.
    """
    txn_fps = {
        t.id: _item_fingerprint(str(t.amount_minor), t.status, t.merchant_name, t.description)
        for t in unmatched_txns
    }
    inv_fps = {
        i.id: _item_fingerprint(
            str(i.outstanding_cents), i.status,
            i.due_date.isoformat() if i.due_date else None, i.contact_name,
        )
        for i in unmatched_invs
    }
    bill_fps = {
        b.id: _item_fingerprint(
            str(b.outstanding_cents), b.status,
            b.due_date.isoformat() if b.due_date else None, b.contact_name,
        )
        for b in unmatched_bills
    }
    fingerprint_map = {**txn_fps, **inv_fps, **bill_fps}
    all_ids = list(fingerprint_map.keys())

    try:
        import redis.asyncio as aioredis
        redis_client = aioredis.from_url(
            settings_obj.redis_public_url,
            socket_connect_timeout=1,
            socket_timeout=1,
            retry_on_timeout=False,
        )
        async with redis_client:
            keys = [f"{_CACHE_KEY_PREFIX}:{tenant_id}:{item_id}:{fingerprint_map[item_id]}" for item_id in all_ids]
            values = await redis_client.mget(*keys) if keys else []

            cached_results: list[_ClaudeItemResult] = []
            uncached_ids: set[str] = set()
            for item_id, raw in zip(all_ids, values):
                if raw:
                    try:
                        cached_results.append(_ClaudeItemResult(**json.loads(raw)))
                    except Exception:
                        uncached_ids.add(item_id)
                else:
                    uncached_ids.add(item_id)

            logger.info("recon_cache_check", extra={
                "tenant_id": tenant_id,
                "cached": len(cached_results),
                "uncached": len(uncached_ids),
            })

            if not uncached_ids:
                return cached_results

            txns_nc = [t for t in unmatched_txns if t.id in uncached_ids]
            invs_nc  = [i for i in unmatched_invs  if i.id in uncached_ids]
            bills_nc = [b for b in unmatched_bills  if b.id in uncached_ids]

            new_results = await _call_claude(txns_nc, invs_nc, bills_nc, settings_obj)

            if new_results:
                pipe = redis_client.pipeline()
                for result in new_results:
                    fp = fingerprint_map.get(result.item_id)
                    if fp:
                        key = f"{_CACHE_KEY_PREFIX}:{tenant_id}:{result.item_id}:{fp}"
                        pipe.set(key, json.dumps(result.model_dump()), ex=_CACHE_TTL_SECONDS)
                await pipe.execute()

            return cached_results + new_results

    except Exception as exc:
        logger.warning("recon_cache_unavailable", extra={"error": str(exc)})
        return await _call_claude(unmatched_txns, unmatched_invs, unmatched_bills, settings_obj)


def _pre_classify(
    txns: list[_TransactionRecord],
) -> tuple[list[_TransactionRecord], list[_ClaudeItemResult]]:
    """Fast-path classification before Claude.

    1. Transactions below £15 → auto ok (clearly routine).
    2. Of the remainder, only the top _MAX_CLAUDE_TXN_ITEMS by |amount| go to Claude.
       Everything else → auto ok (lower-risk tail).
    This guarantees at most one Claude transaction batch regardless of dataset size.
    """
    auto: list[_ClaudeItemResult] = []
    above_threshold = []

    for txn in txns:
        if abs(txn.amount_minor) < _AUTO_OK_THRESHOLD_MINOR:
            auto.append(_ClaudeItemResult(
                item_id=txn.id,
                item_type="transaction",
                severity="low",
                action="ok",
                reasoning=f"Auto-classified: amount {abs(txn.amount_minor) / 100:.2f} below review threshold.",
            ))
        else:
            above_threshold.append(txn)

    # Sort by amount descending - highest risk first
    above_threshold.sort(key=lambda t: abs(t.amount_minor), reverse=True)
    needs_claude = above_threshold[:_MAX_CLAUDE_TXN_ITEMS]
    low_priority = above_threshold[_MAX_CLAUDE_TXN_ITEMS:]

    for txn in low_priority:
        auto.append(_ClaudeItemResult(
            item_id=txn.id,
            item_type="transaction",
            severity="low",
            action="ok",
            reasoning=f"Auto-classified: amount {abs(txn.amount_minor) / 100:.2f} below top-{_MAX_CLAUDE_TXN_ITEMS} review threshold.",
        ))

    return needs_claude, auto


async def _call_claude_batch(
    txns: list[_TransactionRecord],
    invs: list[_InvoiceRecord],
    bills: list[_BillRecord],
    client: AsyncAnthropic,
    settings_obj,
) -> list[_ClaudeItemResult]:
    """Single Claude call for one batch of items."""
    payload = json.dumps(
        {
            "unmatched_transactions": [
                {"item_id": t.id, "item_type": "transaction", "amount_minor": t.amount_minor,
                 "currency": t.currency, "merchant_name": t.merchant_name,
                 "description": t.description, "date": t.date.isoformat(), "status": t.status}
                for t in txns
            ],
            "unmatched_invoices": [
                {"item_id": i.id, "item_type": "invoice", "outstanding_cents": i.outstanding_cents,
                 "total_cents": i.total_cents, "contact_name": i.contact_name,
                 "due_date": i.due_date.isoformat() if i.due_date else None,
                 "status": i.status, "source": i.source}
                for i in invs
            ],
            "unmatched_bills": [
                {"item_id": b.id, "item_type": "bill", "outstanding_cents": b.outstanding_cents,
                 "total_cents": b.total_cents, "contact_name": b.contact_name,
                 "due_date": b.due_date.isoformat() if b.due_date else None,
                 "status": b.status, "source": b.source}
                for b in bills
            ],
        },
        default=str,
    )
    prompt = f"{_CLAUDE_SYSTEM_PROMPT}\n\nUnmatched items:\n{payload}"
    last_exc: Exception | None = None

    for attempt in range(settings_obj.max_agent_attempts):
        try:
            message = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            if message.stop_reason == "max_tokens":
                logger.warning("claude_response_truncated", extra={"chars": len(message.content[0].text)})
                raise RuntimeError("Claude response was truncated (max_tokens hit).")
            raw_text = message.content[0].text.strip()
            if not raw_text:
                return []
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
                raw_text = raw_text.strip()
            parsed = json.loads(raw_text)
            if not isinstance(parsed, list):
                raise ValueError("Claude response is not a JSON array")
            return [_ClaudeItemResult(**item) for item in parsed]
        except (APIStatusError, APIConnectionError) as exc:
            last_exc = exc
            logger.error("claude_api_error", extra={"attempt": attempt + 1, "error": str(exc)})
            if attempt < settings_obj.max_agent_attempts - 1:
                await asyncio.sleep(settings_obj.backoff_seconds * (attempt + 1))
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            raise RuntimeError(f"Claude returned unparseable response: {exc}") from exc

    raise RuntimeError(f"Claude API failed after {settings_obj.max_agent_attempts} attempts: {last_exc}")


async def _call_claude(
    unmatched_txns: list[_TransactionRecord],
    unmatched_invs: list[_InvoiceRecord],
    unmatched_bills: list[_BillRecord],
    settings_obj,
) -> list[_ClaudeItemResult]:
    """Batch-processes all unmatched items through Claude. All batches run in parallel."""
    import os
    api_key = settings_obj.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not configured. "
            "Set it as an environment variable on the worker service."
        )
    client = AsyncAnthropic(api_key=api_key)
    batch_coros = []

    for i in range(0, max(len(unmatched_txns), 1), _BATCH_SIZE):
        batch_txns = unmatched_txns[i:i + _BATCH_SIZE]
        if not batch_txns:
            break
        batch_coros.append(_call_claude_batch(batch_txns, [], [], client, settings_obj))

    inv_count = len(unmatched_invs)
    bill_count = len(unmatched_bills)
    if inv_count or bill_count:
        for i in range(0, max(inv_count, bill_count, 1), _BATCH_SIZE):
            batch_invs = unmatched_invs[i:i + _BATCH_SIZE]
            batch_bills = unmatched_bills[i:i + _BATCH_SIZE]
            if not batch_invs and not batch_bills:
                break
            batch_coros.append(_call_claude_batch([], batch_invs, batch_bills, client, settings_obj))

    if not batch_coros:
        return []

    batch_results = await asyncio.gather(*batch_coros)
    all_results: list[_ClaudeItemResult] = []
    for results in batch_results:
        all_results.extend(results)
    return all_results


_BANK_SOURCES = {"plaid", "truelayer", "mono", "stripe", "paypal"}


async def _execute_reconciliation(
    tenant_id: str,
    tool_id: str,
    execution_id: str,
    period_days: int = 90,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
    account_ids: list[str] | None = None,
    integration_sources: list[str] | None = None,
    triggered_by_email: str | None = None,
    policy_overrides: dict | None = None,
) -> dict:
    settings_obj = get_settings()
    db = get_db()
    _t0 = time.time()

    if period_end is None:
        period_end = datetime.now(UTC)
    if period_start is None:
        period_start = period_end - timedelta(days=period_days)

    tool = await db.tool.find_first(where={"id": tool_id, "tenant_id": tenant_id})
    if tool is None:
        raise ValueError(f"Tool {tool_id} not found for tenant {tenant_id}")
    policy = _parse_policy(
        tool.config_json if isinstance(tool.config_json, dict) else {},
        overrides=policy_overrides,
    )

    txn_statuses = ["pending", "unprocessed", "categorised"]
    if policy.include_reconciled:
        txn_statuses.append("reconciled")
    txn_where: dict = {
        "tenant_id": tenant_id,
        "status": {"in": txn_statuses},
        "date": {"gte": period_start, "lte": period_end},
    }
    if account_ids:
        txn_where["account_id"] = {"in": account_ids}

    bank_sources = [s for s in (integration_sources or []) if s in _BANK_SOURCES]
    acct_sources = [s for s in (integration_sources or []) if s not in _BANK_SOURCES]

    if bank_sources:
        txn_where["source"] = {"in": bank_sources}

    inv_where: dict = {"tenant_id": tenant_id, "status": {"in": ["sent", "viewed", "partial"]}}
    bill_where: dict = {"tenant_id": tenant_id, "status": {"not_in": ["paid", "void"]}}
    if acct_sources:
        inv_where["source"] = {"in": acct_sources}
        bill_where["source"] = {"in": acct_sources}

    raw_txns, raw_invs, raw_bills = await asyncio.gather(
        db.banktransaction.find_many(where=txn_where),
        db.accountinginvoice.find_many(where=inv_where),
        db.accountingbill.find_many(where=bill_where),
    )
    _t_db = time.time()
    logger.info("recon_phase_db", extra={
        "tenant_id": tenant_id, "ms": int((_t_db - _t0) * 1000),
        "txns": len(raw_txns), "invs": len(raw_invs), "bills": len(raw_bills),
    })

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
            currency=i.currency,
        )
        for i in raw_invs
    ]
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
            currency=b.currency,
        )
        for b in raw_bills
    ]

    matched_txn_ids: set[str] = set()
    matched_inv_ids: set[str] = set()
    matched_bill_ids: set[str] = set()
    match_map: dict[str, dict] = {}

    for txn in transactions:
        txn_abs = abs(txn.amount_minor)
        if txn.amount_minor < 0:
            # Credit (money in) - match against invoices
            for invoice in invoices:
                if invoice.id in matched_inv_ids:
                    continue
                if (
                    _currency_matches(txn.currency, invoice.currency)
                    and _amounts_match(txn_abs, invoice.outstanding_cents, policy.match_amount_tolerance_minor)
                    and _dates_match(txn.date, invoice.due_date, policy.match_date_window_days)
                ):
                    matched_txn_ids.add(txn.id)
                    matched_inv_ids.add(invoice.id)
                    match_map[txn.id] = {"type": "invoice", "id": invoice.id}
                    break
        elif txn.amount_minor > 0:
            # Debit (money out) - match against bills
            for bill in bills:
                if bill.id in matched_bill_ids:
                    continue
                if (
                    _currency_matches(txn.currency, bill.currency)
                    and _amounts_match(txn_abs, bill.outstanding_cents, policy.match_amount_tolerance_minor)
                    and _dates_match(txn.date, bill.due_date, policy.match_date_window_days)
                ):
                    matched_txn_ids.add(txn.id)
                    matched_bill_ids.add(bill.id)
                    match_map[txn.id] = {"type": "bill", "id": bill.id}
                    break
        # Zero-amount transactions are passed to Claude for assessment

    unmatched_txns = [t for t in transactions if t.id not in matched_txn_ids]
    unmatched_invs = [i for i in invoices if i.id not in matched_inv_ids]
    unmatched_bills = [b for b in bills if b.id not in matched_bill_ids]

    total_txns = len(transactions)
    unmatched_pct = len(unmatched_txns) / total_txns if total_txns > 0 else 0.0
    policy_breach = unmatched_pct > policy.unmatched_pct_threshold

    _t_match = time.time()
    logger.info("recon_phase_matching", extra={
        "tenant_id": tenant_id, "ms": int((_t_match - _t_db) * 1000),
        "matched_txns": len(matched_txn_ids),
        "unmatched_txns": len(unmatched_txns),
        "unmatched_invs": len(unmatched_invs),
        "unmatched_bills": len(unmatched_bills),
    })

    txns_for_claude, auto_results = _pre_classify(unmatched_txns)
    claude_results: list[_ClaudeItemResult] = list(auto_results)
    if txns_for_claude or unmatched_invs or unmatched_bills:
        claude_results.extend(await _call_claude_with_cache(
            tenant_id, txns_for_claude, unmatched_invs, unmatched_bills, settings_obj
        ))

    _t_claude = time.time()
    logger.info("recon_phase_claude", extra={
        "tenant_id": tenant_id, "ms": int((_t_claude - _t_match) * 1000),
        "claude_txns_in": len(txns_for_claude),
        "auto_ok": len(auto_results),
        "total_assessments": len(claude_results),
    })

    # Enforce stale_open_item_days (→ flag) and unmatched_alert_days (→ review).
    # Claude and pre-classify only set action=ok on unmatched transactions - upgrade
    # those that have breached the configured age thresholds.
    txn_by_id = {t.id: t for t in unmatched_txns}
    _tz = UTC
    _now = period_end if period_end.tzinfo else period_end.replace(tzinfo=_tz)
    stale_cutoff = _now - timedelta(days=policy.stale_open_item_days)
    alert_cutoff = _now - timedelta(days=policy.unmatched_alert_days)
    upgraded: list[_ClaudeItemResult] = []
    for result in claude_results:
        if result.item_type == "transaction" and result.action == "ok":
            txn = txn_by_id.get(result.item_id)
            if txn:
                txn_date = txn.date if txn.date.tzinfo else txn.date.replace(tzinfo=_tz)
                age_days = (_now - txn_date).days
                if txn_date < stale_cutoff:
                    upgraded.append(_ClaudeItemResult(
                        item_id=result.item_id,
                        item_type="transaction",
                        severity="high",
                        action="flag",
                        reasoning=f"Stale: unmatched for {age_days} day(s) - exceeds stale threshold of {policy.stale_open_item_days} day(s).",
                    ))
                    continue
                if txn_date < alert_cutoff:
                    upgraded.append(_ClaudeItemResult(
                        item_id=result.item_id,
                        item_type="transaction",
                        severity="medium",
                        action="review",
                        reasoning=f"Unmatched for {age_days} day(s) - exceeds alert threshold of {policy.unmatched_alert_days} day(s).",
                    ))
                    continue
        upgraded.append(result)
    claude_results = upgraded

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

    # Audit log BEFORE any DB updates - operation fails if audit fails
    await write_audit_log(
        tenant_id=tenant_id,
        actor=_ACTOR,
        action=f"bank_reconciliation:{overall_decision}",
        reasoning_trace=reasoning_trace,
        model_version=_MODEL_VERSION,
        execution_id=execution_id,
    )

    match_updates = []
    if matched_txn_ids:
        match_updates.append(
            db.banktransaction.update_many(
                where={"id": {"in": list(matched_txn_ids)}, "tenant_id": tenant_id},
                data={"status": "reconciled"},
            )
        )
    for txn_id, match_info in match_map.items():
        update_data: dict = (
            {"matched_invoice_id": match_info["id"]}
            if match_info["type"] == "invoice"
            else {"matched_bill_id": match_info["id"]}
        )
        match_updates.append(
            db.banktransaction.update(
                where={"id": txn_id, "tenant_id": tenant_id},
                data=update_data,
            )
        )
    if match_updates:
        await asyncio.gather(*match_updates)

    # Idempotent per execution: a job retry re-runs _execute fully (matches are
    # idempotent), so guard on execution_id to avoid a duplicate ReconciliationRun row.
    existing_run = await db.reconciliationrun.find_first(
        where={"tenant_id": tenant_id, "execution_id": execution_id}
    )
    if existing_run is None:
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
            "triggered_by_email": triggered_by_email,
            "details_json": PrismaJson({
                "claude_assessments": [r.model_dump() for r in claude_results],
                "unmatched_transaction_ids": [t.id for t in unmatched_txns],
                "unmatched_invoice_ids": [i.id for i in unmatched_invs],
                "unmatched_bill_ids": [b.id for b in unmatched_bills],
                "policy_breach": policy_breach,
                "unmatched_pct": round(unmatched_pct, 4),
            }),
        })

    actions_taken: list[str] = []
    if matched_txn_ids:
        actions_taken.append(f"reconciled {len(matched_txn_ids)} transaction(s)")
    if matched_inv_ids:
        actions_taken.append(f"matched {len(matched_inv_ids)} invoice(s)")
    if matched_bill_ids:
        actions_taken.append(f"matched {len(matched_bill_ids)} bill(s)")
    if unmatched_txns:
        actions_taken.append(f"{len(unmatched_txns)} transaction(s) unmatched - pending review")
    if policy_breach:
        actions_taken.append(
            f"policy breach: {unmatched_pct:.1%} unmatched exceeds "
            f"{policy.unmatched_pct_threshold:.1%} threshold"
        )
    if not actions_taken:
        actions_taken.append("no pending items found - nothing to reconcile")

    logger.info("recon_phase_total", extra={
        "tenant_id": tenant_id,
        "total_ms": int((time.time() - _t0) * 1000),
        "decision": overall_decision,
    })

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
    account_ids: list[str] | None = None,
    integration_sources: list[str] | None = None,
    triggered_by_email: str | None = None,
) -> dict:
    db = get_db()
    start_ms = int(time.time() * 1000)

    await db.execution.update(
        where={"id": execution_id},
        data={"status": "running"},
    )

    try:
        result = await _execute_reconciliation(
            tenant_id, tool_id, execution_id, period_days,
            period_start=period_start, period_end=period_end,
            account_ids=account_ids,
            integration_sources=integration_sources,
            triggered_by_email=triggered_by_email,
        )
        duration_ms = int(time.time() * 1000) - start_ms
        final_decision = await complete_execution(
            db=db, execution_id=execution_id, tool_id=tool_id,
            tenant_id=tenant_id, decision=result["decision"],
            confidence=result["confidence"], duration_ms=duration_ms,
        )
        return {**result, "decision": final_decision}
    except Exception as exc:
        logger.error(
            "reconciliation_job_failed",
            extra={"execution_id": execution_id, "tenant_id": tenant_id, "error": str(exc)},
        )
        try:
            await db.execution.update(
                where={"id": execution_id},
                data={"status": "failed", "decision": "failed", "error_message": str(exc)[:2000]},
            )
        except Exception as db_exc:
            logger.error("reconciliation_db_update_failed", extra={"error": str(db_exc)})
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
