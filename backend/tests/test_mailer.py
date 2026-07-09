"""
Tests for the connected-mailbox email rail (app/core/mailer.py).
No network - the Prisma client, settings, token manager and provider send funcs are mocked.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _settings(live: bool):
    s = MagicMock()
    s.emails_live = live
    return s


def _integration(type_="gmail", id_="int1"):
    m = MagicMock()
    m.id = id_
    m.type = type_
    return m


def _db(integration=None):
    db = MagicMock()
    db.integration.find_first = AsyncMock(return_value=integration)
    return db


@pytest.mark.asyncio
async def test_dry_run_sends_nothing_but_reports_channel():
    db = _db(_integration("gmail"))
    with (
        patch("app.core.mailer.get_settings", return_value=_settings(False)),
        patch("app.integrations.google.client.send_gmail_message", AsyncMock()) as send,
    ):
        from app.core.mailer import send_via_mailbox
        res = await send_via_mailbox(db, "t1", to="c@x.com", subject="s", body="b")
    assert res["mode"] == "dry_run"
    assert res["channel"] == "gmail"
    send.assert_not_awaited()  # nothing actually sent in dry-run


@pytest.mark.asyncio
async def test_dry_run_channel_none_when_no_mailbox():
    db = _db(None)
    with patch("app.core.mailer.get_settings", return_value=_settings(False)):
        from app.core.mailer import send_via_mailbox
        res = await send_via_mailbox(db, "t1", to="c@x.com", subject="s", body="b")
    assert res["mode"] == "dry_run"
    assert res["channel"] == "none"


@pytest.mark.asyncio
async def test_live_without_mailbox_raises():
    db = _db(None)
    with patch("app.core.mailer.get_settings", return_value=_settings(True)):
        from app.core.mailer import send_via_mailbox, MailError
        with pytest.raises(MailError, match="no Gmail/Outlook mailbox"):
            await send_via_mailbox(db, "t1", to="c@x.com", subject="s", body="b")


@pytest.mark.asyncio
async def test_live_without_recipient_raises():
    db = _db(_integration("gmail"))
    with patch("app.core.mailer.get_settings", return_value=_settings(True)):
        from app.core.mailer import send_via_mailbox, MailError
        with pytest.raises(MailError, match="no recipient"):
            await send_via_mailbox(db, "t1", to="  ", subject="s", body="b")


@pytest.mark.asyncio
async def test_live_gmail_sends_and_returns_message_id():
    db = _db(_integration("gmail"))
    with (
        patch("app.core.mailer.get_settings", return_value=_settings(True)),
        patch("app.core.mailer.get_valid_token", AsyncMock(return_value="tok")),
        patch("app.integrations.google.client.send_gmail_message",
              AsyncMock(return_value={"message_id": "m1", "thread_id": "th1"})) as send,
    ):
        from app.core.mailer import send_via_mailbox
        res = await send_via_mailbox(db, "t1", to="c@x.com", subject="s", body="b")
    send.assert_awaited_once()
    assert res == {"mode": "live", "channel": "gmail", "to": "c@x.com", "message_id": "m1"}


@pytest.mark.asyncio
async def test_live_outlook_uses_graph_send():
    db = _db(_integration("outlook"))
    with (
        patch("app.core.mailer.get_settings", return_value=_settings(True)),
        patch("app.core.mailer.get_valid_token", AsyncMock(return_value="tok")),
        patch("app.integrations.outlook.client.send_outlook_message",
              AsyncMock(return_value={"message_id": "", "thread_id": ""})) as send,
    ):
        from app.core.mailer import send_via_mailbox
        res = await send_via_mailbox(db, "t1", to="c@x.com", subject="s", body="b")
    send.assert_awaited_once()
    assert res["mode"] == "live"
    assert res["channel"] == "outlook"


@pytest.mark.asyncio
async def test_resolve_prefers_preferred_id():
    preferred = _integration("outlook", "pref")
    db = _db(preferred)
    with patch("app.core.mailer.get_settings", return_value=_settings(False)):
        from app.core.mailer import resolve_mail_integration
        got = await resolve_mail_integration(db, "t1", preferred_id="pref")
    assert got is preferred
    # the where filter must include both the id and the tenant scope
    where = db.integration.find_first.await_args.kwargs["where"]
    assert where["id"] == "pref"
    assert where["tenant_id"] == "t1"
