import asyncio
import random
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.integrations.quickbooks.circuit_breaker import CircuitBreaker

logger = get_logger(__name__)

QB_AUTH_URL = "https://appcenter.intuit.com/connect/oauth2"
QB_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
QB_REVOKE_URL = "https://developer.api.intuit.com/v2/oauth2/tokens/revoke"
QB_API_BASE = "https://quickbooks.api.intuit.com/v3/company"
QB_SANDBOX_API_BASE = "https://sandbox-quickbooks.api.intuit.com/v3/company"
QB_SCOPES = "com.intuit.quickbooks.accounting"
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 1.0

_circuit = CircuitBreaker("quickbooks")


def get_api_base(sandbox: bool = True) -> str:
    return QB_SANDBOX_API_BASE if sandbox else QB_API_BASE


def build_auth_url(state: str) -> str:
    settings = get_settings()
    if not settings.quickbooks_client_id:
        raise ValueError("QUICKBOOKS_CLIENT_ID is not configured")
    params = {
        "client_id": settings.quickbooks_client_id,
        "response_type": "code",
        "scope": QB_SCOPES,
        "redirect_uri": settings.quickbooks_redirect_uri,
        "state": state,
    }
    return f"{QB_AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str, realm_id: str) -> dict:
    """Exchanges OAuth authorization code for access + refresh tokens."""
    settings = get_settings()

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                QB_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.quickbooks_redirect_uri,
                },
                auth=(settings.quickbooks_client_id, settings.quickbooks_client_secret),
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _retry(_call)
    return {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "realm_id": realm_id,
        "expires_in": data.get("expires_in", 3600),
        "x_refresh_token_expires_in": data.get("x_refresh_token_expires_in", 8726400),
        "token_type": data.get("token_type", "bearer"),
    }


async def refresh_token(refresh_token_raw: str) -> dict:
    """Refreshes access token using the stored refresh token."""
    settings = get_settings()
    refresh = refresh_token_raw

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                QB_TOKEN_URL,
                data={"grant_type": "refresh_token", "refresh_token": refresh},
                auth=(settings.quickbooks_client_id, settings.quickbooks_client_secret),
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _retry(_call)
    return {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", refresh_token_raw),
        "expires_in": data.get("expires_in", 3600),
    }


async def get_company_info(encrypted_access: str, realm_id: str, sandbox: bool = True) -> dict:
    """Fetches QuickBooks company info. Validates response before returning."""
    access_token = encrypted_access

    async def _call():
        url = f"{get_api_base(sandbox)}/{realm_id}/companyinfo/{realm_id}"
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    raw = await _circuit.call(_retry, _call)
    company = raw.get("CompanyInfo")
    if not company:
        raise ValueError("QuickBooks returned empty CompanyInfo — sync aborted")
    return {
        "company_name": company.get("CompanyName", ""),
        "legal_name": company.get("LegalName", ""),
        "country": company.get("Country", ""),
        "fiscal_year_start": company.get("FiscalYearStartMonth", ""),
    }


async def get_invoice(encrypted_access: str, realm_id: str, invoice_id: str, sandbox: bool = True) -> dict:
    """Fetches a single QB Invoice. Returns normalised dict with minor-unit amounts."""
    access_token = encrypted_access

    async def _call():
        url = f"{get_api_base(sandbox)}/{realm_id}/invoice/{invoice_id}"
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    raw = await _circuit.call(_retry, _call)
    inv = raw.get("Invoice", {})
    if not inv:
        raise ValueError(f"Empty Invoice response for id={invoice_id}")

    currency = (inv.get("CurrencyRef") or {}).get("value", "USD")
    total = float(inv.get("TotalAmt") or 0)
    return {
        "vendor": (inv.get("CustomerRef") or {}).get("name", "unknown"),
        "invoice_number": inv.get("DocNumber", invoice_id),
        "amount_minor": int(round(total * 100)),
        "currency": currency,
        "due_date": inv.get("DueDate"),
    }


