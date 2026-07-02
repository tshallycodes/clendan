"""
Tool CRUD API unit tests.

Route handlers are called directly (bypassing HTTP) with mocked DB and fake
CurrentUser — the same pattern used by test_hardening.py. No live database
or Clerk connection required.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException

from app.core.security import CurrentUser

FAKE_TENANT_ID = "tenant_test_id"
FAKE_CLERK_ID = "user_test_clerk_id"

FAKE_USER = CurrentUser(
    user_id=FAKE_CLERK_ID,
    org_id="org_test",
    tenant_id=FAKE_TENANT_ID,
    email="test@example.com",
    role="owner",
)


def _make_db(
    tool_create=None,
    tool_find_many=None,
    tool_find_first=None,
    tool_update=None,
) -> MagicMock:
    db = MagicMock()
    db.tool.create = AsyncMock(return_value=tool_create)
    db.tool.find_many = AsyncMock(return_value=tool_find_many or [])
    db.tool.find_first = AsyncMock(return_value=tool_find_first)
    db.tool.update = AsyncMock(return_value=tool_update)
    db.tool.delete = AsyncMock(return_value=None)
    return db


def _make_tool(
    tool_id: str = "tool_001",
    wtype: str = "invoice_processing",
    autonomy_level: str = "approve",
    wstatus: str = "active",
    version: int = 1,
    config_json: dict | None = None,
) -> MagicMock:
    w = MagicMock()
    w.id = tool_id
    w.tenant_id = FAKE_TENANT_ID
    w.type = wtype
    w.autonomy_level = autonomy_level
    w.status = wstatus
    w.version = version
    w.config_json = config_json or {}
    return w


# ---------------------------------------------------------------------------
# POST /v1/tools — deploy_tool
# ---------------------------------------------------------------------------

class TestDeployTool:

    @pytest.mark.asyncio
    async def test_creates_tool_with_correct_fields(self):
        from app.api.v1.tools import deploy_tool, DeployToolRequest

        tool = _make_tool()
        db = _make_db(tool_create=tool)

        result = await deploy_tool(
            body=DeployToolRequest(type="invoice_processing", autonomy_level="approve", config={}),
            current_user=FAKE_USER,
            db=db,
        )

        assert result["error"] is None
        data = result["data"]
        assert data["id"] == "tool_001"
        assert data["type"] == "invoice_processing"
        assert data["autonomy_level"] == "approve"
        assert data["status"] == "active"
        assert data["version"] == 1

        db.tool.create.assert_called_once()
        call_data = db.tool.create.call_args[1]["data"]
        assert call_data["tenant"]["connect"]["id"] == FAKE_TENANT_ID
        assert call_data["type"] == "invoice_processing"
        assert call_data["status"] == "active"
        assert call_data["version"] == 1

    def test_rejects_invalid_type(self):
        from app.api.v1.tools import DeployToolRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            DeployToolRequest(type="not_a_real_type")
        assert "type" in str(exc_info.value).lower() or "must be one of" in str(exc_info.value).lower()

    def test_rejects_invalid_autonomy_level(self):
        from app.api.v1.tools import DeployToolRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            DeployToolRequest(type="invoice_processing", autonomy_level="fully_autonomous")
        assert "autonomy_level" in str(exc_info.value).lower() or "must be one of" in str(exc_info.value).lower()

    def test_accepts_all_valid_types(self):
        from app.api.v1.tools import DeployToolRequest

        for wtype in ("invoice_processing", "receipt_processing"):
            req = DeployToolRequest(type=wtype)
            assert req.type == wtype

    def test_accepts_all_valid_autonomy_levels(self):
        from app.api.v1.tools import DeployToolRequest

        for level in ("auto", "approve"):
            req = DeployToolRequest(type="invoice_processing", autonomy_level=level)
            assert req.autonomy_level == level


# ---------------------------------------------------------------------------
# GET /v1/tools — list_tools
# ---------------------------------------------------------------------------

class TestListTools:

    @pytest.mark.asyncio
    async def test_returns_tenant_scoped_list(self):
        from app.api.v1.tools import list_tools

        tools = [
            _make_tool(tool_id="w1", wtype="invoice_processing"),
            _make_tool(tool_id="w2", wtype="receipt_processing"),
        ]
        db = _make_db(tool_find_many=tools)

        result = await list_tools(current_user=FAKE_USER, db=db)

        assert result["error"] is None
        assert len(result["data"]["tools"]) == 2
        assert result["data"]["tools"][0]["id"] == "w1"
        assert result["data"]["tools"][1]["id"] == "w2"

        db.tool.find_many.assert_called_once()
        where_arg = db.tool.find_many.call_args[1]["where"]
        assert where_arg["tenant_id"] == FAKE_TENANT_ID

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_tools(self):
        from app.api.v1.tools import list_tools

        db = _make_db(tool_find_many=[])

        result = await list_tools(current_user=FAKE_USER, db=db)

        assert result["data"]["tools"] == []


# ---------------------------------------------------------------------------
# GET /v1/tools/{tool_id} — get_tool
# ---------------------------------------------------------------------------

class TestGetTool:

    @pytest.mark.asyncio
    async def test_returns_tool_for_correct_tenant(self):
        from app.api.v1.tools import get_tool

        tool = _make_tool()
        db = _make_db(tool_find_first=tool)

        result = await get_tool(tool_id="tool_001", current_user=FAKE_USER, db=db)

        assert result["error"] is None
        assert result["data"]["id"] == "tool_001"
        assert result["data"]["type"] == "invoice_processing"

    @pytest.mark.asyncio
    async def test_returns_404_for_wrong_tenant(self):
        from app.api.v1.tools import get_tool

        db = _make_db(tool_find_first=None)

        with pytest.raises(HTTPException) as exc_info:
            await get_tool(
                tool_id="tool_belongs_to_other_tenant",
                current_user=FAKE_USER,
                db=db,
            )

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_tool(self):
        from app.api.v1.tools import get_tool

        db = _make_db(tool_find_first=None)

        with pytest.raises(HTTPException) as exc_info:
            await get_tool(tool_id="does_not_exist", current_user=FAKE_USER, db=db)

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /v1/tools/{tool_id} — update_tool
# ---------------------------------------------------------------------------

class TestPatchTool:

    @pytest.mark.asyncio
    async def test_bumps_version_on_update(self):
        from app.api.v1.tools import update_tool, PatchToolRequest

        existing = _make_tool(version=3)
        updated = _make_tool(version=4, autonomy_level="auto")
        db = _make_db(tool_find_first=existing, tool_update=updated)

        result = await update_tool(
            tool_id="tool_001",
            body=PatchToolRequest(autonomy_level="auto"),
            current_user=FAKE_USER,
            db=db,
        )

        assert result["data"]["version"] == 4
        assert result["data"]["autonomy_level"] == "auto"

        update_data = db.tool.update.call_args[1]["data"]
        assert update_data["version"] == 4  # existing.version(3) + 1

    def test_rejects_invalid_autonomy_level(self):
        from app.api.v1.tools import PatchToolRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            PatchToolRequest(autonomy_level="fully_autonomous")

    def test_rejects_invalid_status(self):
        from app.api.v1.tools import PatchToolRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            PatchToolRequest(status="broken")

    @pytest.mark.asyncio
    async def test_returns_404_for_wrong_tenant(self):
        from app.api.v1.tools import update_tool, PatchToolRequest

        db = _make_db(tool_find_first=None)

        with pytest.raises(HTTPException) as exc_info:
            await update_tool(
                tool_id="other_tenant_tool",
                body=PatchToolRequest(autonomy_level="auto"),
                current_user=FAKE_USER,
                db=db,
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_only_updates_provided_fields(self):
        from app.api.v1.tools import update_tool, PatchToolRequest

        existing = _make_tool(version=1)
        updated = _make_tool(version=2, wstatus="inactive")
        db = _make_db(tool_find_first=existing, tool_update=updated)

        await update_tool(
            tool_id="tool_001",
            body=PatchToolRequest(status="inactive"),
            current_user=FAKE_USER,
            db=db,
        )

        update_data = db.tool.update.call_args[1]["data"]
        assert "status" in update_data
        assert "autonomy_level" not in update_data
        assert "config_json" not in update_data


# ---------------------------------------------------------------------------
# PATCH /v1/tools/{tool_id}/pause — pause_tool (soft deactivation)
# ---------------------------------------------------------------------------

class TestDeactivateTool:

    @pytest.mark.asyncio
    async def test_sets_status_inactive_does_not_delete(self):
        from app.api.v1.tools import pause_tool

        existing = _make_tool(wstatus="active", version=2)
        deactivated = _make_tool(wstatus="inactive", version=3)
        db = _make_db(tool_find_first=existing, tool_update=deactivated)

        result = await pause_tool(tool_id="tool_001", current_user=FAKE_USER, db=db)

        assert result["data"]["status"] == "inactive"

        db.tool.update.assert_called_once()
        update_data = db.tool.update.call_args[1]["data"]
        assert update_data["status"] == "inactive"
        assert update_data["version"] == 3  # bumped from 2

    @pytest.mark.asyncio
    async def test_does_not_call_db_delete(self):
        from app.api.v1.tools import pause_tool

        existing = _make_tool()
        deactivated = _make_tool(wstatus="inactive")
        db = _make_db(tool_find_first=existing, tool_update=deactivated)

        await pause_tool(tool_id="tool_001", current_user=FAKE_USER, db=db)

        db.tool.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_404_for_wrong_tenant(self):
        from app.api.v1.tools import pause_tool

        db = _make_db(tool_find_first=None)

        with pytest.raises(HTTPException) as exc_info:
            await pause_tool(
                tool_id="other_tenant_tool",
                current_user=FAKE_USER,
                db=db,
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_bumps_version_on_deactivation(self):
        from app.api.v1.tools import pause_tool

        existing = _make_tool(version=5)
        deactivated = _make_tool(wstatus="inactive", version=6)
        db = _make_db(tool_find_first=existing, tool_update=deactivated)

        await pause_tool(tool_id="tool_001", current_user=FAKE_USER, db=db)

        update_data = db.tool.update.call_args[1]["data"]
        assert update_data["version"] == 6
