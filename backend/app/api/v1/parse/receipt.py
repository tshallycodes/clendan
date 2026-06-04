import base64
import json
from typing import Optional

import anthropic
from fastapi import APIRouter, File, Header, HTTPException, UploadFile
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.models.receipt_parse import ALLOWED_CATEGORIES, ParsedReceipt
from app.queue.pool import get_queue_pool

_logger = get_logger(__name__)

router = APIRouter(prefix="/parse", tags=["parse"])

ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg"}
IDEMPOTENCY_TTL = 86400
IDEMPOTENCY_PREFIX = "parse:receipt:"
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
        {
            "type": "image",
            "source": {"type": "base64", "media_type": content_type, "data": b64},
        },
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


@router.post("/receipt")
async def parse_receipt(
    file: UploadFile = File(...),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{file.content_type}'. Accepted: {sorted(ALLOWED_CONTENT_TYPES)}",
        )

    if idempotency_key:
        pool = await get_queue_pool()
        cache_key = f"{IDEMPOTENCY_PREFIX}{x_tenant_id}:{idempotency_key}"
        cached = await pool.get(cache_key)
        if cached:
            _logger.info("idempotency_cache_hit", extra={"key": idempotency_key})
            return standard_response(data=json.loads(cached))

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    try:
        parsed = await _call_claude(file_bytes, file.content_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except anthropic.APIError as exc:
        _logger.error("claude_api_error", extra={"error": str(exc)})
        raise HTTPException(status_code=502, detail="Receipt extraction service unavailable")

    if parsed.confidence < MIN_CONFIDENCE:
        raise HTTPException(
            status_code=422,
            detail=f"Extraction confidence {parsed.confidence:.2f} is below minimum {MIN_CONFIDENCE}. Image may be illegible.",
        )

    result = parsed.model_dump(mode="json")

    if idempotency_key:
        pool = await get_queue_pool()
        await pool.set(cache_key, json.dumps(result), ex=IDEMPOTENCY_TTL)

    return standard_response(data=result)
