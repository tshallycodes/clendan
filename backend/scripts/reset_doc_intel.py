"""
One-off script: clear all Document Intelligence data for a fresh start.

Deletes (in FK-safe order):
  - Document records
  - Approval records (linked to doc-intel executions)
  - Invoice records (created by doc-intel processing)
  - Execution records (linked to doc-intel tools)

Does NOT touch AuditLog — those are append-only and stay.

Run from the backend directory:
    cd backend
    python scripts/reset_doc_intel.py
"""
import asyncio
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


async def main():
    from prisma import Prisma

    db = Prisma()
    await db.connect()

    tools = await db.tool.find_many(where={"type": "document_intelligence"})
    if not tools:
        print("No document_intelligence tools found.")
        await db.disconnect()
        return

    tool_ids = [t.id for t in tools]
    tenant_ids = list({t.tenant_id for t in tools})
    print(f"Found {len(tools)} doc-intel tool(s) across {len(tenant_ids)} tenant(s).")

    # 1 — Documents
    docs_deleted = await db.document.delete_many(where={"tool_id": {"in": tool_ids}})
    print(f"  Documents deleted:  {docs_deleted}")

    # 2 — Executions for these tools (collect IDs first for Approval delete)
    executions = await db.execution.find_many(
        where={"tool_id": {"in": tool_ids}},
    )
    execution_ids = [e.id for e in executions]

    # 3 — Approvals referencing those executions
    approvals_deleted = 0
    if execution_ids:
        approvals_deleted = await db.approval.delete_many(
            where={"execution_id": {"in": execution_ids}}
        )
    print(f"  Approvals deleted:  {approvals_deleted}")

    # 4 — Invoices created by doc-intel (no tool_id on Invoice, so delete by tenant)
    invoices_deleted = await db.invoice.delete_many(
        where={"tenant_id": {"in": tenant_ids}}
    )
    print(f"  Invoices deleted:   {invoices_deleted}")

    # 5 — Executions (AuditLog.execution_id is nullable; FK will be set to NULL by DB)
    executions_deleted = 0
    if execution_ids:
        try:
            executions_deleted = await db.execution.delete_many(
                where={"id": {"in": execution_ids}}
            )
            print(f"  Executions deleted: {executions_deleted}")
        except Exception as exc:
            print(f"  Executions: could not delete ({exc})")
            print("  AuditLog rows referencing these executions may be blocking deletion.")
            print("  The rest of the data was cleared — executions and audit logs remain.")

    await db.disconnect()
    print("\nDone. AuditLog rows are preserved (append-only).")


asyncio.run(main())
