"""
Connected-mailbox email rail. AR collection reminders (and any future outbound mail) go
through ``send_via_mailbox``, which sends from the tenant's own connected Gmail/Outlook so
replies land in the real person's inbox.

Dry-run by default: when ``settings.emails_live`` is False nothing leaves the mailbox - the
call returns a ``{"mode": "dry_run", ...}`` record so the whole flow is visible without ever
emailing a real customer. Flip ``emails_live`` (and connect a mailbox) to actually send.
Mirrors the payout rail (app/core/payouts.py): "live" never silently no-ops - a live send
with no mailbox or no recipient raises rather than quietly doing nothing.
"""
from __future__ import annotations

from app.core.config import get_settings
from app.core.logging import get_logger
from app.integrations.token_manager import get_valid_token

logger = get_logger(__name__)

_MAIL_TYPES = ("gmail", "outlook")


class MailError(Exception):
    """Raised when a live send is requested but cannot be fulfilled."""


async def resolve_mail_integration(db, tenant_id: str, preferred_id: str | None = None):
    """Return a connected Gmail/Outlook integration for the tenant, or None.

    Prefers ``preferred_id`` when it is a valid mailbox for the tenant; otherwise the most
    recently connected mailbox. ``connected_at`` is the "actually connected" signal.
    """
    base = {"tenant_id": tenant_id, "type": {"in": list(_MAIL_TYPES)}}
    if preferred_id:
        intg = await db.integration.find_first(where={**base, "id": preferred_id})
        if intg:
            return intg
    return await db.integration.find_first(
        where={**base, "connected_at": {"not": None}},
        order={"connected_at": "desc"},
    )


async def send_via_mailbox(
    db,
    tenant_id: str,
    *,
    to: str,
    subject: str,
    body: str,
    reply_to: str | None = None,
    integration=None,
    preferred_integration_id: str | None = None,
) -> dict:
    """Send one plain-text email from the tenant's connected mailbox.

    Returns ``{"mode": "dry_run"|"live", "channel": <type|"none">, "to":..., "message_id":...}``.
    In dry-run nothing is sent. In live mode a missing mailbox or missing recipient raises
    ``MailError`` - a live send never silently no-ops.
    """
    settings = get_settings()
    to = (to or "").strip()

    if not settings.emails_live:
        intg = integration or await resolve_mail_integration(db, tenant_id, preferred_integration_id)
        return {"mode": "dry_run", "channel": intg.type if intg else "none", "to": to, "message_id": ""}

    if not to:
        raise MailError("Cannot send a live reminder: no recipient email address.")
    intg = integration or await resolve_mail_integration(db, tenant_id, preferred_integration_id)
    if intg is None:
        raise MailError("Live email is enabled but no Gmail/Outlook mailbox is connected.")

    token = await get_valid_token(intg.id, db)
    if intg.type == "gmail":
        from app.integrations.google.client import send_gmail_message
        res = await send_gmail_message(token, to=to, subject=subject, body_text=body, reply_to=reply_to)
    elif intg.type == "outlook":
        from app.integrations.outlook.client import send_outlook_message
        res = await send_outlook_message(token, to=to, subject=subject, body_text=body, reply_to=reply_to)
    else:
        raise MailError(f"Unsupported mail integration type: {intg.type!r}")

    # Never log the recipient address (PII) - channel + tenant only.
    logger.info("mail_sent", extra={"tenant_id": tenant_id, "channel": intg.type})
    return {"mode": "live", "channel": intg.type, "to": to, "message_id": res.get("message_id", "")}
