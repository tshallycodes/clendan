"""
Tests for tenant-specific credential encryption.

Covers:
- Round-trip encrypt/decrypt for the same tenant
- Cross-tenant isolation: decrypting with a different tenant key must fail
- Tamper detection: modified ciphertext must fail decryption
- Empty dict round-trip
- Nested dict round-trip
"""

import os
import pytest

try:
    from app.integrations.encryption import encrypt_credentials, decrypt_credentials
except ImportError as exc:
    pytest.skip(f"encryption module not available: {exc}", allow_module_level=True)


MASTER_SECRET = "test-master-secret-32-characters!!"

TENANT_A = "tenant_aaa"
TENANT_B = "tenant_bbb"


def _patch_master_secret(monkeypatch):
    """Sets the integration master secret via the settings cache."""
    monkeypatch.setenv("INTEGRATION_MASTER_SECRET", MASTER_SECRET)
    # Clear the lru_cache so settings re-reads the env var.
    try:
        from app.core.config import get_settings
        get_settings.cache_clear()
    except Exception:
        pass


def test_round_trip(monkeypatch):
    """encrypt for tenant A, decrypt for tenant A → matches original."""
    _patch_master_secret(monkeypatch)

    data = {"access_token": "tok_123", "refresh_token": "ref_456"}
    encrypted = encrypt_credentials(data, TENANT_A)

    assert isinstance(encrypted, str)
    assert encrypted != str(data)

    decrypted = decrypt_credentials(encrypted, TENANT_A)
    assert decrypted == data


def test_cross_tenant_isolation(monkeypatch):
    """Decrypting tenant A ciphertext with tenant B key must raise ValueError."""
    _patch_master_secret(monkeypatch)

    data = {"access_token": "tok_secret"}
    encrypted = encrypt_credentials(data, TENANT_A)

    with pytest.raises(ValueError, match="decryption failed"):
        decrypt_credentials(encrypted, TENANT_B)


def test_tamper_detection(monkeypatch):
    """Modifying the ciphertext must raise ValueError on decryption."""
    _patch_master_secret(monkeypatch)

    data = {"access_token": "tok_tamper"}
    encrypted = encrypt_credentials(data, TENANT_A)

    # Flip some bytes in the middle of the base64 ciphertext
    mid = len(encrypted) // 2
    tampered = encrypted[:mid] + ("X" if encrypted[mid] != "X" else "Y") + encrypted[mid + 1:]

    with pytest.raises(ValueError, match="decryption failed"):
        decrypt_credentials(tampered, TENANT_A)


def test_empty_dict_round_trip(monkeypatch):
    """Encrypting an empty dict and decrypting must return an empty dict."""
    _patch_master_secret(monkeypatch)

    encrypted = encrypt_credentials({}, TENANT_A)
    decrypted = decrypt_credentials(encrypted, TENANT_A)

    assert decrypted == {}


def test_nested_data_round_trip(monkeypatch):
    """Nested credential structures must survive encrypt/decrypt unchanged."""
    _patch_master_secret(monkeypatch)

    data = {
        "access_token": "abc",
        "nested": {"key": "val", "deep": {"level": 2}},
        "list_field": [1, 2, 3],
    }
    encrypted = encrypt_credentials(data, TENANT_A)
    decrypted = decrypt_credentials(encrypted, TENANT_A)

    assert decrypted == data
