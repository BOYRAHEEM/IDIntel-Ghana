"""Ed25519 signing for immutable audit records."""
import hashlib
import json
from datetime import datetime, timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


_signing_key: Ed25519PrivateKey | None = None


def _get_signing_key() -> Ed25519PrivateKey:
    """Load or generate the Ed25519 audit signing key."""
    global _signing_key
    if _signing_key is not None:
        return _signing_key

    import os
    from pathlib import Path

    key_path = os.getenv("AUDIT_SIGNING_KEY_PATH", "")
    if key_path and Path(key_path).exists():
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        pem_data = Path(key_path).read_bytes()
        _signing_key = load_pem_private_key(pem_data, password=None)
    else:
        # Generate ephemeral key for development (not persisted — do not use in production)
        _signing_key = Ed25519PrivateKey.generate()

    return _signing_key


def sign_audit_record(record_data: dict) -> str:
    """Return hex-encoded Ed25519 signature over the canonical JSON of record_data."""
    canonical = json.dumps(record_data, sort_keys=True, default=str).encode("utf-8")
    key = _get_signing_key()
    signature_bytes = key.sign(canonical)
    return signature_bytes.hex()


def verify_audit_record(record_data: dict, signature_hex: str) -> bool:
    """Verify a previously signed audit record. Returns False if tampered."""
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        public_key = _get_signing_key().public_key()
        canonical = json.dumps(record_data, sort_keys=True, default=str).encode("utf-8")
        public_key.verify(bytes.fromhex(signature_hex), canonical)
        return True
    except Exception:
        return False
