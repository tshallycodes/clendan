"""
Clear document_intelligence executions (and optionally documents) for the tenant.

Usage (from backend/):
    python scripts/clear_doc_intelligence_executions.py
    python scripts/clear_doc_intelligence_executions.py --docs   # also wipe documents
    python scripts/clear_doc_intelligence_executions.py --all    # wipe ALL executions
"""
import asyncio
import argparse
import sys

from prisma import Prisma


async def main(also_clear_docs: bool, clear_all: bool) -> None:
    db = Prisma()
    await db.connect()

    try:
        tenant = await db.tenant.find_first()
        if not tenant:
            print("No tenant found — aborting.")
            sys.exit(1)

        tid = tenant.id
        print(f"Tenant: {tenant.name!r} ({tid})")

        # List all tools and their execution counts
        tools = await db.tool.find_many(where={"tenant_id": tid})
        print(f"\nTools ({len(tools)}):")
        for t in tools:
            n = await db.execution.count(where={"tenant_id": tid, "tool_id": t.id})
            print(f"  [{n:>4} executions]  type={t.type}  id={t.id}")

        if clear_all:
            target_ids = [t.id for t in tools]
        else:
            doc_tools = [t for t in tools if "document" in t.type.lower()]
            if not doc_tools:
                print("\nNo document* tool found. Use --all to clear every execution.")
                sys.exit(1)
            target_ids = [t.id for t in doc_tools]
            print(f"\nTargeting: {[t.type for t in doc_tools]}")

        if not target_ids:
            print("Nothing to delete.")
            sys.exit(0)

        # Delete audit logs first (FK constraint)
        executions = await db.execution.find_many(
            where={"tenant_id": tid, "tool_id": {"in": target_ids}}
        )
        exec_ids = [e.id for e in executions]
        print(f"\nFound {len(exec_ids)} execution(s) to delete.")

        if exec_ids:
            audit_deleted = await db.auditlog.delete_many(
                where={"execution_id": {"in": exec_ids}}
            )
            print(f"Deleted {audit_deleted} audit log(s).")

            approval_deleted = await db.approval.delete_many(
                where={"execution_id": {"in": exec_ids}}
            )
            print(f"Deleted {approval_deleted} approval(s).")

            exec_deleted = await db.execution.delete_many(
                where={"id": {"in": exec_ids}}
            )
            print(f"Deleted {exec_deleted} execution(s).")

        if also_clear_docs:
            doc_deleted = await db.document.delete_many(where={"tenant_id": tid})
            print(f"Deleted {doc_deleted} document(s).")

    finally:
        await db.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--docs", action="store_true", help="Also delete all documents")
    parser.add_argument("--all", dest="clear_all", action="store_true", help="Clear ALL tool executions")
    args = parser.parse_args()
    asyncio.run(main(also_clear_docs=args.docs, clear_all=args.clear_all))
