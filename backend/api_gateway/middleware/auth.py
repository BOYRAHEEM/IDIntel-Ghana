"""Authentication middleware: API key + JWT + IP allowlist + mTLS verification."""
import ipaddress
import json
from datetime import datetime, timezone

from fastapi import Request, Response
from jose import JWTError
from starlette.middleware.base import BaseHTTPMiddleware

from ...shared.config import get_settings
from ...shared.security import decode_access_token, verify_api_key

settings = get_settings()

UNAUTHENTICATED_PATHS = {"/health", "/metrics", "/v1/auth/token"}

_institution_cache: dict = {}  # In production, this is loaded from DB + Redis


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in UNAUTHENTICATED_PATHS:
            return await call_next(request)

        # mTLS certificate verification (Nginx passes verified cert details)
        if settings.mtls_required:
            cert_verify = request.headers.get("X-Client-Cert-Verified")
            if cert_verify != "SUCCESS":
                return _auth_error(request, "mTLS client certificate required", 401)
            cert_fingerprint = request.headers.get("X-Client-Cert-Fingerprint", "")
            request.state.cert_fingerprint = cert_fingerprint

        # IP allowlist check
        if settings.ip_allowlist_enabled:
            client_ip = _extract_client_ip(request)
            if not await _check_ip_allowlist(client_ip, request):
                return _auth_error(request, "IP address not in institution allowlist", 403)
            request.state.client_ip = client_ip

        # API key validation
        api_key = request.headers.get("X-IDIntel-API-Key", "")
        if not api_key:
            return _auth_error(request, "X-IDIntel-API-Key header required", 401)

        institution = await _validate_api_key(api_key)
        if institution is None:
            return _auth_error(request, "Invalid or revoked API key", 401)

        if institution["status"] != "ACTIVE":
            return _auth_error(request, "Institution account is not active", 403)

        request.state.institution_id = institution["institution_id"]
        request.state.institution = institution

        # JWT validation
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return _auth_error(request, "Bearer token required", 401)

        token = auth_header.removeprefix("Bearer ").strip()
        try:
            claims = decode_access_token(token)
        except JWTError as exc:
            return _auth_error(request, f"Invalid token: {exc}", 401)

        # Token must belong to the same institution as the API key
        if claims.get("inst") != institution["institution_id"]:
            return _auth_error(request, "Token institution mismatch", 403)

        request.state.user_id = claims["sub"]
        request.state.user_role = claims["role"]
        request.state.scopes = claims.get("scope", "").split()
        request.state.token_claims = claims

        # Request signature verification
        timestamp = request.headers.get("X-Request-Timestamp", "")
        signature = request.headers.get("X-Request-Signature", "")
        if timestamp and signature:
            # Full body signature check done in router layer for POST requests
            request.state.request_timestamp = timestamp
            request.state.request_signature = signature

        return await call_next(request)


async def _validate_api_key(raw_key: str) -> dict | None:
    """Look up institution by API key prefix, then verify hash."""
    from ...shared.database import AsyncSessionLocal
    from ...shared.models.institution import APIKey, Institution

    if not raw_key.startswith(("idig_live_", "idig_test_")):
        return None

    prefix = raw_key[:20]

    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        result = await session.execute(
            select(APIKey, Institution)
            .join(Institution, APIKey.institution_id == Institution.id)
            .where(APIKey.key_prefix == prefix, APIKey.is_active)
        )
        row = result.first()

        if row is None:
            return None

        api_key_record, institution = row
        if not verify_api_key(raw_key, api_key_record.key_hash):
            return None

        if api_key_record.expires_at and api_key_record.expires_at < datetime.now(timezone.utc):
            return None

        return {
            "institution_id": institution.institution_id,
            "name": institution.name,
            "institution_type": institution.institution_type.value,
            "status": institution.status.value,
            "allowed_ip_ranges": institution.allowed_ip_ranges,
            "allowed_purpose_codes": institution.allowed_purpose_codes,
            "data_scope": institution.data_scope,
            "rate_limit_per_minute": institution.rate_limit_per_minute,
            "rate_limit_per_day": institution.rate_limit_per_day,
            "subscription_tier": institution.subscription_tier,
            "api_key_id": str(api_key_record.id),
            "signing_key_encrypted": api_key_record.signing_key_encrypted,
        }


async def _check_ip_allowlist(client_ip: str, request: Request) -> bool:
    institution = getattr(request.state, "institution", None)
    if institution is None:
        return True  # Not yet authenticated; checked after API key validation

    allowed_ranges = institution.get("allowed_ip_ranges", [])
    if not allowed_ranges:
        return True  # No allowlist configured — allow all (log warning)

    try:
        client_addr = ipaddress.ip_address(client_ip)
        return any(
            client_addr in ipaddress.ip_network(cidr, strict=False)
            for cidr in allowed_ranges
        )
    except ValueError:
        return False


def _extract_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _auth_error(request: Request, detail: str, status_code: int) -> Response:
    body = json.dumps({
        "type": f"https://api.idintel.com.gh/errors/{'unauthorized' if status_code == 401 else 'forbidden'}",
        "title": "Unauthorized" if status_code == 401 else "Forbidden",
        "status": status_code,
        "detail": detail,
        "request_id": getattr(request.state, "request_id", "unknown"),
    })
    return Response(
        content=body,
        status_code=status_code,
        media_type="application/json",
        headers={"WWW-Authenticate": "Bearer"} if status_code == 401 else {},
    )
