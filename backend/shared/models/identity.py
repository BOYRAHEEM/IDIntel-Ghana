"""SQLAlchemy models for identity records."""
import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class DocumentStatus(str, enum.Enum):
    VALID = "VALID"
    EXPIRED = "EXPIRED"
    SUSPENDED = "SUSPENDED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


class VerificationStatus(str, enum.Enum):
    VERIFIED = "VERIFIED"
    PARTIAL_MATCH = "PARTIAL_MATCH"
    NOT_FOUND = "NOT_FOUND"
    BLOCKED = "BLOCKED"
    ERROR = "ERROR"


class IdentityRecord(Base):
    """
    Core identity record. All PII fields are stored encrypted.
    Use FieldEncryptor from security.py to read/write PII columns.
    """
    __tablename__ = "identity_records"
    __table_args__ = (
        Index("ix_identity_ghana_card_hash", "ghana_card_hash"),
        Index("ix_identity_passport_hash", "passport_hash"),
        Index("ix_identity_ssnit_hash", "ssnit_hash"),
        {"postgresql_partition_by": None},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    idintel_id: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)

    # Encrypted PII fields (AES-256-GCM, decrypt via FieldEncryptor)
    full_name_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    date_of_birth_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    ghana_card_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    passport_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    ssnit_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    address_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Searchable hashes (for lookup without decryption — non-reversible HMAC)
    ghana_card_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    passport_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ssnit_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phone_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Non-PII metadata
    gender: Mapped[str | None] = mapped_column(String(1), nullable=True)
    nationality: Mapped[str] = mapped_column(String(50), default="Ghanaian")
    region: Mapped[str | None] = mapped_column(String(50), nullable=True)

    ghana_card_status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus), default=DocumentStatus.UNKNOWN
    )
    ghana_card_issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    ghana_card_expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    passport_status: Mapped[DocumentStatus | None] = mapped_column(
        Enum(DocumentStatus), nullable=True
    )

    photo_reference_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    biometric_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Data source tracking
    data_sources: Mapped[list] = mapped_column(JSONB, default=list)
    source_confidence_scores: Mapped[dict] = mapped_column(JSONB, default=dict)
    overall_confidence: Mapped[float] = mapped_column(Float, default=0.0)

    # Verification state
    nia_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    gis_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    ssnit_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # Flags
    is_deceased: Mapped[bool] = mapped_column(Boolean, default=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    block_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    nia_last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    fraud_scores: Mapped[list["FraudScoreRecord"]] = relationship(back_populates="identity")
    audit_events: Mapped[list["AuditEvent"]] = relationship(back_populates="identity")


class FraudScoreRecord(Base):
    """Historical fraud scores for an identity."""
    __tablename__ = "fraud_scores"
    __table_args__ = (Index("ix_fraud_scores_identity_created", "identity_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    identity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity_records.id"), nullable=False)
    institution_id: Mapped[str] = mapped_column(String(50), nullable=False)
    request_id: Mapped[str] = mapped_column(String(50), nullable=False)

    overall_score: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_band: Mapped[str] = mapped_column(String(20), nullable=False)
    contributing_factors: Mapped[dict] = mapped_column(JSONB, default=dict)
    shap_values: Mapped[dict] = mapped_column(JSONB, default=dict)
    watchlist_status: Mapped[str] = mapped_column(String(20), default="CLEAR")
    sanctions_status: Mapped[str] = mapped_column(String(20), default="CLEAR")
    model_version: Mapped[str] = mapped_column(String(20), nullable=False)
    context: Mapped[dict] = mapped_column(JSONB, default=dict)
    purpose_code: Mapped[str] = mapped_column(String(50), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    identity: Mapped["IdentityRecord"] = relationship(back_populates="fraud_scores")


class AuditEvent(Base):
    """
    Immutable audit log. Records must never be updated or deleted.
    Each record is cryptographically signed and chained (hash of previous).
    """
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_institution_created", "institution_id", "created_at"),
        Index("ix_audit_events_subject_hash", "subject_id_hash"),
        Index("ix_audit_events_request_id", "request_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sequence_number: Mapped[int] = mapped_column(Integer, autoincrement=True, unique=True)

    # Who
    institution_id: Mapped[str] = mapped_column(String(50), nullable=False)
    institution_name: Mapped[str] = mapped_column(String(200), nullable=False)
    user_id: Mapped[str] = mapped_column(String(50), nullable=False)
    user_role: Mapped[str] = mapped_column(String(50), nullable=False)
    session_id: Mapped[str] = mapped_column(String(100), nullable=False)
    request_id: Mapped[str] = mapped_column(String(50), nullable=False)

    # What
    endpoint: Mapped[str] = mapped_column(String(200), nullable=False)
    query_type: Mapped[str] = mapped_column(String(50), nullable=False)
    query_params_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    fields_accessed: Mapped[list] = mapped_column(JSONB, default=list)
    purpose_code: Mapped[str] = mapped_column(String(50), nullable=False)
    legal_basis: Mapped[str] = mapped_column(String(200), nullable=False)

    # About whom
    subject_id_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    identity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("identity_records.id"), nullable=True
    )

    # Result
    response_status: Mapped[str] = mapped_column(String(30), nullable=False)
    http_status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Context
    request_ip_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    user_agent_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    data_retention_days: Mapped[int] = mapped_column(Integer, default=90)

    # Cryptographic chain
    record_signature: Mapped[str] = mapped_column(String(200), nullable=False)
    previous_record_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    identity: Mapped["IdentityRecord | None"] = relationship(back_populates="audit_events")
