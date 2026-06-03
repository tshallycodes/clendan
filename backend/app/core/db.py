from contextlib import asynccontextmanager

from prisma import Prisma

prisma_client = Prisma()


async def connect_db() -> None:
    await prisma_client.connect()


async def disconnect_db() -> None:
    if prisma_client.is_connected():
        await prisma_client.disconnect()


def get_db() -> Prisma:
    return prisma_client


async def get_db_dep() -> Prisma:
    """FastAPI dependency for Prisma client."""
    return prisma_client


@asynccontextmanager
async def tenant_context(tenant_id: str):
    """
    Sets PostgreSQL app.current_tenant_id for RLS enforcement within a transaction.
    Use this wrapping any query that must be tenant-scoped at the DB layer.

    Usage:
        async with tenant_context(tenant_id) as tx:
            results = await tx.invoice.find_many(where={"tenant_id": tenant_id})
    """
    async with prisma_client.tx() as tx:
        await tx.execute_raw(
            "SELECT set_config('app.current_tenant_id', $1, true)", [tenant_id]
        )
        yield tx
