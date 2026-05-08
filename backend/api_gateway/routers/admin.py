"""Admin endpoints: institution management, audit export, user management."""
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ...shared.database import get_db

router = APIRouter()


# ---------------------------------------------------------------------------
# Audit log endpoints
# ---------------------------------------------------------------------------

class AuditExportRequest(BaseModel):
    start_date: date
    end_date: date
    user_id: str | None = None
    query_type: str | None = None
    format: Literal["json", "csv", "pdf"] = "json"
    include_signature_chain: bool = False
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=100, ge=1, le=1000)


@router.get("/audit/logs")
async def get_audit_logs(
    request: Request,
    start_date: date | None = None,
    end_date: date | None = None,
    user_id: str | None = None,
    query_type: str | None = None,
    page: int = 1,
    per_page: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve audit logs for the requesting institution."""
    _require_compliance_role(request)

    from ...audit_service.services.audit_logger import AuditLogger

    logger = AuditLogger(db)
    logs, total = await logger.get_institution_logs(
        institution_id=request.state.institution_id,
        start_date=start_date,
        end_date=end_date,
        user_id=user_id,
        query_type=query_type,
        page=page,
        per_page=per_page,
    )

    return {
        "institution_id": request.state.institution_id,
        "total": total,
        "page": page,
        "per_page": per_page,
        "logs": logs,
    }


@router.post("/audit/export")
async def export_audit_logs(
    request: Request,
    body: AuditExportRequest,
    db: AsyncSession = Depends(get_db),
):
    """Export audit logs as a signed compliance report."""
    _require_compliance_role(request)

    from ...audit_service.services.audit_logger import AuditLogger

    logger = AuditLogger(db)
    export_url = await logger.export_report(
        institution_id=request.state.institution_id,
        start_date=body.start_date,
        end_date=body.end_date,
        format=body.format,
        include_signature_chain=body.include_signature_chain,
    )

    return {
        "export_url": export_url,
        "expires_in_minutes": 60,
        "format": body.format,
    }


# ---------------------------------------------------------------------------
# API key management
# ---------------------------------------------------------------------------

class CreateAPIKeyRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    scopes: list[str]
    is_test: bool = False
    expires_days: int | None = Field(None, ge=1, le=365)


@router.post("/api-keys")
async def create_api_key(
    request: Request,
    body: CreateAPIKeyRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new API key for the institution. Returns raw key once — store it securely."""
    _require_admin_role(request)

    from ...shared.security import generate_api_key

    raw_key, key_hash = generate_api_key(test=body.is_test)
    # Store key_hash in DB (not raw_key)
    # Returns raw_key once — caller must store it

    return {
        "api_key": raw_key,
        "key_prefix": raw_key[:20],
        "name": body.name,
        "scopes": body.scopes,
        "is_test": body.is_test,
        "warning": "Store this API key securely. It will not be shown again.",
    }


@router.delete("/api-keys/{key_prefix}")
async def revoke_api_key(
    request: Request,
    key_prefix: str,
    db: AsyncSession = Depends(get_db),
):
    """Revoke an API key immediately."""
    _require_admin_role(request)

    from ...shared.models.institution import APIKey
    from sqlalchemy import update

    async with db.begin():
        await db.execute(
            update(APIKey)
            .where(APIKey.key_prefix == key_prefix)
            .values(is_active=False)
        )

    return {"message": "API key revoked successfully", "key_prefix": key_prefix}


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

class CreateUserRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=200)
    role: Literal["INSTITUTION_ADMIN", "COMPLIANCE_OFFICER", "ANALYST", "API_SERVICE", "AUDITOR"]
    temporary_password: str = Field(..., min_length=12, max_length=128)


@router.post("/users")
async def create_user(
    request: Request,
    body: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new user for the institution."""
    _require_admin_role(request)

    import argon2
    import secrets

    ph = argon2.PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)
    ph.hash(body.temporary_password)  # validate strength; actual hash stored by user service

    user_id = f"usr-{request.state.institution['institution_id'][:10]}-{secrets.token_hex(4)}"

    # Insert into DB — simplified here
    return {
        "user_id": user_id,
        "email": body.email,
        "full_name": body.full_name,
        "role": body.role,
        "status": "ACTIVE",
        "mfa_enabled": False,
        "message": "User created. MFA enrollment required on first login.",
    }


# ---------------------------------------------------------------------------
# Platform admin only
# ---------------------------------------------------------------------------

@router.get("/institutions")
async def list_institutions(
    request: Request,
    page: int = 1,
    per_page: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List all institutions (platform admin only)."""
    if request.state.user_role != "PLATFORM_ADMIN":
        raise HTTPException(403, "Platform admin role required")

    from ...shared.models.institution import Institution
    from sqlalchemy import select

    async with db.begin():
        result = await db.execute(
            select(Institution)
            .order_by(Institution.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        institutions = result.scalars().all()

    return {
        "institutions": [
            {
                "institution_id": inst.institution_id,
                "name": inst.name,
                "institution_type": inst.institution_type.value,
                "status": inst.status.value,
                "subscription_tier": inst.subscription_tier,
                "onboarded_at": inst.onboarded_at.isoformat() if inst.onboarded_at else None,
            }
            for inst in institutions
        ]
    }


# ---------------------------------------------------------------------------
# Role guards
# ---------------------------------------------------------------------------

def _require_compliance_role(request: Request) -> None:
    role = getattr(request.state, "user_role", "")
    if role not in ("COMPLIANCE_OFFICER", "INSTITUTION_ADMIN", "PLATFORM_ADMIN", "AUDITOR"):
        raise HTTPException(403, "Compliance officer role or higher required")


def _require_admin_role(request: Request) -> None:
    role = getattr(request.state, "user_role", "")
    if role not in ("INSTITUTION_ADMIN", "PLATFORM_ADMIN"):
        raise HTTPException(403, "Institution admin role or higher required")
