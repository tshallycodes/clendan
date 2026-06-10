"""
tools/__init__.py — re-exports all tool functions so server.py can import
from a single namespace.
"""
from clendan_mcp.tools.invoices import parse_invoice, run_invoice_worker
from clendan_mcp.tools.approvals import (
    get_pending_approvals,
    approve_execution,
    reject_execution,
    get_approval_detail,
)
from clendan_mcp.tools.audit import get_audit_trail, get_execution_detail
from clendan_mcp.tools.workers import (
    list_workers,
    get_worker_status,
    pause_worker,
    resume_worker,
    get_policy_rules,
)
from clendan_mcp.tools.integrations import (
    list_integrations,
    get_integration_status,
    trigger_sync,
)
from clendan_mcp.tools.api_tools import (
    score_fraud,
    reconcile_datasets,
    extract_contract_data,
)
from clendan_mcp.tools.analytics import get_execution_stats, get_hours_saved

__all__ = [
    "parse_invoice",
    "run_invoice_worker",
    "score_fraud",
    "reconcile_datasets",
    "extract_contract_data",
    "get_pending_approvals",
    "approve_execution",
    "reject_execution",
    "get_approval_detail",
    "get_audit_trail",
    "get_execution_detail",
    "list_workers",
    "get_worker_status",
    "pause_worker",
    "resume_worker",
    "get_policy_rules",
    "list_integrations",
    "get_integration_status",
    "trigger_sync",
    "get_execution_stats",
    "get_hours_saved",
]
