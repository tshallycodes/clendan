"""Firm / portfolio layer tests (app.core.security firm resolution + app.api.v1.firms).

Proves the multi-tenant guarantees of the firm layer with a mocked Prisma client (no DB):
  1. A firm member can list only their own firm's client tenants (with health).
  2. A firm member can act-as only their own firm's client tenants (cross-firm -> 403).
  3. A non-member / non-firm user is denied any act-as (403).
  4. A non-firm user is unaffected: with no client selector they keep their own tenant.

Cross-firm leakage is a critical security failure, so every deny path is asserted explicitly.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.core.security import (
    CurrentUser,
    authorise_client_access,
    get_member_firm_ids,
    resolve_active_context,
)
import app.api.v1.firms as firms


# ---- fixtures / builders ----------------------------------------------------

def _cu(user_id="u_firm", tenant_id="own_tenant", role="admin") -> CurrentUser:
    return CurrentUser(
        user_id=user_id,
        org_id="org_1",
        tenant_id=tenant_id,
        email="operator@firm.com",
        role=role,
    )


def _membership(firm_id: str) -> MagicMock:
    m = MagicMock()
    m.firm_id = firm_id
    return m


def _tenant(tid: str, firm_id: str | None, name: str = "Client Co") -> MagicMock:
    t = MagicMock()
    t.id = tid
    t.firm_id = firm_id
    t.name = name
    return t


def _db(
    *,
    member=MagicMock(id="m_1"),
    memberships=None,
    tenant=None,
    tenants=None,
    pending=0,
    connected=0,
) -> MagicMock:
    db = MagicMock()
    db.member.find_unique = AsyncMock(return_value=member)
    db.firmmembership.find_many = AsyncMock(return_value=memberships or [])
    db.tenant.find_unique = AsyncMock(return_value=tenant)
    db.tenant.find_many = AsyncMock(return_value=tenants or [])
    db.approval.count = AsyncMock(return_value=pending)
    db.integration.count = AsyncMock(return_value=connected)
    return db


# ---- get_member_firm_ids ----------------------------------------------------

@pytest.mark.asyncio
async def test_member_firm_ids_resolved_from_memberships():
    db = _db(memberships=[_membership("firm_A"), _membership("firm_B")])
    ids = await get_member_firm_ids(db, "u_firm")
    assert ids == ["firm_A", "firm_B"]
    # Both the internal Member.id and the raw clerk_user_id are candidate member_ids.
    where = db.firmmembership.find_many.await_args.kwargs["where"]
    assert set(where["member_id"]["in"]) == {"u_firm", "m_1"}


@pytest.mark.asyncio
async def test_member_firm_ids_empty_for_non_firm_user():
    db = _db(member=None, memberships=[])
    assert await get_member_firm_ids(db, "u_solo") == []


# ---- authorise_client_access (the single act-as gate) -----------------------

@pytest.mark.asyncio
async def test_authorise_allows_own_firm_client():
    db = _db(
        memberships=[_membership("firm_A")],
        tenant=_tenant("client_1", "firm_A"),
    )
    target = await authorise_client_access(db, "u_firm", "client_1")
    assert target.id == "client_1"
    assert target.firm_id == "firm_A"


@pytest.mark.asyncio
async def test_authorise_denies_cross_firm_client():
    # Member is in firm_A but the target tenant belongs to firm_B -> 403, no leakage.
    db = _db(
        memberships=[_membership("firm_A")],
        tenant=_tenant("client_2", "firm_B"),
    )
    with pytest.raises(HTTPException) as exc:
        await authorise_client_access(db, "u_firm", "client_2")
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_authorise_denies_non_firm_user():
    db = _db(member=None, memberships=[], tenant=_tenant("client_1", "firm_A"))
    with pytest.raises(HTTPException) as exc:
        await authorise_client_access(db, "u_solo", "client_1")
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_authorise_denies_tenant_with_no_firm():
    db = _db(memberships=[_membership("firm_A")], tenant=_tenant("orphan", None))
    with pytest.raises(HTTPException) as exc:
        await authorise_client_access(db, "u_firm", "orphan")
    assert exc.value.status_code == 403


# ---- resolve_active_context (the request-scope dependency) ------------------

@pytest.mark.asyncio
async def test_resolve_no_selector_keeps_own_tenant():
    # Backward compat: non-firm flow with no client selector is untouched.
    db = _db(member=None, memberships=[])
    ctx = await resolve_active_context(current_user=_cu(), db=db)
    assert ctx.tenant_id == "own_tenant"
    assert ctx.acting_as is False
    assert ctx.firm_id is None
    db.firmmembership.find_many.assert_not_awaited()  # no firm lookup when no selector


@pytest.mark.asyncio
async def test_resolve_selector_equal_own_tenant_is_noop():
    db = _db(member=None, memberships=[])
    ctx = await resolve_active_context(
        current_user=_cu(tenant_id="own_tenant"), db=db, x_clendan_client="own_tenant"
    )
    assert ctx.tenant_id == "own_tenant"
    assert ctx.acting_as is False


@pytest.mark.asyncio
async def test_resolve_acts_as_own_firm_client():
    db = _db(
        memberships=[_membership("firm_A")],
        tenant=_tenant("client_1", "firm_A", name="Acme Books"),
    )
    ctx = await resolve_active_context(
        current_user=_cu(), db=db, x_clendan_client="client_1"
    )
    assert ctx.acting_as is True
    assert ctx.tenant_id == "client_1"
    assert ctx.firm_id == "firm_A"
    assert ctx.user.user_id == "u_firm"  # caller identity unchanged


@pytest.mark.asyncio
async def test_resolve_query_param_selector_also_works():
    db = _db(memberships=[_membership("firm_A")], tenant=_tenant("client_1", "firm_A"))
    ctx = await resolve_active_context(current_user=_cu(), db=db, client="client_1")
    assert ctx.acting_as is True
    assert ctx.tenant_id == "client_1"


@pytest.mark.asyncio
async def test_resolve_denies_cross_firm_selector():
    db = _db(memberships=[_membership("firm_A")], tenant=_tenant("client_2", "firm_B"))
    with pytest.raises(HTTPException) as exc:
        await resolve_active_context(current_user=_cu(), db=db, x_clendan_client="client_2")
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_resolve_denies_selector_for_non_firm_user():
    db = _db(member=None, memberships=[], tenant=_tenant("client_1", "firm_A"))
    with pytest.raises(HTTPException) as exc:
        await resolve_active_context(current_user=_cu(user_id="u_solo"), db=db, x_clendan_client="client_1")
    assert exc.value.status_code == 403


# ---- GET /firms/clients -----------------------------------------------------

@pytest.mark.asyncio
async def test_list_clients_returns_firm_portfolio_with_health():
    db = _db(
        memberships=[_membership("firm_A")],
        tenants=[_tenant("c1", "firm_A", "Acme"), _tenant("c2", "firm_A", "Beta")],
        pending=3,
        connected=2,
    )
    resp = await firms.list_clients(current_user=_cu(), db=db)
    clients = resp["data"]["clients"]
    assert len(clients) == 2
    assert {c["name"] for c in clients} == {"Acme", "Beta"}
    assert clients[0]["pending_approvals"] == 3
    assert clients[0]["connected_integrations"] == 2
    # Portfolio query is scoped to the caller's own firms only.
    assert db.tenant.find_many.await_args.kwargs["where"]["firm_id"]["in"] == ["firm_A"]


@pytest.mark.asyncio
async def test_list_clients_empty_for_non_firm_user():
    db = _db(member=None, memberships=[])
    resp = await firms.list_clients(current_user=_cu(user_id="u_solo"), db=db)
    assert resp["data"]["clients"] == []
    db.tenant.find_many.assert_not_awaited()  # no firm -> never scan tenants


# ---- POST /firms/clients/{tenant_id}/act-as ---------------------------------

@pytest.mark.asyncio
async def test_act_as_writes_audit_and_returns_context():
    db = _db(
        memberships=[_membership("firm_A")],
        tenant=_tenant("client_1", "firm_A", name="Acme Books"),
    )
    with patch.object(firms, "write_audit_log", new_callable=AsyncMock) as mock_audit:
        resp = await firms.act_as_client(tenant_id="client_1", current_user=_cu(), db=db)

    assert resp["data"]["tenant_id"] == "client_1"
    assert resp["data"]["firm_id"] == "firm_A"
    assert resp["data"]["name"] == "Acme Books"
    mock_audit.assert_awaited_once()
    audit_kwargs = mock_audit.await_args.kwargs
    assert audit_kwargs["tenant_id"] == "client_1"  # audit on the CLIENT tenant's trail
    assert audit_kwargs["action"] == "firm.act_as"


@pytest.mark.asyncio
async def test_act_as_cross_firm_denied_and_not_audited():
    db = _db(memberships=[_membership("firm_A")], tenant=_tenant("client_2", "firm_B"))
    with patch.object(firms, "write_audit_log", new_callable=AsyncMock) as mock_audit:
        with pytest.raises(HTTPException) as exc:
            await firms.act_as_client(tenant_id="client_2", current_user=_cu(), db=db)
    assert exc.value.status_code == 403
    mock_audit.assert_not_awaited()  # denied acts must never touch the audit log
