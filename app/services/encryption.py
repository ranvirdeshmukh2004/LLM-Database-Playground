"""
Encryption service for API key storage.
Uses Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256).

Keys are encrypted before storage and decrypted only when needed
for provider API calls. Plaintext keys never touch logs or responses.
"""

from __future__ import annotations

import logging

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

logger = logging.getLogger("app.services.encryption")


def _get_fernet() -> Fernet:
    """Get a Fernet instance using the configured encryption key."""
    settings = get_settings()
    if not settings.encryption_key:
        raise RuntimeError("ENCRYPTION_KEY is not configured")
    return Fernet(settings.encryption_key.encode())


def encrypt_api_key(plaintext_key: str) -> str:
    """
    Encrypt an API key for storage.

    Args:
        plaintext_key: The raw API key (e.g., "sk-or-v1-abc123...")

    Returns:
        Base64-encoded encrypted string safe for DB storage.
    """
    f = _get_fernet()
    encrypted = f.encrypt(plaintext_key.encode("utf-8"))
    return encrypted.decode("utf-8")


def decrypt_api_key(encrypted_key: str) -> str:
    """
    Decrypt an API key from storage.

    Args:
        encrypted_key: The Fernet-encrypted string from the database.

    Returns:
        The original plaintext API key.

    Raises:
        ValueError: If decryption fails (wrong key or corrupted data).
    """
    f = _get_fernet()
    try:
        decrypted = f.decrypt(encrypted_key.encode("utf-8"))
        return decrypted.decode("utf-8")
    except InvalidToken:
        logger.error("Failed to decrypt API key — encryption key may have changed")
        raise ValueError("Failed to decrypt API key. The encryption key may have changed.")


def mask_api_key(plaintext_key: str) -> str:
    """
    Create a masked preview of an API key for display.

    Examples:
        "sk-or-v1-abc123xyz789" → "sk-or-...z789"
        "sk-ant-api03-abc"     → "sk-an...3-abc"
        "short"                → "s...t"
    """
    if len(plaintext_key) <= 8:
        return f"{plaintext_key[:1]}...{plaintext_key[-1:]}"

    # Find a natural prefix (e.g., "sk-or-", "sk-ant-")
    prefix_len = min(5, len(plaintext_key) // 3)
    suffix_len = min(4, len(plaintext_key) // 4)

    return f"{plaintext_key[:prefix_len]}...{plaintext_key[-suffix_len:]}"