async def get_bill(encrypted_access: str, realm_id: str, bill_id: str, sandbox: bool = True) -> dict:
    """Fetches a single QB Bill (supplier invoice). Returns normalised dict."""
    access_token = encrypted_access

    async def _call():
        url = f"{get_api_base(sandbox)}/{realm_id}/bill/{bill_id}"
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    raw = await _circuit.call(_retry, _call)
    bill = raw.get("Bill", {})
    if not bill:
        raise ValueError(f"Empty Bill response for id={bill_id}")

    currency = (bill.get("CurrencyRef") or {}).get("value", "USD")
    total = float(bill.get("TotalAmt") or 0)
    return {
        "vendor": (bill.get("VendorRef") or {}).get("name", "unknown"),
        "invoice_number": bill.get("DocNumber", bill_id),
        "amount_minor": int(round(total * 100)),
        "currency": currency,
        "due_date": bill.get("DueDate"),
    }


async def find_or_create_vendor(encrypted_access: str, realm_id: str, vendor_name: str, sandbox: bool = True) -> str:
    """Returns QB Vendor entity ID, creating the vendor if not found."""
    access_token = encrypted_access

    async def _call():
        async with httpx.AsyncClient() as client:
            safe_name = vendor_name.replace("'", "\\'")
            res = await client.get(
                f"{get_api_base(sandbox)}/{realm_id}/query",
                params={"query": f"SELECT * FROM Vendor WHERE DisplayName = '{safe_name}' MAXRESULTS 1"},
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
                timeout=15.0,
            )
            res.raise_for_status()
            vendors = res.json().get("QueryResponse", {}).get("Vendor", [])
            if vendors:
                return vendors[0]["Id"]

            create = await client.post(
                f"{get_api_base(sandbox)}/{realm_id}/vendor",
                json={"DisplayName": vendor_name},
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                timeout=15.0,
            )
            create.raise_for_status()
            return create.json()["Vendor"]["Id"]

    return await _retry(_call)


async def get_expense_account_id(encrypted_access: str, realm_id: str, sandbox: bool = True) -> str:
    """Returns the ID of the first Expense account in QB. Used as default for bill line items."""
    settings = get_settings()
    if settings.quickbooks_default_account_id:
        return settings.quickbooks_default_account_id

    access_token = encrypted_access

    async def _call():
        async with httpx.AsyncClient() as client:
            res = await client.get(
                f"{get_api_base(sandbox)}/{realm_id}/query",
                params={"query": "SELECT * FROM Account WHERE AccountType = 'Expense' MAXRESULTS 1"},
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
                timeout=15.0,
            )
            res.raise_for_status()
            accounts = res.json().get("QueryResponse", {}).get("Account", [])
            if not accounts:
                raise ValueError("No Expense accounts found in QuickBooks")
            return accounts[0]["Id"]

    return await _retry(_call)


async def create_bill(
    encrypted_access: str,
    realm_id: str,
    vendor_id: str,
    account_id: str,
    invoice_number: str,
    amount_minor: int,
    currency: str,
    due_date: str | None,
    line_items: list[dict],
    sandbox: bool = True,
) -> dict:
    """
    Creates a Bill in QuickBooks from a parsed invoice.
    Idempotent — returns existing bill if DocNumber + VendorRef already exists.
    Amounts are passed in minor units (pence/cents) and converted to decimal here.
    """
    access_token = encrypted_access
    api_base = get_api_base(sandbox)

    async def _check_existing():
        async with httpx.AsyncClient() as client:
            safe_num = invoice_number.replace("'", "\\'")
            res = await client.get(
                f"{api_base}/{realm_id}/query",
                params={"query": f"SELECT * FROM Bill WHERE DocNumber = '{safe_num}' MAXRESULTS 1"},
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
                timeout=15.0,
            )
            res.raise_for_status()
            bills = res.json().get("QueryResponse", {}).get("Bill", [])
            return bills[0] if bills else None

    existing = await _retry(_check_existing)
    if existing:
        return {
            "qb_bill_id": existing["Id"],
            "qb_sync_token": existing["SyncToken"],
            "doc_number": existing.get("DocNumber", invoice_number),
            "total_amount": float(existing.get("TotalAmt", amount_minor / 100)),
            "created": False,
        }

    lines = (
        [
            {
                "Amount": round(item["total_minor"] / 100, 2),
                "DetailType": "AccountBasedExpenseLineDetail",
                "AccountBasedExpenseLineDetail": {"AccountRef": {"value": account_id}},
                "Description": item.get("description", ""),
            }
            for item in line_items
        ]
        if line_items
        else [
            {
                "Amount": round(amount_minor / 100, 2),
                "DetailType": "AccountBasedExpenseLineDetail",
                "AccountBasedExpenseLineDetail": {"AccountRef": {"value": account_id}},
            }
        ]
    )

    payload: dict = {
        "VendorRef": {"value": vendor_id},
        "Line": lines,
        "CurrencyRef": {"value": currency},
        "DocNumber": invoice_number,
    }
    if due_date:
        payload["DueDate"] = due_date

    async def _call():
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{api_base}/{realm_id}/bill",
                json=payload,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                timeout=15.0,
            )
            res.raise_for_status()
            return res.json()

    raw = await _circuit.call(_retry, _call)
    bill = raw.get("Bill", {})
    if not bill:
        raise ValueError("QuickBooks returned empty Bill response after creation")

    return {
        "qb_bill_id": bill["Id"],
        "qb_sync_token": bill["SyncToken"],
        "doc_number": bill.get("DocNumber", invoice_number),
        "total_amount": float(bill.get("TotalAmt", amount_minor / 100)),
        "created": True,
    }


