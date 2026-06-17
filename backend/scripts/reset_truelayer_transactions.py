"""
One-off script: clear all TrueLayer transactions so the next sync re-fetches them
with the correct sign convention (income negative, expense positive).

Run from the backend directory:
    cd backend
    python scripts/reset_truelayer_transactions.py

After this script completes, go to the Integrations page and click Sync on your
TrueLayer connection to re-fetch transactions with correct signs.
"""
import asyncio
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


async def main():
    from prisma import Prisma

    db = Prisma()
    await db.connect()

    integrations = await db.integration.find_many(
        where={"type": "truelayer", "status": {"not": "disconnected"}},
        include={"bank_accounts": True},
    )

    if not integrations:
        print("No active TrueLayer integrations found.")
        await db.disconnect()
        return

    total_cleared = 0
    for intg in integrations:
        account_ids = [a.id for a in (intg.bank_accounts or [])]
        txns_deleted = 0
        if account_ids:
            txns_deleted = await db.banktransaction.delete_many(
                where={"account_id": {"in": account_ids}}
            )
            total_cleared += txns_deleted

        # Reset to connected so the Sync button is available in the UI
        await db.integration.update(
            where={"id": intg.id},
            data={"status": "connected"},
        )
        print(f"Integration {intg.id}: cleared {txns_deleted} transactions.")

    await db.disconnect()
    print(f"\nDone. {total_cleared} transactions cleared.")
    print("Now go to Integrations and click Sync on your TrueLayer connection.")


asyncio.run(main())
