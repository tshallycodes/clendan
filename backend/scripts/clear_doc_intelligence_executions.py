"""
Clear all document_intelligence executions (and optionally documents) for the tenant.

Usage (from backend/):
    python scripts/clear_doc_intelligence_executions.py
    python scripts/clear_doc_intelligence_executions.py --docs   # also wipe documents
"""
import asyncio
import argparse
import sys

from prisma import Prisma


async def main(also_clear_docs: bool) -> None:
    db = Prisma()
    await db.connect()

    try:
        tenant = await db.tenant.find_first()
        if not tenant:
            print("No tenant found — aborting.")
            sys.exit(1)

        tenant_id = tenant.id
        print(f"Tenant: {tenant.name!r} ({tenant_id})")

        tool = await db.tool.find_first(
            where={"tenant_id": tenant_id, "type": "document_intelligence"}
        )
        if not tool:
            print("No document_intelligence tool found — aborting.")
            sys.exit(1)

        print(f"Tool ID: {tool.id}")

        deleted_executions = await db.execution.delete_many(
            where={"tenant_id": tenant_id, "tool_id": tool.id}
        )
        print(f"Deleted {deleted_executions} execution(s).")

        if also_clear_docs:
            deleted_docs = await db.document.delete_many(
                where={"tenant_id": tenant_id}
            )
            print(f"Deleted {deleted_docs} document(s).")

    finally:
        await db.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--docs", action="store_true", help="Also delete all documents")
    args = parser.parse_args()

    asyncio.run(main(also_clear_docs=args.docs))
