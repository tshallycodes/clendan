"""Per-source scoping helper.

Tools that read accounting/bank data can be scoped to a subset of the tenant's
connected integrations via config (e.g. ``accounting_sources: ["xero"]``). An empty
or unset list means "all connected sources" — no scoping. Every accounting/bank model
carries a ``source`` column holding the integration type (xero, quickbooks, plaid, …).
"""


def source_filter(config_json: dict | None, key: str) -> dict:
    """Return a Prisma where-fragment scoping rows by integration source, or {} for none.

    Merge the result into a query's ``where`` dict:
        where={"tenant_id": tenant_id, **source_filter(cfg, "accounting_sources"), ...}
    """
    if not isinstance(config_json, dict):
        return {}
    sources = config_json.get(key)
    if isinstance(sources, list) and sources:
        return {"source": {"in": [str(s) for s in sources]}}
    return {}
