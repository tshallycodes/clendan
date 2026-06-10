"""
tools/invoices.py — Invoice parsing and processing tools.

parse_invoice: Upload a local file, call the invoice parser, and return
               structured invoice data synchronously (polls until done).

run_invoice_worker: Run the Invoice Processing Worker on parsed invoice data.
"""
from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Any

from clendan_mcp.auth import MCPError, api_get, api_post

ALLOWED_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif"}
SUFFIX_TO_MIME = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
}

POLL_INTERVAL = 2.0   # seconds between polls
POLL_TIMEOUT = 90.0   # maximum wait before giving up


async def parse_invoice(file_path: str) -> dict[str, Any]:
    """
    Parse an invoice document and extract structured data.

    Accepts a local file path to a PDF, PNG, JPG, or TIFF file. Uploads the
    file to Clendan's invoice parser and waits for the result (up to 90 seconds).

    Returns:
        vendor (str): Supplier/vendor name
        invoice_number (str): Invoice reference number
        line_items (list): [{description, quantity, unit_price_minor, total_minor}]
        amount_minor (int): Total amount in minor currency units (pence/cents)
        currency (str): ISO 4217 currency code (e.g. GBP, USD, EUR)
        due_date (str | null): ISO 8601 date YYYY-MM-DD or null
        vat_minor (int | null): VAT/tax in minor units or null
        po_number (str | null): Purchase order number or null
        confidence (float): Extraction confidence score 0.0–1.0
        parse_id (str): ID for this parse operation (use in run_invoice_worker)

    Raises MCPError if the file doesn't exist, has an unsupported type,
    or parsing fails.
    """
    path = Path(file_path)
    if not path.exists():
        raise MCPError(f"File not found: {file_path}")
    if not path.is_file():
        raise MCPError(f"Path is not a file: {file_path}")

    suffix = path.suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise MCPError(
            f"Unsupported file type '{suffix}'. "
            f"Accepted types: {', '.join(sorted(ALLOWED_SUFFIXES))}"
        )

    mime_type = SUFFIX_TO_MIME[suffix]
    file_bytes = path.read_bytes()
    if not file_bytes:
        raise MCPError(f"File is empty: {file_path}")

    # Upload via multipart POST
    files = {"file": (path.name, file_bytes, mime_type)}
    submit_response = await api_post("/v1/parse/invoice", files=files)
    body = submit_response.get("data", submit_response)

    parse_id = body.get("parse_id")
    if not parse_id:
        raise MCPError("Invoice parser did not return a parse_id. Please try again.")

    status = body.get("status", "queued")

    # If already complete (cached result returned immediately)
    if status == "complete" and "result" in body:
        result = body["result"]
        result["parse_id"] = parse_id
        return result

    # Poll until complete or timed out
    deadline = time.monotonic() + POLL_TIMEOUT
    while time.monotonic() < deadline:
        await asyncio.sleep(POLL_INTERVAL)
        poll_response = await api_get(f"/v1/parse/invoice/{parse_id}")
        poll_body = poll_response.get("data", poll_response)
        poll_status = poll_body.get("status", "pending")

        if poll_status == "complete":
            result = poll_body.get("result", poll_body)
            result["parse_id"] = parse_id
            return result

        if poll_status == "failed":
            error = poll_body.get("error", "Unknown parsing error")
            raise MCPError(f"Invoice parsing failed: {error}")

    raise MCPError(
        f"Invoice parsing timed out after {int(POLL_TIMEOUT)} seconds. "
        "The file may be too large or the service is busy — try again."
    )


async def run_invoice_worker(invoice_data: dict[str, Any]) -> dict[str, Any]:
    """
    Run the Invoice Processing Worker on parsed invoice data.

    The worker validates the invoice against policy rules and takes one of
    three actions:
      - auto_approve: within thresholds, no approval needed
      - route_for_approval: above threshold, requires human review
      - block: policy violation or fraud signal detected

    Pass the dict returned by parse_invoice() directly, or construct your own
    with at least: vendor, amount_minor, currency, invoice_number.

    Returns:
        execution_id (str): Unique ID for this worker execution
        decision (str): "auto_approve" | "route_for_approval" | "block"
        confidence (float): Worker confidence 0.0–1.0
        reasoning (str): Plain-English explanation of the decision
        actions_taken (list): What the worker did (e.g. created QuickBooks bill)
        approval_id (str | null): Set if decision is route_for_approval
        duration_ms (int): How long the worker took in milliseconds
    """
    if not isinstance(invoice_data, dict):
        raise MCPError("invoice_data must be a dict. Pass the output of parse_invoice() directly.")
    if not invoice_data:
        raise MCPError("invoice_data is empty. Pass the output of parse_invoice() directly.")

    response = await api_post(
        "/v1/agents/run",
        data={
            "worker_type": "invoice_processing",
            "input": invoice_data,
        },
    )
    body = response.get("data", response)
    return body
