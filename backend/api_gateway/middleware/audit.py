"""Audit middleware: writes an immutable audit record for every request."""
import hashlib
import json
import time
from datetime import datetime, timezone

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ...shared.security import hash_pii_for_audit

AUDIT_EXCLUDED_PATHS = {"/health", "/metrics"}


class AuditMiddleware(BaseHTTPMiddleware):
    """
    Logs every authorized request as an immutable audit record.
    Fires asynchronously after the response is returned to avoid latency impact.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in AUDIT_EXCLUDED_PATHS:
            return await call_next(request)

        start_ms = time.time()
        response = await call_next(request)
        duration_ms = int((time.time() - start_ms) * 1000)

        # Only audit authenticated requests
        institution_id = getattr(request.state, "institution_id", None)
        if institution_id:
            await _write_audit_record(request, response, duration_ms)

        return response


async def _write_audit_record(request: Request, response: Response, duration_ms: int) -> None:
    """Write audit record to database asynchronously."""
    try:
        from ...shared.database import AsyncSessionLocal
        from ...shared.models.identity import AuditEvent
        from .._signing import sign_audit_record

        institution = getattr(request.state, "institution", {})
        client_ip = getattr(request.state, "client_ip", "unknown")
        user_agent = request.headers.get("User-Agent", "")

        # Extract subject hash from response headers (set by routers)
        subject_id_hash = response.headers.pop("X-Audit-Subject-Hash", None)
        identity_id_str = response.headers.pop("X-Audit-Identity-ID", None)

        import uuid

        record_id = uuid.uuid4()
        created_at = datetime.now(timezone.utc)

        # Build record dict for signing
        record_data = {
            "id": str(record_id),
            "timestamp": created_at.isoformat(),
            "institution_id": institution.get("institution_id", "unknown"),
            "user_id": getattr(request.state, "user_id", "unknown"),
            "endpoint": request.url.path,
            "query_type": _extract_query_type(request),
            "response_status": _status_label(response.status_code),
            "http_status_code": response.status_code,
        }
        signature = sign_audit_record(record_data)
        previous_hash = await _get_latest_record_hash()

        async with AsyncSessionLocal() as session:
            audit_event = AuditEvent(
                id=record_id,
                institution_id=institution.get("institution_id", "unknown"),
                institution_name=institution.get("name", "unknown"),
                user_id=getattr(request.state, "user_id", "system"),
                user_role=getattr(request.state, "user_role", "unknown"),
                session_id=getattr(request.state, "token_claims", {}).get("jti", "unknown"),
                request_id=getattr(request.state, "request_id", str(uuid.uuid4())),
                endpoint=request.url.path,
                query_type=_extract_query_type(request),
                query_params_hash=_hash_query_params(request),
                fields_accessed=[],  # Populated by routers via X-Audit-Fields header
                purpose_code=_extract_purpose_code(request),
                legal_basis="institutional_authorization",
                subject_id_hash=subject_id_hash,
                response_status=_status_label(response.status_code),
                http_status_code=response.status_code,
                response_time_ms=duration_ms,
                request_ip_hash=hash_pii_for_audit(client_ip),
                user_agent_hash=hashlib.sha256(user_agent.encode()).hexdigest(),
                record_signature=signature,
                previous_record_hash=previous_hash,
                created_at=created_at,
            )
            session.add(audit_event)
            await session.commit()
    except Exception:
        pass  # Audit must never crash the request


def _extract_query_type(request: Request) -> str:
    path_parts = request.url.path.strip("/").split("/")
    if len(path_parts) >= 3:
        return f"{path_parts[1]}_{path_parts[2]}"
    return request.url.path.strip("/").replace("/", "_")


def _hash_query_params(request: Request) -> str:
    params = dict(request.query_params)
    canonical = json.dumps(params, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _extract_purpose_code(request: Request) -> str:
    return response_headers_or_default(request, "X-Purpose-Code", "UNSPECIFIED")


def _status_label(status_code: int) -> str:
    if status_code == 200:
        return "SUCCESS"
    if status_code == 404:
        return "NOT_FOUND"
    if status_code == 403:
        return "FORBIDDEN"
    if status_code == 429:
        return "RATE_LIMITED"
    if status_code >= 500:
        return "ERROR"
    return str(status_code)


def response_headers_or_default(request: Request, header: str, default: str) -> str:
    return request.headers.get(header, default)


async def _get_latest_record_hash() -> str | None:
    """Fetch hash of the most recent audit record for hash chaining."""
    try:
        from ...shared.database import AsyncSessionLocal
        from ...shared.models.identity import AuditEvent
        from sqlalchemy import select, desc

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(AuditEvent.id)
                .order_by(desc(AuditEvent.sequence_number))
                .limit(1)
            )
            row = result.first()
            if row:
                return hashlib.sha256(str(row[0]).encode()).hexdigest()
    except Exception:
        pass
    return None
