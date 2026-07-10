"""
Tests for the VAT filing seam (app/core/vat_filing.py). No network - settings and the
Prisma client are mocked.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _settings(live: bool):
    s = MagicMock()
    s.vat_filing_live = live
    return s


def _db(ret):
    db = MagicMock()
    db.vatreturn.find_first = AsyncMock(return_value=ret)
    db.vatreturn.update = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_dry_run_marks_prepared():
    db = _db(MagicMock(id="vr1", status="draft"))
    with patch("app.core.vat_filing.get_settings", return_value=_settings(False)):
        from app.core.vat_filing import file_vat_return
        res = await file_vat_return(db, "t1", "vr1")
    assert res["mode"] == "dry_run" and res["status"] == "prepared"
    data = db.vatreturn.update.await_args.kwargs["data"]
    assert data["status"] == "prepared" and data["filed_at"] is not None


@pytest.mark.asyncio
async def test_live_without_rail_raises():
    db = _db(MagicMock(id="vr1", status="draft"))
    with patch("app.core.vat_filing.get_settings", return_value=_settings(True)):
        from app.core.vat_filing import file_vat_return, VatFilingError
        with pytest.raises(VatFilingError, match="no e-filing rail"):
            await file_vat_return(db, "t1", "vr1")
    db.vatreturn.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_already_filed_is_noop():
    db = _db(MagicMock(id="vr1", status="filed"))
    with patch("app.core.vat_filing.get_settings", return_value=_settings(False)):
        from app.core.vat_filing import file_vat_return
        res = await file_vat_return(db, "t1", "vr1")
    assert res["mode"] == "noop"
    db.vatreturn.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_return_raises():
    db = _db(None)
    from app.core.vat_filing import file_vat_return, VatFilingError
    with pytest.raises(VatFilingError, match="not found"):
        await file_vat_return(db, "t1", "missing")
