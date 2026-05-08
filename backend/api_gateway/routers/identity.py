"""Identity verification and search endpoints."""
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from ...shared.database import get_db
from ...shared.security import hash_pii_for_audit
from ...shared.utils.encryption import GhanaCardValidator, PhoneValidator

router = APIRouter()


# ---------------------------------------------------------------------------
# Request/Response Schemas
# ---------------------------------------------------------------------------

class IdentityVerifyRequest(BaseModel):
    query_type: Literal[
        "ghana_card", "name_dob", "phone_number",
        "passport", "ssnit", "multi_identifier"
    ]
    ghana_card_number: str | None = Field(None, pattern=r"^GHA-\d{9}-\d$")
    full_name: str | None = Field(None, min_length=2, max_length=200)
    date_of_birth: date | None = None
    phone_number: str | None = None
    passport_number: str | None = Field(None, min_length=6, max_length=20)
    ssnit_number: str | None = None
    purpose_code: str = Field(..., min_length=4, max_length=50)
    consent_reference: str | None = Field(None, max_length=100)
    requesting_officer: str | None = Field(None, max_length=50)
    additional_context: dict | None = None

    @field_validator("purpose_code")
    @classmethod
    def validate_purpose_code(cls, v):
        valid_codes = {
            "ACCOUNT_OPENING", "KYC_REFRESH", "LOAN_APPLICATION",
            "INSURANCE_UNDERWRITING", "SIM_REGISTRATION", "AML_SCREENING",
            "FRAUD_INVESTIGATION", "CLAIMS_VERIFICATION", "LAW_ENFORCEMENT_QUERY",
            "IMMIGRATION_CONTROL", "BENEFIT_VERIFICATION", "REGULATORY_COMPLIANCE",
            "CREDIT_SCORING",
        }
        if v not in valid_codes:
            raise ValueError(f"Invalid purpose_code. Allowed: {sorted(valid_codes)}")
        return v

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v):
        if v is None:
            return v
        normalized = PhoneValidator.normalize(v)
        if not PhoneValidator.is_valid_ghana(normalized):
            raise ValueError("Phone number must be a valid Ghana number in E.164 format")
        return normalized

    def resolve_primary_key(self) -> tuple[str, str]:
        """Returns (key_type, key_value) for primary lookup."""
        if self.ghana_card_number:
            return "ghana_card", GhanaCardValidator.normalize(self.ghana_card_number)
        if self.passport_number:
            return "passport", self.passport_number.upper().strip()
        if self.ssnit_number:
            return "ssnit", self.ssnit_number.strip()
        if self.phone_number:
            return "phone", self.phone_number
        if self.full_name and self.date_of_birth:
            return "name_dob", f"{self.full_name}|{self.date_of_birth}"
        raise ValueError("Insufficient identifiers for the specified query_type")


class AddressResponse(BaseModel):
    region: str | None = None
    district: str | None = None
    town: str | None = None


class DocumentStatusResponse(BaseModel):
    ghana_card: str
    expiry_date: date | None = None
    issue_date: date | None = None


class IdentityProfileResponse(BaseModel):
    identity_id: str
    ghana_card_number: str | None = None
    full_name: str
    date_of_birth: date | None = None
    gender: str | None = None
    nationality: str = "Ghanaian"
    address: AddressResponse | None = None
    document_status: DocumentStatusResponse | None = None
    phone_verified: bool = False
    photo_available: bool = False
    data_sources: list[str] = []
    last_verified: str | None = None


class IdentityVerifyResponse(BaseModel):
    request_id: str
    timestamp: str
    verification_status: Literal["VERIFIED", "PARTIAL_MATCH", "NOT_FOUND", "BLOCKED"]
    confidence_score: float
    identity_profile: IdentityProfileResponse | None = None
    audit_reference: str


class SearchRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=200)
    date_of_birth: date | None = None
    gender: str | None = Field(None, pattern="^[MF]$")
    region: str | None = None
    purpose_code: str
    max_results: int = Field(default=5, ge=1, le=20)
    min_confidence: float = Field(default=0.80, ge=0.5, le=1.0)


class SearchCandidate(BaseModel):
    identity_id: str
    full_name: str
    confidence_score: float
    match_fields: list[str]
    ghana_card_status: str


