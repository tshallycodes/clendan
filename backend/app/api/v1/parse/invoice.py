import base64
import json
from typing import Optional

import anthropic
import fitz  # PyMuPDF
from fastapi import APIRouter, File, Header, HTTPException, UploadFile
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.models.invoice_parse import ParsedInvoice
from app.queue.pool import get_queue_pool

_logger = get_logger(__name__)

router = APIRouter(prefix="/parse", tags=["parse"])

ALLOWED_CONTENT_TYPES = {"application/pdf", "image/png", "image/jpeg"}
IDEMPOTENCY_TTL = 86400  # 24 hours
IDEMPOTENCY_PREFIX = "parse:invoice:"

MIN_CONFIDENCE = 0.5

_INVOICE_PROMPT = """You are an invoice data extraction system. Extract fields from this invoice and return ONLY a valid JSON object.

Fields:
- vendor (string): Vendor/supplier company name
- invoice_number (string): Invoice reference number
- line_items (array): [{description, quantity, unit_price_minor, total_minor}] — all amounts in minor units (pence/cents, multiply decimal by 100)
- amount_minor (integer): Total invoice amount in minor units
- currency (string): ISO 4217 code (GBP, USD, EUR, etc.)
- due_date (string|null): ISO 8601 date YYYY-MM-DD or null
- vat_minor (integer|null): VAT/tax amount in minor units or null
- po_number (string|null): Purchase order number or null
- confidence (float): Extraction confidence 0.0–1.0

Return ONLY the JSON object. No markdown, no explanation."""


def _pdf_to_images(pdf_bytes: bytes) -> list[bytes]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    return [page.get_pixmap(dpi=150).tobytes("png") for page in doc]


async def _call_claude(file_bytes: bytes, content_type: str) -> ParsedInvoice:
    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    if content_type == "application/pdf":
        images = _pdf_to_images(file_bytes)
        media_type = "image/png"
    else:
        images = [file_bytes]
        media_type = content_type

    content: list[dict] = []
    for img_bytes in images:
        b64 = base64.standard_b64encode(img_bytes).decode()
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": b64},
        })
    content.append({"type": "text", "text": _INVOICE_PROMPT})

    response = await client.messages.create(
        model=settings.claude_model,
        max_tokens=2048,
        messages=[{"role": "user", "content": content}],
    )
    raw_text = response.content[0].text
    try:
        data = json.loads(raw_text)
        return ParsedInvoice(**data)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"Claude returned unparseable invoice data: {exc}") from exc


@router.post("/invoice")
async def parse_invoice(
    file: UploadFile = File(...),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{file.content_type}'. Accepted: {sorted(ALLOWED_CONTENT_TYPES)}",
        )

    # Idempotency check — return cached result if key already seen
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
        raise HTTPException(status_code=502, detail="Invoice extraction service unavailable")

    if parsed.confidence < MIN_CONFIDENCE:
        raise HTTPException(
            status_code=422,
            detail=f"Extraction confidence {parsed.confidence:.2f} is below minimum {MIN_CONFIDENCE}. Document may be illegible.",
        )

    result = parsed.model_dump(mode="json")

    # Cache successful result for idempotency
    if idempotency_key:
        pool = await get_queue_pool()
        await pool.set(cache_key, json.dumps(result), ex=IDEMPOTENCY_TTL)

    return standard_response(data=result)
