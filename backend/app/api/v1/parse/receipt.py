import base64
import json
import uuid
from typing import Optional

import anthropic
from fastapi import APIRouter, File, Header, HTTPException, Path, UploadFile
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth
from app.models.receipt_parse import ALLOWED_CATEGORIES, ParsedReceipt
from app.queue.pool import get_queue_pool, push_to_dlq

_logger = get_logger(__name__)

router = APIRouter(prefix="/parse", tags=["parse"])

ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg"}
IDEMPOTENCY_TTL = 86400
PARSE_RESULT_TTL = 3600
IDEMPOTENCY_PREFIX = "parse:receipt:idem:"
RESULT_PREFIX = "parse:receipt:result:"
MIN_CONFIDENCE = 0.5

_RECEIPT_PROMPT = f"""You are a receipt data extraction system. Extract fields from this receipt image and return ONLY a valid JSON object.

Fields:
- merchant (string): Store or vendor name
- amount_minor (integer): Total amount paid in minor units (multiply decimal by 100, round to integer — e.g. £12.50 → 1250)
- currency (string): ISO 4217 code (GBP, USD, EUR, etc.)
- date (string|null): ISO 8601 date YYYY-MM-DD or null if not visible
- category (string): One of: {", ".join(sorted(ALLOWED_CATEGORIES))}
- confidence (float): Extraction confidence 0.0–1.0

Return ONLY the JSON object. No markdown, no explanation."""


async def _call_claude(file_bytes: bytes, content_type: str) -> ParsedReceipt:
    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    b64 = base64.standard_b64encode(file_bytes).decode()
    content = [
        {"type": "image", "source": {"type": "base64", "media_type": content_type, "data": b64}},
        {"type": "text", "text": _RECEIPT_PROMPT},
    ]

    response = await client.messages.create(
        model=settings.claude_model,
        max_tokens=512,
        messages=[{"role": "user", "content": content}],
    )
    raw_text = response.content[0].text
    try:
        data = json.loads(raw_text)
        return ParsedReceipt(**data)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"Claude returned unparseable receipt data: {exc}") from exc


async def run_parse_receipt_job(
    ctx: dict,
    *,
    parse_id: str,
    tenant_id: str,
    file_bytes: bytes,
    content_type: str,
) -> dict:
    """arq job: calls Claude, stores result in Redis for the client to poll."""
    pool = await get_queue_pool()
    result_key = f"{RESULT_PREFIX}{parse_id}"
    try:
        parsed = await _call_claude(file_bytes, content_type)
        await pool.set(
            result_key,
            json.dumps({"status": "complete", "result": parsed.model_dump(mode="json")}),
            ex=PARSE_RESULT_TTL,
        )
        return {"parse_id": parse_id, "status": "complete"}
    except Exception as exc:
        await pool.set(
            result_key,
            json.dumps({"status": "failed", "error": str(exc)}),
            ex=PARSE_RESULT_TTL,
        )
        if ctx.get("job_try", 1) >= 3:
            await push_to_dlq(str(ctx.get("job_id", "unknown")), "run_parse_receipt_job", str(exc))
        raise


@router.post("/receipt")
async def parse_receipt(
    current_user: RequireOrgAuth,
    file: UploadFile = File(...),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    """
    Enqueues a receipt parse job and returns a parse_id immediately.
    Poll GET /v1/parse/receipt/{parse_id} for the result.
    Claude is called in the background — the request thread is never blocked.
    """
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{file.content_type}'. Accepted: {sorted(ALLOWED_CONTENT_TYPES)}",
        )

    pool = await get_queue_pool()

    if idempotency_key:
        idem_key = f"{IDEMPOTENCY_PREFIX}{current_user.tenant_id}:{idempotency_key}"
        existing = await pool.get(idem_key)
        if existing:
            parse_id = existing.decode() if isinstance(existing, bytes) else existing
            _logger.info("idempotency_cache_hit", extra={"key": idempotency_key})
            cached_result = await pool.get(f"{RESULT_PREFIX}{parse_id}")
            if cached_result:
                return standard_response(data=json.loads(cached_result))
            return standard_response(data={"parse_id": parse_id, "status": "pending"})

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    parse_id = str(uuid.uuid4())

    await pool.enqueue_job(
        "run_parse_receipt_job",
        parse_id=parse_id,
        tenant_id=current_user.tenant_id,
        file_bytes=file_bytes,
        content_type=file.content_type,
    )

    if idempotency_key:
        await pool.set(idem_key, parse_id, ex=IDEMPOTENCY_TTL)

    _logger.info("parse_receipt_enqueued", extra={"parse_id": parse_id, "tenant_id": current_user.tenant_id})

    return standard_response(data={"parse_id": parse_id, "status": "queued"})


@router.get("/receipt/{parse_id}")
async def get_receipt_parse_result(
    current_user: RequireOrgAuth,
    parse_id: str = Path(...),
):
    """Poll for the result of a previously enqueued receipt parse."""
    pool = await get_queue_pool()
    cached = await pool.get(f"{RESULT_PREFIX}{parse_id}")
    if not cached:
        return standard_response(data={"parse_id": parse_id, "status": "pending"})
    return standard_response(data=json.loads(cached))
