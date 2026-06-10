import base64
import hashlib
import hmac
import json

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _derive_key(tenant_id: str) -> bytes:
    settings = get_settings()
    master = settings.integration_master_secret
    if not master:
        # Fall back to global encryption_key in dev — not suitable for production
        master = settings.encryption_key or "dev-fallback-secret-not-for-production"
        logger.warning("INTEGRATION_MASTER_SECRET not set — using fallback. Set in production.")
    derived = hmac.new(master.encode(), tenant_id.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(derived)


def encrypt_credentials(data: dict, tenant_id: str) -> str:
    """Encrypts integration credentials with a tenant-specific key. Never logs plaintext."""
    key = _derive_key(tenant_id)
    f = Fernet(key)
    plaintext = json.dumps(data).encode()
    return f.encrypt(plaintext).decode()


def decrypt_credentials(encrypted: str, tenant_id: str) -> dict:
    """Decrypts credentials. Raises ValueError if key mismatch or tampered data."""
    key = _derive_key(tenant_id)
    f = Fernet(key)
    try:
        plaintext = f.decrypt(encrypted.encode())
        return json.loads(plaintext)
    except (InvalidToken, json.JSONDecodeError) as exc:
        raise ValueError("Credential decryption failed — invalid key or tampered data") from exc
