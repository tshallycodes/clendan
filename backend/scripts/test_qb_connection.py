"""
Local dev script — tests live QuickBooks sandbox connection.
Run from backend/: python scripts/test_qb_connection.py
"""
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings
from app.integrations.quickbooks import client as qb
from app.core.db import get_db


async def main() -> None:
    db = get_db()
    await db.connect()

    try:
        integration = await db.integration.find_first(
            where={"type": "quickbooks", "status": "connected"}
        )
        if not integration:
            print("FAIL: No connected QuickBooks integration in DB")
            return

        print(f"Found integration: {integration.id} (tenant: {integration.tenant_id})")

        creds = json.loads(integration.encrypted_credentials)
        realm_id = creds.get("realm_id", "")
        settings = get_settings()

        print(f"Realm ID: {realm_id}")
        print(f"Sandbox mode: {settings.quickbooks_sandbox}")
        print("Testing company info fetch...")

        company = await qb.get_company_info(
            encrypted_access=creds["access_token"],
            realm_id=realm_id,
            sandbox=settings.quickbooks_sandbox,
        )
        print(f"OK: Company name: {company.get('company_name')}")
        print(f"    Country: {company.get('country')}")
        print(f"    Fiscal year start: {company.get('fiscal_year_start')}")
        print("\nQuickBooks connection is live and tools can fetch data.")

    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}")
    finally:
        await db.disconnect()


asyncio.run(main())
