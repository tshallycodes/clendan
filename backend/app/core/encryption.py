import base64
import os
from cryptography.fernet import Fernet, InvalidToken
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _get_fernet() -> Fernet:
    settings = get_settings()
    key = settings.encryption_key
    if not key:
        # Generate a development key - not suitable for production
        key = base64.urlsafe_b64encode(os.urandom(32)).decode()
        logger.warning("ENCRYPTION_KEY not set - using ephemeral dev key. Set in production.")
    # Fernet requires a 32-byte URL-safe base64-encoded key
    if len(key) < 32:
        raise ValueError("ENCRYPTION_KEY must be at least 32 characters")
    # Pad/encode to Fernet format if needed
    padded = key.encode()[:32]
    fernet_key = base64.urlsafe_b64encode(padded)
    return Fernet(fernet_key)


def encrypt(plaintext: str) -> str:
    """Encrypts a string. Returns URL-safe base64 ciphertext."""
    fernet = _get_fernet()
    return fernet.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypts a ciphertext string. Raises ValueError on failure."""
    fernet = _get_fernet()
    try:
        return fernet.decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Decryption failed - invalid or tampered ciphertext") from exc
