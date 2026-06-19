"""
Exchange rate service — fetches daily rates from exchangerate-api.com (v6, USD base)
and upserts them into the ExchangeRate table. Used by the daily arq cron job.
"""
import asyncio
from datetime import datetime, UTC

import httpx

from app.audit.logger import write_audit_log
from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.models.currency import SUPPORTED_CURRENCIES

logger = get_logger(__name__)

_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = 5.0
_API_BASE = "https://v6.exchangerate-api.com/v6"


async def fetch_and_upsert_rates() -> dict:
    """
    Fetches all 50 supported currency rates (USD base) from exchangerate-api.com
    and upserts into the ExchangeRate table.

    Returns a result dict with status, upserted count, or error.
    Never raises — on failure keeps existing stale rates intact.
    """
    settings = get_settings()

    if not settings.exchange_rates_api_key:
        logger.warning("exchange_rates_fetch_skipped", extra={"reason": "no_api_key"})
        return {"status": "skipped", "reason": "no_api_key"}

    db = get_db()
    managed_connection = not db.is_connected()
    if managed_connection:
        await db.connect()

    last_exc: Exception | None = None

    try:
        for attempt in range(_MAX_ATTEMPTS):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    url = f"{_API_BASE}/{settings.exchange_rates_api_key}/latest/USD"
                    response = await client.get(url)
                    response.raise_for_status()
                    data = response.json()

                if data.get("result") != "success":
                    raise ValueError(f"API result={data.get('result')} error={data.get('error-type', 'unknown')}")

                conversion_rates: dict = data.get("conversion_rates", {})
                if not conversion_rates:
                    raise ValueError("Empty conversion_rates in API response")

                upserted = 0
                missing: list[str] = []

                for code in SUPPORTED_CURRENCIES:
                    rate = conversion_rates.get(code)
                    if rate is None:
                        missing.append(code)
                        continue

                    existing = await db.exchangerate.find_first(
                        where={"base_currency": "USD", "target_currency": code}
                    )
                    if existing:
                        await db.exchangerate.update(
                            where={"id": existing.id},
                            data={"rate": str(rate)},
                        )
                    else:
                        await db.exchangerate.create(
                            data={"base_currency": "USD", "target_currency": code, "rate": str(rate)},
                        )
                    upserted += 1

                if missing:
                    logger.warning("exchange_rates_missing_currencies", extra={"codes": missing})

                logger.info("exchange_rates_fetched", extra={"upserted": upserted, "missing": len(missing)})
                return {"status": "ok", "upserted": upserted, "missing": missing}

            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "exchange_rates_fetch_attempt_failed",
                    extra={"attempt": attempt + 1, "error": str(exc)},
                )
                if attempt < _MAX_ATTEMPTS - 1:
                    await asyncio.sleep(_BACKOFF_SECONDS * (attempt + 1))

        # All attempts failed — keep existing stale rates, return error without raising
        logger.error(
            "exchange_rates_fetch_failed_all_attempts",
            extra={"attempts": _MAX_ATTEMPTS, "error": str(last_exc)},
        )
        return {"status": "failed", "error": str(last_exc), "attempts": _MAX_ATTEMPTS}

    finally:
        if managed_connection:
            await db.disconnect()


async def fetch_exchange_rates_daily(ctx: dict) -> dict:
    """
    arq cron job: fetches and upserts exchange rates daily.
    Writes to audit log on success or failure.
    """
    result = await fetch_and_upsert_rates()

    try:
        await write_audit_log(
            tenant_id="system",
            actor="cron:exchange_rates_daily",
            action=f"exchange_rates_fetch:{result['status']}",
            reasoning_trace={
                "result": result,
                "timestamp": datetime.now(UTC).isoformat(),
            },
            model_version="exchange-rates-v1",
        )
    except Exception as exc:
        # Audit failure is logged but does not fail the cron — rates are already upserted
        logger.error("exchange_rates_audit_write_failed", extra={"error": str(exc)})

    return result
