"""
Xero integration client — re-exports all public symbols from client_auth and client_api.
Import from here in application code: `from app.integrations.xero import client as xero`
"""
from app.integrations.xero.client_auth import (
    build_auth_url,
    exchange_code,
    get_connections,
    refresh_xero_token,
)
from app.integrations.xero.client_api import (
    get_accounts,
    get_contacts,
    revoke_connection,
)

__all__ = [
    "build_auth_url",
    "exchange_code",
    "get_connections",
    "refresh_xero_token",
    "get_accounts",
    "get_contacts",
    "revoke_connection",
]
