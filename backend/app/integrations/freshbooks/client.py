"""
FreshBooks API client.
Handles token exchange, refresh, and data fetching for invoices, clients, payments.
"""
import time
from datetime import datetime, UTC

import httpx

from app.core.config import get_settings

_BASE = "https://api.freshbooks.com"
_TOKEN_URL = f"{_BASE}/auth/oauth/token"
_ME_URL = f"{_BASE}/auth/api/v1/users/me"


def _auth_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


async def exchange_code(code: str) -> dict:
    """Exchanges an authorization code for access + refresh tokens. Returns credential dict."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.post(
            _TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": settings.freshbooks_client_id,
                "client_secret": settings.freshbooks_client_secret,
                "redirect_uri": settings.freshbooks_redirect_uri,
                "code": code,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        tokens = resp.json()

    expires_in = int(tokens.get("expires_in") or 43200)
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token", ""),
        "token_expiry_at": datetime.fromtimestamp(time.time() + expires_in, UTC).isoformat(),
    }


async def refresh_token(refresh_token_val: str) -> dict:
    """Refreshes an expired access token. Returns updated credential dict."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.post(
            _TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": settings.freshbooks_client_id,
                "client_secret": settings.freshbooks_client_secret,
                "redirect_uri": settings.freshbooks_redirect_uri,
                "refresh_token": refresh_token_val,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        tokens = resp.json()

    expires_in = int(tokens.get("expires_in") or 43200)
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token", refresh_token_val),
        "token_expiry_at": datetime.fromtimestamp(time.time() + expires_in, UTC).isoformat(),
    }


async def get_me(access_token: str) -> dict:
    """
    Returns the current user's profile including business memberships.
    The account_id on the first active membership is used for subsequent API calls.
    """
    async with httpx.AsyncClient(timeout=15) as http:
        resp = await http.get(_ME_URL, headers=_auth_headers(access_token))
        resp.raise_for_status()
        return resp.json().get("response", {})


def extract_account_id(me: dict) -> str:
    """Extracts the first active business account_id from a /users/me response."""
    memberships = me.get("business_memberships", [])
    if not memberships:
        raise ValueError("No business memberships found in FreshBooks profile")
    return memberships[0]["business"]["account_id"]


async def get_invoices(access_token: str, account_id: str, page: int = 1, per_page: int = 100) -> list[dict]:
    url = f"{_BASE}/accounting/account/{account_id}/invoices/invoices"
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.get(
            url,
            params={"page": page, "per_page": per_page},
            headers=_auth_headers(access_token),
        )
        resp.raise_for_status()
        return resp.json().get("response", {}).get("result", {}).get("invoices", [])


async def get_clients(access_token: str, account_id: str, page: int = 1, per_page: int = 100) -> list[dict]:
    url = f"{_BASE}/accounting/account/{account_id}/users/clients"
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.get(
            url,
            params={"page": page, "per_page": per_page},
            headers=_auth_headers(access_token),
        )
        resp.raise_for_status()
        return resp.json().get("response", {}).get("result", {}).get("clients", [])


async def get_payments(access_token: str, account_id: str, page: int = 1, per_page: int = 100) -> list[dict]:
    url = f"{_BASE}/accounting/account/{account_id}/payments/payments"
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.get(
            url,
            params={"page": page, "per_page": per_page},
            headers=_auth_headers(access_token),
        )
        resp.raise_for_status()
        return resp.json().get("response", {}).get("result", {}).get("payments", [])


async def get_expenses(access_token: str, account_id: str, page: int = 1, per_page: int = 100) -> list[dict]:
    url = f"{_BASE}/accounting/account/{account_id}/expenses/expenses"
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.get(url, params={"page": page, "per_page": per_page}, headers=_auth_headers(access_token))
        resp.raise_for_status()
        return resp.json().get("response", {}).get("result", {}).get("expenses", [])


