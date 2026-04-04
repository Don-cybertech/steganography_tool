"""
crypto_utils.py — Optional AES-256 Encryption Layer
=====================================================
Wraps the `cryptography` library's Fernet (AES-128-CBC + HMAC-SHA256)
with a PBKDF2-derived key so a password protects the payload
*before* it is embedded into the image.

Why encrypt before hiding?
  Steganography hides the *existence* of a message.
  Encryption protects its *content*.
  Together they give defence-in-depth.

Usage:
    ciphertext = encrypt(b"secret message", password="hunter2")
    plaintext  = decrypt(ciphertext, password="hunter2")
"""

import os
import base64
import hashlib
from cryptography.fernet import Fernet, InvalidToken


# ── Key derivation ─────────────────────────────────────────────────────────────

_SALT_SIZE = 16
_ITERATIONS = 390_000   # OWASP 2023 recommendation for PBKDF2-SHA256


def _derive_key(password: str, salt: bytes) -> bytes:
    """Derive a 32-byte key from *password* + *salt* via PBKDF2-HMAC-SHA256."""
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        _ITERATIONS,
        dklen=32,
    )
    # Fernet requires a URL-safe base64-encoded 32-byte key
    return base64.urlsafe_b64encode(dk)


# ── Public API ─────────────────────────────────────────────────────────────────

def encrypt(data: bytes, password: str) -> bytes:
    """
    Encrypt *data* with AES-256 (Fernet) using a PBKDF2-derived key.

    Returns:
        salt (16 B) || fernet_token  — a single bytes object safe to embed.
    """
    salt = os.urandom(_SALT_SIZE)
    key = _derive_key(password, salt)
    token = Fernet(key).encrypt(data)
    return salt + token          # prepend salt so decryption can re-derive


def decrypt(payload: bytes, password: str) -> bytes:
    """
    Decrypt a payload produced by :func:`encrypt`.

    Raises:
        ValueError  – wrong password or corrupted payload.
    """
    if len(payload) <= _SALT_SIZE:
        raise ValueError("Payload is too short to be a valid encrypted message.")

    salt = payload[:_SALT_SIZE]
    token = payload[_SALT_SIZE:]
    key = _derive_key(password, salt)

    try:
        return Fernet(key).decrypt(token)
    except InvalidToken:
        raise ValueError("Decryption failed — wrong password or corrupted data.")
