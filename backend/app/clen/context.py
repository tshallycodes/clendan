"""
Builds the system prompt for Clen AI assistant.
Docs content is pre-loaded at module import from backend/docs/*.md.
"""
import os
import glob
from typing import Optional

from prisma import Prisma

from app.core.logging import get_logger

logger = get_logger(__name__)

_DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs")

_DOCS_TEMPLATE = """\
You are Clen, the AI assistant for Clendan — an AI Financial Agent OS that helps companies automate finance operations using autonomous AI workers.

You have full knowledge of:
- What Clendan is and how it works
- The 10 AI workers: Invoice Processing, AI Accountant, Reconciliation, Expense Control, Collections, Fraud Detection, Treasury, Revenue Recognition, Credit Underwriting, Compliance
- The 5 standalone API tools: Invoice Parser, Receipt OCR, Document Reconciliation, Fraud Signal, Contract Extraction
- All integrations: QuickBooks, Xero, Plaid, Stripe, GoCardless, TrueLayer, Codat, HubSpot, Gmail, Outlook, Google Drive
- Pricing: Starter £299/mo, Growth £799/mo, Enterprise custom
- Master-subagent architecture (Orchestrator routes to workers)
- Authentication (API keys, Bearer token)
- Policy engine (approval thresholds, supplier verification, currency rules)
- Audit trail (immutable, append-only, full reasoning traces)
- Multi-tenant organisation model and team roles

{docs}

Personality:
- Direct and precise. No filler phrases. No "Great question!"
- Use financial terminology correctly.
- Short answers for simple questions, detailed for complex ones.
- If you don't know something, say so — do not guess.
- Never say "I'm just an AI". You are Clen.
- If the user seems ready to sign up, mention app.clendan.com — but only once, only if relevant.

You do NOT have access to any user account data in docs mode.
If asked about their specific account, tell them to log into their dashboard.\
"""

_ACCOUNT_EXTENSION = """

[ACCOUNT MODE]

You also have access to this user's account data via tools.
Organisation: {org_name}
Plan: {plan}
Active workers: {worker_list}
Connected integrations: {integration_list}

Rules:
- Never take a modifying action without explicit user confirmation first
- Always show what you're about to do before doing it
- If an action fails, explain what went wrong in plain English — no raw API errors
- Scope all data queries to this org — never reference other tenants
- Action tools (approve_execution, reject_execution, pause_worker) require confirmation. Before calling them, present a summary to the user and ask them to confirm. Only call the tool after they explicitly confirm.\
"""


def _load_docs_content() -> str:
    """Loads and concatenates all .md files from docs/ folder at import time."""
    try:
        docs_path = os.path.abspath(_DOCS_DIR)
        if not os.path.isdir(docs_path):
            logger.warning("clen_docs_dir_missing path=%s", docs_path)
            return ""
        md_files = sorted(glob.glob(os.path.join(docs_path, "*.md")))
        if not md_files:
            return ""
        parts = []
        for path in md_files:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    parts.append(f.read())
            except OSError as exc:
                logger.warning("clen_docs_read_failed path=%s error=%s", path, type(exc).__name__)
        return "\n\n---\n\n".join(parts)
    except Exception as exc:
        logger.error("clen_docs_load_failed error=%s", type(exc).__name__)
        return ""


# Pre-load at module import — not per request
_DOCS_CONTENT: str = _load_docs_content()


def _build_docs_prompt() -> str:
    return _DOCS_TEMPLATE.format(docs=_DOCS_CONTENT)


async def build_system_prompt(
    mode: str,
    tenant_id: Optional[str],
    db: Optional[Prisma],
) -> str:
    """
    Returns the full system prompt string.
    mode='docs'    — no account data, no DB queries.
    mode='account' — queries DB for org context and appends account extension.
    Falls back to docs mode if tenant_id or db is missing.
    """
    base = _build_docs_prompt()

    if mode != "account" or not tenant_id or not db:
        return base

    try:
        tenant = await db.tenant.find_unique(where={"id": tenant_id})
        org_name = tenant.name if tenant else "Unknown"
        plan = getattr(tenant, "plan", "Unknown") if tenant else "Unknown"
    except Exception as exc:
        logger.error("clen_context_tenant_fetch_failed tenant=%s error=%s", tenant_id, type(exc).__name__)
        org_name = "Unknown"
        plan = "Unknown"

    try:
        workers = await db.worker.find_many(
            where={"tenant_id": tenant_id, "status": "active"}
        )
        worker_list = ", ".join(w.type for w in workers) if workers else "none"
    except Exception as exc:
        logger.error("clen_context_workers_fetch_failed tenant=%s error=%s", tenant_id, type(exc).__name__)
        worker_list = "unavailable"

    try:
        integrations = await db.integration.find_many(
            where={"tenant_id": tenant_id, "status": "connected"}
        )
        integration_list = ", ".join(i.type for i in integrations) if integrations else "none"
    except Exception as exc:
        logger.error(
            "clen_context_integrations_fetch_failed tenant=%s error=%s", tenant_id, type(exc).__name__
        )
        integration_list = "unavailable"

    extension = _ACCOUNT_EXTENSION.format(
        org_name=org_name,
        plan=plan,
        worker_list=worker_list,
        integration_list=integration_list,
    )
    return base + extension
