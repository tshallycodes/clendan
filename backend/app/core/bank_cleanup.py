async def cleanup_integration_data(db, integration_id: str) -> dict:
    """
    Deletes all bank transactions and accounts tied to an integration.
    Called before marking an integration as disconnected.
    """
    accounts = await db.bankaccount.find_many(
        where={"integration_id": integration_id}
    )
    account_ids = [a.id for a in accounts]

    txns_deleted = 0
    accounts_deleted = 0

    if account_ids:
        txns_deleted = await db.banktransaction.delete_many(
            where={"account_id": {"in": account_ids}}
        )

        accounts_deleted = await db.bankaccount.delete_many(
            where={"id": {"in": account_ids}}
        )

    return {"transactions_deleted": txns_deleted, "accounts_deleted": accounts_deleted}
