"""
tools/api_tools.py — Standalone financial analysis tool wrappers.

These tools map to purpose-built API endpoints for fraud scoring,
reconciliation, and contract extraction. They are not tool executions —
they call direct API endpoints and return synchronous results.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from clendan_mcp.auth import MCPError, api_post

VALID_TRANSACTION_TYPES = {
    "payment",
    "transfer",
    "refund",
    "withdrawal",
    "deposit",
    "charge",
    "other",
}

CONTRACT_ALLOWED_SUFFIXES = {".pdf"}
CONTRACT_MIME = "application/pdf"


async def score_fraud(
    transaction_id: str,
    amount_minor: int,
    currency: str,
    counterparty: str,
    transaction_type: str,
) -> dict[str, Any]:
    """
    Score a transaction for fraud risk.

    Runs the transaction through Clendan's fraud detection model and returns
    a risk assessment with detected signals and a recommended action.

    Args:
        transaction_id: Your internal transaction reference ID
        amount_minor: Transaction amount in minor currency units (pence/cents).
            For example, £12.50 = 1250.
        currency: ISO 4217 currency code (e.g. "GBP", "USD", "EUR")
        counterparty: Counterparty name, account number, or identifier
        transaction_type: One of: payment, transfer, refund, withdrawal,
            deposit, charge, other

    Returns:
        risk_score (float): Risk score 0.0 (safe) to 1.0 (high risk)
        risk_level (str): "low" | "medium" | "high" | "critical"
        signals (list): Detected risk signals, each with name and description
        action (str): Recommended action: "allow" | "flag" | "block"
        confidence (float): Model confidence 0.0–1.0
        reasoning (str): Plain-English explanation of the risk assessment
    """
    if not transaction_id or not transaction_id.strip():
        raise MCPError("transaction_id is required.")
    if amount_minor < 0:
        raise MCPError("amount_minor must be a non-negative integer (pence/cents).")
    if not currency or len(currency) != 3:
        raise MCPError("currency must be a 3-letter ISO 4217 code (e.g. 'GBP', 'USD').")
    if not counterparty or not counterparty.strip():
        raise MCPError("counterparty is required.")
    if transaction_type not in VALID_TRANSACTION_TYPES:
        raise MCPError(
            f"Invalid transaction_type '{transaction_type}'. "
            f"Valid types: {', '.join(sorted(VALID_TRANSACTION_TYPES))}"
        )

    response = await api_post(
        "/v1/fraud/score",
        data={
            "transaction_id": transaction_id.strip(),
            "amount_minor": amount_minor,
            "currency": currency.upper(),
            "counterparty": counterparty.strip(),
            "transaction_type": transaction_type,
        },
    )
    return response.get("data", response)


async def reconcile_datasets(
    source_records: list[dict[str, Any]],
    target_records: list[dict[str, Any]],
    period_start: str,
    period_end: str,
) -> dict[str, Any]:
    """
    Reconcile two financial datasets to identify matches, gaps, and discrepancies.

    Useful for month-end close: compare your internal records against bank
    statements, accounting system exports, or payment processor data.

    Each record in source_records and target_records should be a dict with
    at least: id, amount_minor, currency, date, and description.

    Args:
        source_records: Your source dataset (e.g. internal payment records).
            Each record: {id, amount_minor, currency, date, description, ...}
        target_records: Your target dataset (e.g. bank statement entries).
            Each record: {id, amount_minor, currency, date, description, ...}
        period_start: Start of reconciliation period in YYYY-MM-DD format
        period_end: End of reconciliation period in YYYY-MM-DD format

    Returns:
        matched (list): Records that matched between source and target
        unmatched_source (list): Source records with no match in target
        unmatched_target (list): Target records with no match in source
        flagged_discrepancies (list): Partial matches with amount/date differences
        confidence (float): Overall reconciliation confidence 0.0–1.0
        summary (dict): Count breakdown: total, matched, unmatched, flagged
    """
    if not isinstance(source_records, list):
        raise MCPError("source_records must be a list of dicts.")
    if not isinstance(target_records, list):
        raise MCPError("target_records must be a list of dicts.")
    if not source_records and not target_records:
        raise MCPError("Both source_records and target_records are empty — nothing to reconcile.")
    if not period_start:
        raise MCPError("period_start is required (format: YYYY-MM-DD).")
    if not period_end:
        raise MCPError("period_end is required (format: YYYY-MM-DD).")
    if period_end < period_start:
        raise MCPError("period_end must be on or after period_start.")

    response = await api_post(
        "/v1/reconcile",
        data={
            "source_dataset": source_records,
            "target_dataset": target_records,
            "period_start": period_start,
            "period_end": period_end,
        },
    )
    return response.get("data", response)


async def extract_contract_data(file_path: str) -> dict[str, Any]:
    """
    Extract structured data from a contract PDF.

    Parses a contract document using Clendan's contract extraction model
    and returns key commercial terms in structured form.

    Accepts a local file path to a PDF only (other formats not yet supported).

    Args:
        file_path: Absolute or relative path to the contract PDF file.

    Returns:
        counterparty (str): Other party to the contract
        payment_terms (str): Payment terms (e.g. "Net 30", "50% upfront")
        renewal_date (str | null): Contract renewal/expiry date YYYY-MM-DD or null
        obligations (list): Key contractual obligations as plain-English strings
        amounts (list): Financial amounts: [{description, amount_minor, currency}]
        governing_law (str): Jurisdiction/governing law
        effective_date (str | null): Contract effective date YYYY-MM-DD or null
        confidence (float): Extraction confidence 0.0–1.0
        notes (str | null): Anything the model flagged for review
    """
    path = Path(file_path)
    if not path.exists():
        raise MCPError(f"File not found: {file_path}")
    if not path.is_file():
        raise MCPError(f"Path is not a file: {file_path}")

    suffix = path.suffix.lower()
    if suffix not in CONTRACT_ALLOWED_SUFFIXES:
        raise MCPError(
            f"Unsupported file type '{suffix}'. "
            "Contract extraction only supports PDF files (.pdf)."
        )

    file_bytes = path.read_bytes()
    if not file_bytes:
        raise MCPError(f"File is empty: {file_path}")

    files = {"file": (path.name, file_bytes, CONTRACT_MIME)}
    response = await api_post("/v1/parse/contract", files=files)
    return response.get("data", response)
