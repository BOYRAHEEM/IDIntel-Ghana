"""SQLAlchemy models for institutions, users, and API keys."""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class InstitutionType(str, enum.Enum):
    BANK = "BANK"
    FINTECH = "FINTECH"
    MICROFINANCE = "MICROFINANCE"
    INSURANCE = "INSURANCE"
    TELECOM = "TELECOM"
    CREDIT_BUREAU = "CREDIT_BUREAU"
    GOVERNMENT = "GOVERNMENT"
    LAW_ENFORCEMENT = "LAW_ENFORCEMENT"
    IMMIGRATION = "IMMIGRATION"
    REGULATORY = "REGULATORY"
    INTERNAL = "INTERNAL"


class InstitutionStatus(str, enum.Enum):
    PENDING_ONBOARDING = "PENDING_ONBOARDING"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    TERMINATED = "TERMINATED"


class UserRole(str, enum.Enum):
    PLATFORM_ADMIN = "PLATFORM_ADMIN"
    INSTITUTION_ADMIN = "INSTITUTION_ADMIN"
    COMPLIANCE_OFFICER = "COMPLIANCE_OFFICER"
    ANALYST = "ANALYST"
    API_SERVICE = "API_SERVICE"
    AUDITOR = "AUDITOR"


class Institution(Base):
    __tablename__ = "institutions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    short_name: Mapped[str] = mapped_column(String(30), nullable=False)
    institution_type: Mapped[InstitutionType] = mapped_column(Enum(InstitutionType), nullable=False)
    status: Mapped[InstitutionStatus] = mapped_column(
        Enum(InstitutionStatus), default=InstitutionStatus.PENDING_ONBOARDING
    )

    # Contact and legal
    legal_registration_number: Mapped[str] = mapped_column(String(50), nullable=False)
    nia_authorization_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    msa_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    dpa_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    dpo_contact_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    emergency_contact_email: Mapped[str] = mapped_column(String(200), nullable=False)
    primary_contact_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Access configuration
    allowed_ip_ranges: Mapped[list] = mapped_column(JSONB, default=list)
    allowed_purpose_codes: Mapped[list] = mapped_column(JSONB, default=list)
    data_scope: Mapped[list] = mapped_column(JSONB, default=list)
    mtls_cert_fingerprint: Mapped[str | None] = mapped_column(String(200), nullable=True)
    mtls_cert_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Rate limits (override defaults)
    rate_limit_per_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rate_limit_per_day: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Tier
    subscription_tier: Mapped[str] = mapped_column(String(20), default="STARTER")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    onboarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    suspension_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    users: Mapped[list["InstitutionUser"]] = relationship(back_populates="institution")
    api_keys: Mapped[list["APIKey"]] = relationship(back_populates="institution")


class InstitutionUser(Base):
    __tablename__ = "institution_users"
    __table_args__ = (
        Index("ix_users_institution_email", "institution_id", "email"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    institution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("institutions.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(200), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)

    # Auth
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    totp_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    webauthn_credentials: Mapped[list] = mapped_column(JSONB, default=list)

    # State
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    password_history_hashes: Mapped[list] = mapped_column(JSONB, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    institution: Mapped["Institution"] = relationship(back_populates="users")


class APIKey(Base):
    """API keys for service-account / machine-to-machine access."""
    __tablename__ = "api_keys"
    __table_args__ = (Index("ix_api_keys_key_prefix", "key_prefix"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("institutions.id"), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    signing_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    scopes: Mapped[list] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_test: Mapped[bool] = mapped_column(Boolean, default=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    institution: Mapped["Institution"] = relationship(back_populates="api_keys")
