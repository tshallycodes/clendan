"""
Xero API calls — accounts, contacts, connection revocation.
All calls go through the circuit breaker and retry helper.
"""
import asyncio
import random

import httpx

from app.core.logging import get_logger
from app.integrations.xero.circuit_breaker import _circuit

logger = get_logger(__name__)

XERO_API_BASE = "https://api.xero.com/api.xro/2.0"
XERO_CONNECTIONS_URL = "https://api.xero.com/connections"

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 1.0


async def _retry(fn, *args, **kwargs):
    """Exponential backoff with jitter. Raises on final failure."""
    last_exc = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            return await fn(*args, **kwargs)
        except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.NetworkError) as exc:
            last_exc = exc
            if attempt < MAX_ATTEMPTS - 1:
                wait = BACKOFF_SECONDS * (2 ** attempt) + random.uniform(0, 0.5)
                logger.warning(
                    "xero_api_call_failed attempt=%d/%d retry_in=%.1fs",
                    attempt + 1, MAX_ATTEMPTS, wait,
                )
                await asyncio.sleep(wait)
    raise last_exc


async def get_accounts(access_token: str, xero_tenant_id: str) -> list:
    """
    GET /api.xro/2.0/Accounts — returns list of chart-of-accounts entries.
    Validates response is non-empty before returning.
    """
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{XERO_API_BASE}/Accounts",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Xero-Tenant-Id": xero_tenant_id,
                    "Accept": "application/json",
                },
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    raw = await _circuit.call(_retry, _call)
    accounts = raw.get("Accounts", [])
    if not isinstance(accounts, list):
        raise ValueError("Xero returned unexpected Accounts shape — sync aborted")
    return accounts


async def get_contacts(access_token: str, xero_tenant_id: str) -> list:
    """
    GET /api.xro/2.0/Contacts — returns list of contacts (suppliers, customers).
    Validates response is non-empty before returning.
    """
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{XERO_API_BASE}/Contacts",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Xero-Tenant-Id": xero_tenant_id,
                    "Accept": "application/json",
                },
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    raw = await _circuit.call(_retry, _call)
    contacts = raw.get("Contacts", [])
    if not isinstance(contacts, list):
        raise ValueError("Xero returned unexpected Contacts shape — sync aborted")
    return contacts


async def get_invoices(access_token: str, xero_tenant_id: str) -> list:
    """
    GET /api.xro/2.0/Invoices — returns AR invoices (Type==ACCREC).
    """
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{XERO_API_BASE}/Invoices",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Xero-Tenant-Id": xero_tenant_id,
                    "Accept": "application/json",
                },
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    raw = await _circuit.call(_retry, _call)
    invoices = raw.get("Invoices", [])
    if not isinstance(invoices, list):
        raise ValueError("Xero returned unexpected Invoices shape — sync aborted")
    return invoices


async def get_bills(access_token: str, xero_tenant_id: str) -> list:
    """
    GET /api.xro/2.0/Invoices?where=Type=="ACCPAY" — returns AP bills.
    """
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{XERO_API_BASE}/Invoices",
                params={"where": 'Type=="ACCPAY"'},
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Xero-Tenant-Id": xero_tenant_id,
                    "Accept": "application/json",
                },
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    raw = await _circuit.call(_retry, _call)
    bills = raw.get("Invoices", [])
    if not isinstance(bills, list):
        raise ValueError("Xero returned unexpected Bills shape — sync aborted")
    return bills


async def get_payments(access_token: str, xero_tenant_id: str) -> list:
    """
    GET /api.xro/2.0/Payments — returns all payments.
    """
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{XERO_API_BASE}/Payments",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Xero-Tenant-Id": xero_tenant_id,
                    "Accept": "application/json",
                },
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    raw = await _circuit.call(_retry, _call)
    payments = raw.get("Payments", [])
    if not isinstance(payments, list):
        raise ValueError("Xero returned unexpected Payments shape — sync aborted")
    return payments


async def get_expenses(access_token: str, xero_tenant_id: str) -> list:
    """
    GET /api.xro/2.0/BankTransactions?where=Type=="SPEND" — returns expense transactions.
    """
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{XERO_API_BASE}/BankTransactions",
                params={"where": 'Type=="SPEND"'},
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Xero-Tenant-Id": xero_tenant_id,
                    "Accept": "application/json",
                },
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    raw = await _circuit.call(_retry, _call)
    expenses = raw.get("BankTransactions", [])
    if not isinstance(expenses, list):
        raise ValueError("Xero returned unexpected BankTransactions shape — sync aborted")
    return expenses


async def get_credit_notes(access_token: str, xero_tenant_id: str) -> list:
    """
    GET /api.xro/2.0/CreditNotes — returns all credit notes.
    """
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{XERO_API_BASE}/CreditNotes",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Xero-Tenant-Id": xero_tenant_id,
                    "Accept": "application/json",
                },
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    raw = await _circuit.call(_retry, _call)
    credit_notes = raw.get("CreditNotes", [])
    if not isinstance(credit_notes, list):
        raise ValueError("Xero returned unexpected CreditNotes shape — sync aborted")
    return credit_notes


async def get_tax_rates(access_token: str, xero_tenant_id: str) -> list:
    """
    GET /api.xro/2.0/TaxRates — returns all tax rates.
    """
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{XERO_API_BASE}/TaxRates",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Xero-Tenant-Id": xero_tenant_id,
                    "Accept": "application/json",
                },
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    raw = await _circuit.call(_retry, _call)
    tax_rates = raw.get("TaxRates", [])
    if not isinstance(tax_rates, list):
        raise ValueError("Xero returned unexpected TaxRates shape — sync aborted")
    return tax_rates


async def revoke_connection(access_token: str, connection_id: str) -> None:
    """
    DELETE https://api.xero.com/connections/{connection_id}
    Revokes the specific Xero org connection.
    """
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{XERO_CONNECTIONS_URL}/{connection_id}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
                timeout=10.0,
            )
            response.raise_for_status()

    await _circuit.call(_retry, _call)
