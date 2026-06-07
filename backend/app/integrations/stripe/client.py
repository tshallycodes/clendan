"""Stripe webhook signature verification and event parsing."""
import hashlib
import hmac
import time

STRIPE_WEBHOOK_TOLERANCE_SECONDS = 300  # 5 minutes


def verify_stripe_signature(payload: bytes, sig_header: str, secret: str) -> bool:
    """Verify Stripe webhook signature (stripe-signature header).

    Stripe format: t=timestamp,v1=signature,v1=signature2,...
    Signed payload: HMAC-SHA256(secret, f"{timestamp}.{payload}")
    """
    try:
        parts = dict(item.split("=", 1) for item in sig_header.split(",") if "=" in item)
        timestamp = int(parts.get("t", "0"))
        signatures = [v for k, v in parts.items() if k == "v1"]

        if abs(time.time() - timestamp) > STRIPE_WEBHOOK_TOLERANCE_SECONDS:
            return False  # Too old — replay attack protection

        signed_payload = f"{timestamp}.{payload.decode()}"
        expected = hmac.new(
            secret.encode(), signed_payload.encode(), hashlib.sha256
        ).hexdigest()
        return any(hmac.compare_digest(expected, sig) for sig in signatures)
    except Exception:
        return False


def parse_stripe_event_type(event_type: str) -> str | None:
    """Map Stripe event type to Clendan orchestrator event type."""
    _MAP: dict[str, str] = {
        "invoice.payment_succeeded": "invoice_received",
        "invoice.finalized": "invoice_received",
        "charge.succeeded": "transaction_posted",
        "payment_intent.succeeded": "transaction_posted",
    }
    return _MAP.get(event_type)