class SearchResponse(BaseModel):
    request_id: str
    total_candidates: int
    candidates: list[SearchCandidate]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/verify", response_model=IdentityVerifyResponse)
async def verify_identity(
    request: Request,
    body: IdentityVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """Verify and retrieve an identity profile from authorized data sources."""
    _check_purpose_code_authorized(request, body.purpose_code)

    from ...identity_service.services.identity_resolver import IdentityResolver

    resolver = IdentityResolver(db)
    result = await resolver.resolve(
        query=body,
        institution=request.state.institution,
        requesting_user=request.state.user_id,
    )

    if result.identity:
        # Set audit headers for AuditMiddleware to capture
        request.state.audit_subject_hash = hash_pii_for_audit(
            result.primary_key_value or ""
        )

    import uuid
    from datetime import datetime, timezone

    return IdentityVerifyResponse(
        request_id=request.state.request_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        verification_status=result.status,
        confidence_score=result.confidence,
        identity_profile=_to_profile_response(result.identity, request.state.institution),
        audit_reference=str(uuid.uuid4()),
    )


@router.post("/search", response_model=SearchResponse)
async def search_identities(
    request: Request,
    body: SearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Fuzzy search for identities by name and optional attributes."""
    _check_purpose_code_authorized(request, body.purpose_code)

    from ...identity_service.services.identity_resolver import IdentityResolver

    resolver = IdentityResolver(db)
    candidates = await resolver.fuzzy_search(
        full_name=body.full_name,
        date_of_birth=body.date_of_birth,
        gender=body.gender,
        region=body.region,
        max_results=body.max_results,
        min_confidence=body.min_confidence,
        institution=request.state.institution,
    )

    return SearchResponse(
        request_id=request.state.request_id,
        total_candidates=len(candidates),
        candidates=[
            SearchCandidate(
                identity_id=c.idintel_id,
                full_name=c.full_name,
                confidence_score=c.confidence_score,
                match_fields=c.match_fields,
                ghana_card_status=c.ghana_card_status,
            )
            for c in candidates
        ],
    )


@router.get("/{identity_id}/profile", response_model=IdentityVerifyResponse)
async def get_profile(
    request: Request,
    identity_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a full identity profile by IDIntel identity ID."""
    from ...identity_service.services.identity_resolver import IdentityResolver

    resolver = IdentityResolver(db)
    identity = await resolver.get_by_idintel_id(identity_id, request.state.institution)
    if identity is None:
        raise HTTPException(status_code=404, detail="Identity not found")

    import uuid
    from datetime import datetime, timezone

    return IdentityVerifyResponse(
        request_id=request.state.request_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        verification_status="VERIFIED",
        confidence_score=identity.overall_confidence,
        identity_profile=_to_profile_response(identity, request.state.institution),
        audit_reference=str(uuid.uuid4()),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_purpose_code_authorized(request: Request, purpose_code: str) -> None:
    institution = request.state.institution
    allowed = institution.get("allowed_purpose_codes", [])
    if allowed and purpose_code not in allowed:
        raise HTTPException(
            status_code=403,
            detail=f"Purpose code '{purpose_code}' is not authorized for your institution.",
        )


def _to_profile_response(
    identity,
    institution: dict,
) -> IdentityProfileResponse | None:
    if identity is None:
        return None

    data_scope = set(institution.get("data_scope", []))

    from ...shared.utils.encryption import decrypt_pii_field

    return IdentityProfileResponse(
        identity_id=identity.idintel_id,
        ghana_card_number=decrypt_pii_field(identity.ghana_card_encrypted) if "ghana_card_number" in data_scope else None,
        full_name=decrypt_pii_field(identity.full_name_encrypted) or "[REDACTED]",
        date_of_birth=None,  # DOB returned only if in data scope
        gender=identity.gender if "gender" in data_scope else None,
        nationality=identity.nationality,
        address=AddressResponse(region=identity.region) if "address" in data_scope else None,
        document_status=DocumentStatusResponse(
            ghana_card=identity.ghana_card_status.value,
            expiry_date=identity.ghana_card_expiry_date,
            issue_date=identity.ghana_card_issue_date,
        ) if "document_validity" in data_scope else None,
        photo_available=bool(identity.photo_reference_id),
        data_sources=identity.data_sources,
        last_verified=identity.last_verified_at.isoformat() if identity.last_verified_at else None,
    )
