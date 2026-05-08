"""Utility wrappers for consistent PII encryption across services."""
import re
from dataclasses import dataclass

from ..security import get_identity_encryptor, hash_pii_for_audit


@dataclass
class GhanaCardValidator:
    PATTERN = re.compile(r"^GHA-\d{9}-\d$")

    @classmethod
    def is_valid(cls, value: str) -> bool:
        return bool(cls.PATTERN.match(value.strip().upper()))

    @classmethod
    def normalize(cls, value: str) -> str:
        return value.strip().upper()


@dataclass
class PhoneValidator:
    """Validates Ghana phone numbers (E.164 format +233...)."""
    GHANA_PREFIXES = ("024", "025", "026", "027", "028", "029", "050", "054", "055", "059")

    @classmethod
    def normalize(cls, phone: str) -> str:
        phone = re.sub(r"[^\d+]", "", phone)
        if phone.startswith("0") and len(phone) == 10:
            phone = "+233" + phone[1:]
        elif phone.startswith("233") and len(phone) == 12:
            phone = "+" + phone
        return phone

    @classmethod
    def is_valid_ghana(cls, phone: str) -> bool:
        normalized = cls.normalize(phone)
        return normalized.startswith("+233") and len(normalized) == 13


def encrypt_pii_field(value: str | None) -> str | None:
    if value is None:
        return None
    return get_identity_encryptor().encrypt(value)


def decrypt_pii_field(encrypted: str | None) -> str | None:
    if encrypted is None:
        return None
    return get_identity_encryptor().decrypt(encrypted)


def make_search_hash(value: str) -> str:
    """Deterministic hash for use in database lookups (HMAC-SHA256)."""
    return hash_pii_for_audit(value.strip().upper())
