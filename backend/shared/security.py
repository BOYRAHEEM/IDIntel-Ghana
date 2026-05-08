"""Security utilities: encryption, JWT, API key management, request signing."""
import base64
import hashlib
import hmac
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import boto3
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from jose import JWTError, jwt

from .config import get_settings

settings = get_settings()

_kms_client = None


def _get_kms_client():
    global _kms_client
    if _kms_client is None:
        _kms_client = boto3.client("kms", region_name=settings.aws_region)
    return _kms_client


# ---------------------------------------------------------------------------
# Field-level encryption (AES-256-GCM via AWS KMS data key)
# ---------------------------------------------------------------------------

class FieldEncryptor:
    """Encrypts/decrypts individual PII fields using AWS KMS-derived data keys."""

    def __init__(self, kms_key_id: str):
        self._kms_key_id = kms_key_id
        self._data_key_cache: dict[str, tuple[bytes, float]] = {}
        self._cache_ttl_seconds = 300  # Refresh data key every 5 minutes

    def _get_data_key(self) -> bytes:
        cache_entry = self._data_key_cache.get("current")
        if cache_entry:
            plaintext_key, expires_at = cache_entry
            if time.time() < expires_at:
                return plaintext_key

        response = _get_kms_client().generate_data_key(
            KeyId=self._kms_key_id,
            KeySpec="AES_256",
        )
        plaintext_key: bytes = response["Plaintext"]
        self._data_key_cache["current"] = (plaintext_key, time.time() + self._cache_ttl_seconds)
        return plaintext_key

    def encrypt(self, plaintext: str) -> str:
        """Returns base64-encoded nonce+ciphertext string."""
        if not plaintext:
            return plaintext
        key = self._get_data_key()
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return base64.b64encode(nonce + ciphertext).decode("ascii")

    def decrypt(self, encrypted: str) -> str:
        """Decrypts a base64-encoded nonce+ciphertext string."""
        if not encrypted:
            return encrypted
        key = self._get_data_key()
        aesgcm = AESGCM(key)
        raw = base64.b64decode(encrypted)
        nonce, ciphertext = raw[:12], raw[12:]
        return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")


_identity_encryptor: FieldEncryptor | None = None


def get_identity_encryptor() -> FieldEncryptor:
    global _identity_encryptor
    if _identity_encryptor is None:
        _identity_encryptor = FieldEncryptor(settings.aws_kms_key_id)
    return _identity_encryptor


# ---------------------------------------------------------------------------
# API Key generation and verification
# ---------------------------------------------------------------------------

API_KEY_PREFIX = "idig_live_"
API_KEY_TEST_PREFIX = "idig_test_"


def generate_api_key(test: bool = False) -> tuple[str, str]:
    """Returns (raw_key, argon2_hash). Store only the hash."""
    import argon2

    raw_key = (API_KEY_TEST_PREFIX if test else API_KEY_PREFIX) + secrets.token_urlsafe(32)
    ph = argon2.PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)
    key_hash = ph.hash(raw_key)
    return raw_key, key_hash


def verify_api_key(raw_key: str, stored_hash: str) -> bool:
    import argon2
    import argon2.exceptions

    ph = argon2.PasswordHasher()
    try:
        return ph.verify(stored_hash, raw_key)
    except argon2.exceptions.VerifyMismatchError:
        return False


# ---------------------------------------------------------------------------
# JWT tokens (RS256)
# ---------------------------------------------------------------------------

def _load_private_key() -> str:
    return Path(settings.jwt_private_key_path).read_text()


def _load_public_key() -> str:
    return Path(settings.jwt_public_key_path).read_text()


def create_access_token(
    institution_id: str,
    user_id: str,
    role: str,
    scopes: list[str],
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "inst": institution_id,
        "role": role,
        "scope": " ".join(scopes),
        "iat": now,
        "exp": now + timedelta(seconds=settings.jwt_expiry_seconds),
        "jti": secrets.token_urlsafe(16),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, _load_private_key(), algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Raises JWTError on invalid/expired tokens."""
    return jwt.decode(token, _load_public_key(), algorithms=[settings.jwt_algorithm])


# ---------------------------------------------------------------------------
# Request signing (HMAC-SHA256)
# ---------------------------------------------------------------------------

SIGNATURE_WINDOW_SECONDS = 300  # 5-minute replay prevention window


def sign_request(body: bytes, timestamp: str, signing_key: bytes) -> str:
    """Generate HMAC-SHA256 signature for request body + timestamp."""
    message = f"{timestamp}:".encode() + body
    return hmac.new(signing_key, message, hashlib.sha256).hexdigest()


def verify_request_signature(
    body: bytes,
    timestamp_str: str,
    provided_signature: str,
    signing_key: bytes,
) -> bool:
    try:
        request_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        age = abs((datetime.now(timezone.utc) - request_time).total_seconds())
        if age > SIGNATURE_WINDOW_SECONDS:
            return False  # Replay attack prevention
    except ValueError:
        return False

    expected = sign_request(body, timestamp_str, signing_key)
    return hmac.compare_digest(expected, provided_signature)


# ---------------------------------------------------------------------------
# Secure data hashing (for audit log subject IDs)
# ---------------------------------------------------------------------------

def hash_pii_for_audit(value: str) -> str:
    """One-way hash of PII value for audit log storage (non-reversible)."""
    salt = settings.secret_key[:32].encode()
    return hashlib.sha256(salt + value.encode("utf-8")).hexdigest()