async def get_staff_id(access_token: str, account_id: str) -> int | None:
    """
    Returns the staffid for the current user on this FreshBooks account.
    Tries /accounting/account/{id}/users/me first (account-scoped user record).
    Falls back to reading the staffid from an existing expense.
    """
    async with httpx.AsyncClient(timeout=15) as http:
        # Strategy 1: account-scoped /users/me returns the current user's staff record
        try:
            resp = await http.get(
                f"{_BASE}/accounting/account/{account_id}/users/me",
                headers=_auth_headers(access_token),
            )
            if resp.is_success:
                result = resp.json().get("response", {}).get("result", {})
                staff = result.get("staff") or result.get("staffs")
                if staff:
                    sid = staff[0].get("id") if isinstance(staff, list) else staff.get("id")
                    if sid:
                        return int(sid)
        except Exception:
            pass

        # Strategy 2: extract staffid from an existing expense (requires user:expenses:read)
        try:
            resp = await http.get(
                f"{_BASE}/accounting/account/{account_id}/expenses/expenses",
                params={"per_page": 1},
                headers=_auth_headers(access_token),
            )
            if resp.is_success:
                expenses = resp.json().get("response", {}).get("result", {}).get("expenses", [])
                if expenses and expenses[0].get("staffid"):
                    return int(expenses[0]["staffid"])
        except Exception:
            pass

    return None


async def get_expense_categories(access_token: str, account_id: str) -> list[dict]:
    """Returns all expense categories for the account. Used to pick a default category_id."""
    url = f"{_BASE}/accounting/account/{account_id}/expenses/categories"
    async with httpx.AsyncClient(timeout=15) as http:
        resp = await http.get(url, headers=_auth_headers(access_token))
        resp.raise_for_status()
        return resp.json().get("response", {}).get("result", {}).get("categories", [])


# ---------------------------------------------------------------------------
# Writes — AP bills (FreshBooks has no journal-entry API)
# ---------------------------------------------------------------------------

async def find_or_create_vendor(access_token: str, account_id: str, vendor_name: str) -> str:
    """Return a FreshBooks bill-vendor id for ``vendor_name``, creating the vendor if absent."""
    url = f"{_BASE}/accounting/account/{account_id}/bills/bill_vendors/bill_vendors"
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.get(url, params={"search[vendor_name]": vendor_name}, headers=_auth_headers(access_token))
        if resp.is_success:
            vendors = resp.json().get("response", {}).get("result", {}).get("bill_vendors", [])
            for v in vendors:
                if (v.get("vendor_name") or "").strip().lower() == vendor_name.strip().lower():
                    return str(v.get("vendorid") or v.get("id"))
        resp = await http.post(url, json={"bill_vendor": {"vendor_name": vendor_name}}, headers=_auth_headers(access_token))
        resp.raise_for_status()
        created = resp.json().get("response", {}).get("result", {}).get("bill_vendor", {})
        vid = created.get("vendorid") or created.get("id")
        if not vid:
            raise ValueError("FreshBooks did not return a vendor id")
        return str(vid)


async def create_bill(
    access_token: str, account_id: str, *,
    vendor_id: str, bill_number: str, amount_minor: int, currency: str,
    issue_date: str | None = None, description: str = "",
) -> dict:
    """Create an AP bill in FreshBooks. Amount is minor units, converted to decimal here.
    Returns {"id": <bill id>}."""
    url = f"{_BASE}/accounting/account/{account_id}/bills/bills"
    line = {
        "amount": {"amount": f"{amount_minor / 100:.2f}", "code": currency or "GBP"},
        "description": description or (bill_number or "Bill"),
    }
    bill_obj: dict = {"vendorid": int(vendor_id), "lines": [line], "currency_code": currency or "GBP"}
    if bill_number:
        bill_obj["bill_number"] = bill_number
    if issue_date:
        bill_obj["issue_date"] = issue_date

    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.post(url, json={"bill": bill_obj}, headers=_auth_headers(access_token))
        resp.raise_for_status()
        result = resp.json().get("response", {}).get("result", {}).get("bill", {})
        bid = result.get("id") or result.get("billid")
        if not bid:
            raise ValueError("FreshBooks did not return a bill id")
        return {"id": str(bid)}
