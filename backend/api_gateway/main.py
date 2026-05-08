"""IDIntel Ghana — API Gateway.

Single entry point for all authorized institution traffic.
Handles authentication, rate limiting, routing, and request auditing.
"""
import time
import uuid
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from ..shared.config import get_settings
from .middleware.audit import AuditMiddleware
from .middleware.auth import AuthMiddleware
from .middleware.rate_limit import RateLimitMiddleware
from .routers import admin, fraud, identity, intelligence

settings = get_settings()


def _strip_pii_from_sentry_event(event, hint):
    """Remove any PII before sending to Sentry."""
    if "request" in event:
        event["request"].pop("data", None)
        event["request"].pop("headers", None)
    return event


if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=0.1,
        before_send=_strip_pii_from_sentry_event,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: verify connectivity to critical dependencies
    from ..shared.database import engine
    async with engine.begin() as conn:
        await conn.execute("SELECT 1")
    yield
    # Shutdown: clean up resources
    await engine.dispose()


app = FastAPI(
    title="IDIntel Ghana API",
    description="Secure identity intelligence platform for authorized Ghanaian institutions.",
    version="1.0.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    openapi_url="/openapi.json" if not settings.is_production else None,
    lifespan=lifespan,
)

# Security headers middleware
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    try:
        del response.headers["Server"]
    except KeyError:
        pass
    return response


# Request ID middleware
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    request.state.start_time = time.time()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# CORS — restricted to registered institution origins only
if settings.allowed_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "X-IDIntel-API-Key", "X-Request-ID", "X-Request-Timestamp", "X-Request-Signature", "Content-Type"],
        expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
        max_age=600,
    )

# Core middleware stack (executed in reverse order)
app.add_middleware(AuditMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthMiddleware)

# Prometheus metrics
if settings.prometheus_enabled:
    Instrumentator(
        should_group_status_codes=False,
        excluded_handlers=["/health", "/metrics"],
    ).instrument(app).expose(app, endpoint="/metrics")

# Routers
app.include_router(identity.router, prefix="/v1/identity", tags=["Identity Verification"])
app.include_router(fraud.router, prefix="/v1/fraud", tags=["Fraud Detection"])
app.include_router(intelligence.router, prefix="/v1/intelligence", tags=["AI Intelligence"])
app.include_router(admin.router, prefix="/v1/admin", tags=["Administration"])


@app.get("/health", include_in_schema=False)
async def health_check():
    return {"status": "healthy", "service": "api-gateway", "version": settings.app_version}


@app.get("/v1/auth/token", include_in_schema=False)
async def _token_redirect():
    """Auth token endpoint is handled by AuthMiddleware directly."""
    return JSONResponse({"detail": "Use POST /v1/auth/token"}, status_code=405)


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        {
            "type": "https://api.idintel.com.gh/errors/not-found",
            "title": "Not Found",
            "status": 404,
            "detail": "The requested endpoint does not exist.",
            "request_id": getattr(request.state, "request_id", "unknown"),
        },
        status_code=404,
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    return JSONResponse(
        {
            "type": "https://api.idintel.com.gh/errors/internal-error",
            "title": "Internal Server Error",
            "status": 500,
            "detail": "An unexpected error occurred. This has been logged.",
            "request_id": getattr(request.state, "request_id", "unknown"),
        },
        status_code=500,
    )