async def _query(access_token: str, realm_id: str, sql: str, sandbox: bool = True) -> list:
    """Runs a QB query and returns the first entity list found in QueryResponse."""
    async def _call():
        url = f"{get_api_base(sandbox)}/{realm_id}/query"
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                params={"query": sql, "minorversion": "65"},
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    raw = await _circuit.call(_retry, _call)
    qr = raw.get("QueryResponse", {})
    # Return the first non-metadata list value
    for key, val in qr.items():
        if isinstance(val, list):
            return val
    return []


async def get_invoices(access_token: str, realm_id: str, sandbox: bool = True) -> list:
    """Fetches all QB Invoices (up to 1000)."""
    return await _query(access_token, realm_id, "SELECT * FROM Invoice MAXRESULTS 1000", sandbox)


async def get_bills(access_token: str, realm_id: str, sandbox: bool = True) -> list:
    """Fetches all QB Bills (up to 1000)."""
    return await _query(access_token, realm_id, "SELECT * FROM Bill MAXRESULTS 1000", sandbox)


async def get_customers(access_token: str, realm_id: str, sandbox: bool = True) -> list:
    """Fetches all QB Customers (up to 1000)."""
    return await _query(access_token, realm_id, "SELECT * FROM Customer MAXRESULTS 1000", sandbox)


async def get_vendors(access_token: str, realm_id: str, sandbox: bool = True) -> list:
    """Fetches all QB Vendors (up to 1000)."""
    return await _query(access_token, realm_id, "SELECT * FROM Vendor MAXRESULTS 1000", sandbox)


async def get_payments(access_token: str, realm_id: str, sandbox: bool = True) -> list:
    """Fetches all QB Payments (up to 1000)."""
    return await _query(access_token, realm_id, "SELECT * FROM Payment MAXRESULTS 1000", sandbox)


async def get_expenses(access_token: str, realm_id: str, sandbox: bool = True) -> list:
    """Fetches all QB Purchases (expenses) (up to 1000)."""
    return await _query(access_token, realm_id, "SELECT * FROM Purchase MAXRESULTS 1000", sandbox)


async def get_accounts(access_token: str, realm_id: str, sandbox: bool = True) -> list:
    """Fetches all QB Accounts (up to 1000)."""
    return await _query(access_token, realm_id, "SELECT * FROM Account MAXRESULTS 1000", sandbox)


async def get_tax_codes(access_token: str, realm_id: str, sandbox: bool = True) -> list:
    """Fetches all QB TaxCodes (up to 1000)."""
    return await _query(access_token, realm_id, "SELECT * FROM TaxCode MAXRESULTS 1000", sandbox)


async def get_credit_memos(access_token: str, realm_id: str, sandbox: bool = True) -> list:
    """Fetches all QB CreditMemos (up to 1000)."""
    return await _query(access_token, realm_id, "SELECT * FROM CreditMemo MAXRESULTS 1000", sandbox)


async def revoke_token(encrypted_token: str) -> None:
    """Revokes a QuickBooks token."""
    settings = get_settings()
    token = encrypted_token

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                QB_REVOKE_URL,
                data={"token": token},
                auth=(settings.quickbooks_client_id, settings.quickbooks_client_secret),
                timeout=10.0,
            )
            response.raise_for_status()

    await _retry(_call)


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
                    "QB call failed (attempt %d/%d), retrying in %.1fs",
                    attempt + 1, MAX_ATTEMPTS, wait,
                )
                await asyncio.sleep(wait)
    raise last_exc
