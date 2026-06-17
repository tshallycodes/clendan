"""
One-off script: clear all TrueLayer transactions and trigger a full re-sync.

Run on Railway console:
    python scripts/reset_truelayer_transactions.py

This fixes the sign bug where abs() stored all amounts as positive (everything
appeared as an expense). The sync code now negates TrueLayer amounts correctly,
but existing rows need to be cleared so the dedup check doesn't skip them.
"""
import asyncio
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


async def main():
    from prisma import Prisma
    from app.integrations.truelayer.sync import enqueue_truelayer_sync

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

    for intg in integrations:
        account_ids = [a.id for a in (intg.bank_accounts or [])]
        txns_deleted = 0
        if account_ids:
            result = await db.banktransaction.delete_many(
                where={"account_id": {"in": account_ids}}
            )
            txns_deleted = result.count

        await db.integration.update(
            where={"id": intg.id},
            data={"status": "syncing"},
        )
        await enqueue_truelayer_sync(intg.id, intg.tenant_id)
        print(
            f"Integration {intg.id} (tenant={intg.tenant_id}): "
            f"cleared {txns_deleted} transactions, re-sync enqueued."
        )

    await db.disconnect()
    print("Done. Check the transactions page in ~10 seconds after the worker finishes.")


asyncio.run(main())
