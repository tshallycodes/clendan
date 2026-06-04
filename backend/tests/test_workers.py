"""
Worker CRUD API unit tests.

Route handlers are called directly (bypassing HTTP) with mocked DB and fake
JWT payload — the same pattern used by test_hardening.py. No live database
or Clerk connection required.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException

FAKE_TENANT_ID = "tenant_test_id"
FAKE_CLERK_ID = "user_test_clerk_id"


def _fake_payload() -> dict:
    return {"sub": FAKE_CLERK_ID, "email": "test@example.com"}


def _fake_user() -> MagicMock:
    user = MagicMock()
    user.tenant_id = FAKE_TENANT_ID
    return user


def _make_db(
    worker_create=None,
    worker_find_many=None,
    worker_find_first=None,
    worker_update=None,
) -> MagicMock:
    db = MagicMock()
    db.user.find_unique = AsyncMock(return_value=_fake_user())
    db.worker.create = AsyncMock(return_value=worker_create)
    db.worker.find_many = AsyncMock(return_value=worker_find_many or [])
    db.worker.find_first = AsyncMock(return_value=worker_find_first)
    db.worker.update = AsyncMock(return_value=worker_update)
    db.worker.delete = AsyncMock(return_value=None)
    return db


def _make_worker(
    worker_id: str = "worker_001",
    wtype: str = "invoice_processing",
    autonomy_level: str = "approve",
    wstatus: str = "active",
    version: int = 1,
    config_json: dict | None = None,
) -> MagicMock:
    w = MagicMock()
    w.id = worker_id
    w.tenant_id = FAKE_TENANT_ID
    w.type = wtype
    w.autonomy_level = autonomy_level
    w.status = wstatus
    w.version = version
    w.config_json = config_json or {}
    return w


# ---------------------------------------------------------------------------
# POST /v1/workers — deploy_worker
# ---------------------------------------------------------------------------

class TestDeployWorker:

    @pytest.mark.asyncio
    async def test_creates_worker_with_correct_fields(self):
        from app.api.v1.workers import deploy_worker, DeployWorkerRequest

        worker = _make_worker()
        db = _make_db(worker_create=worker)

        result = await deploy_worker(
            body=DeployWorkerRequest(type="invoice_processing", autonomy_level="approve", config={}),
            payload=_fake_payload(),
            db=db,
        )

        assert result["error"] is None
        data = result["data"]
        assert data["id"] == "worker_001"
        assert data["type"] == "invoice_processing"
        assert data["autonomy_level"] == "approve"
        assert data["status"] == "active"
        assert data["version"] == 1

        db.worker.create.assert_called_once()
        call_data = db.worker.create.call_args[1]["data"]
        assert call_data["tenant_id"] == FAKE_TENANT_ID
        assert call_data["type"] == "invoice_processing"
        assert call_data["status"] == "active"
        assert call_data["version"] == 1

    def test_rejects_invalid_type(self):
        from app.api.v1.workers import DeployWorkerRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            DeployWorkerRequest(type="not_a_real_type")
        assert "type" in str(exc_info.value).lower() or "must be one of" in str(exc_info.value).lower()

    def test_rejects_invalid_autonomy_level(self):
        from app.api.v1.workers import DeployWorkerRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            DeployWorkerRequest(type="invoice_processing", autonomy_level="fully_autonomous")
        assert "autonomy_level" in str(exc_info.value).lower() or "must be one of" in str(exc_info.value).lower()

    def test_accepts_all_valid_types(self):
        from app.api.v1.workers import DeployWorkerRequest

        for wtype in ("invoice_processing", "ai_accountant", "receipt_processing"):
            req = DeployWorkerRequest(type=wtype)
            assert req.type == wtype

    def test_accepts_all_valid_autonomy_levels(self):
        from app.api.v1.workers import DeployWorkerRequest

        for level in ("auto", "approve", "suggest"):
            req = DeployWorkerRequest(type="invoice_processing", autonomy_level=level)
            assert req.autonomy_level == level


# ---------------------------------------------------------------------------
# GET /v1/workers — list_workers
# ---------------------------------------------------------------------------

class TestListWorkers:

    @pytest.mark.asyncio
    async def test_returns_tenant_scoped_list(self):
        from app.api.v1.workers import list_workers

        workers = [
            _make_worker(worker_id="w1", wtype="invoice_processing"),
            _make_worker(worker_id="w2", wtype="ai_accountant"),
        ]
        db = _make_db(worker_find_many=workers)

        result = await list_workers(payload=_fake_payload(), db=db)

        assert result["error"] is None
        assert len(result["data"]["workers"]) == 2
        assert result["data"]["workers"][0]["id"] == "w1"
        assert result["data"]["workers"][1]["id"] == "w2"

        db.worker.find_many.assert_called_once()
        where_arg = db.worker.find_many.call_args[1]["where"]
        assert where_arg["tenant_id"] == FAKE_TENANT_ID

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_workers(self):
        from app.api.v1.workers import list_workers

        db = _make_db(worker_find_many=[])

        result = await list_workers(payload=_fake_payload(), db=db)

        assert result["data"]["workers"] == []


# ---------------------------------------------------------------------------
# GET /v1/workers/{worker_id} — get_worker
# ---------------------------------------------------------------------------

class TestGetWorker:

    @pytest.mark.asyncio
    async def test_returns_worker_for_correct_tenant(self):
        from app.api.v1.workers import get_worker

        worker = _make_worker()
        db = _make_db(worker_find_first=worker)

        result = await get_worker(worker_id="worker_001", payload=_fake_payload(), db=db)

        assert result["error"] is None
        assert result["data"]["id"] == "worker_001"
        assert result["data"]["type"] == "invoice_processing"

    @pytest.mark.asyncio
    async def test_returns_404_for_wrong_tenant(self):
        from app.api.v1.workers import get_worker

        db = _make_db(worker_find_first=None)

        with pytest.raises(HTTPException) as exc_info:
            await get_worker(
                worker_id="worker_belongs_to_other_tenant",
                payload=_fake_payload(),
                db=db,
            )

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_worker(self):
        from app.api.v1.workers import get_worker

        db = _make_db(worker_find_first=None)

        with pytest.raises(HTTPException) as exc_info:
            await get_worker(worker_id="does_not_exist", payload=_fake_payload(), db=db)

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /v1/workers/{worker_id} — update_worker
# ---------------------------------------------------------------------------

class TestPatchWorker:

    @pytest.mark.asyncio
    async def test_bumps_version_on_update(self):
        from app.api.v1.workers import update_worker, PatchWorkerRequest

        existing = _make_worker(version=3)
        updated = _make_worker(version=4, autonomy_level="auto")
        db = _make_db(worker_find_first=existing, worker_update=updated)

        result = await update_worker(
            worker_id="worker_001",
            body=PatchWorkerRequest(autonomy_level="auto"),
            payload=_fake_payload(),
            db=db,
        )

        assert result["data"]["version"] == 4
        assert result["data"]["autonomy_level"] == "auto"

        update_data = db.worker.update.call_args[1]["data"]
        assert update_data["version"] == 4  # existing.version(3) + 1

    def test_rejects_invalid_autonomy_level(self):
        from app.api.v1.workers import PatchWorkerRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            PatchWorkerRequest(autonomy_level="fully_autonomous")

    def test_rejects_invalid_status(self):
        from app.api.v1.workers import PatchWorkerRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            PatchWorkerRequest(status="broken")

    @pytest.mark.asyncio
    async def test_returns_404_for_wrong_tenant(self):
        from app.api.v1.workers import update_worker, PatchWorkerRequest

        db = _make_db(worker_find_first=None)

        with pytest.raises(HTTPException) as exc_info:
            await update_worker(
                worker_id="other_tenant_worker",
                body=PatchWorkerRequest(autonomy_level="auto"),
                payload=_fake_payload(),
                db=db,
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_only_updates_provided_fields(self):
        from app.api.v1.workers import update_worker, PatchWorkerRequest

        existing = _make_worker(version=1)
        updated = _make_worker(version=2, wstatus="inactive")
        db = _make_db(worker_find_first=existing, worker_update=updated)

        await update_worker(
            worker_id="worker_001",
            body=PatchWorkerRequest(status="inactive"),
            payload=_fake_payload(),
            db=db,
        )

        update_data = db.worker.update.call_args[1]["data"]
        assert "status" in update_data
        assert "autonomy_level" not in update_data
        assert "config_json" not in update_data


# ---------------------------------------------------------------------------
# DELETE /v1/workers/{worker_id} — deactivate_worker
# ---------------------------------------------------------------------------

class TestDeactivateWorker:

    @pytest.mark.asyncio
    async def test_sets_status_inactive_does_not_delete(self):
        from app.api.v1.workers import deactivate_worker

        existing = _make_worker(wstatus="active", version=2)
        deactivated = _make_worker(wstatus="inactive", version=3)
        db = _make_db(worker_find_first=existing, worker_update=deactivated)

        result = await deactivate_worker(worker_id="worker_001", payload=_fake_payload(), db=db)

        assert result["data"]["status"] == "inactive"

        db.worker.update.assert_called_once()
        update_data = db.worker.update.call_args[1]["data"]
        assert update_data["status"] == "inactive"
        assert update_data["version"] == 3  # bumped from 2

    @pytest.mark.asyncio
    async def test_does_not_call_db_delete(self):
        from app.api.v1.workers import deactivate_worker

        existing = _make_worker()
        deactivated = _make_worker(wstatus="inactive")
        db = _make_db(worker_find_first=existing, worker_update=deactivated)

        await deactivate_worker(worker_id="worker_001", payload=_fake_payload(), db=db)

        db.worker.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_404_for_wrong_tenant(self):
        from app.api.v1.workers import deactivate_worker

        db = _make_db(worker_find_first=None)

        with pytest.raises(HTTPException) as exc_info:
            await deactivate_worker(
                worker_id="other_tenant_worker",
                payload=_fake_payload(),
                db=db,
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_bumps_version_on_deactivation(self):
        from app.api.v1.workers import deactivate_worker

        existing = _make_worker(version=5)
        deactivated = _make_worker(wstatus="inactive", version=6)
        db = _make_db(worker_find_first=existing, worker_update=deactivated)

        await deactivate_worker(worker_id="worker_001", payload=_fake_payload(), db=db)

        update_data = db.worker.update.call_args[1]["data"]
        assert update_data["version"] == 6
