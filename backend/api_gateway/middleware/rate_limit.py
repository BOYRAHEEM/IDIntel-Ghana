"""Sliding window rate limiting per institution using Redis."""
import json
import time

import redis.asyncio as aioredis
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ...shared.config import get_settings

settings = get_settings()

TIER_LIMITS = {
    "STARTER":      {"per_minute": 20,   "per_day": 5_000},
    "PROFESSIONAL": {"per_minute": 100,  "per_day": 50_000},
    "ENTERPRISE":   {"per_minute": 500,  "per_day": 200_000},
    "GOVERNMENT":   {"per_minute": 1000, "per_day": None},
}

UNRATED_PATHS = {"/health", "/metrics", "/v1/auth/token"}

_redis_client: aioredis.Redis | None = None


async def _get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = await aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in UNRATED_PATHS:
            return await call_next(request)

        institution = getattr(request.state, "institution", None)
        if institution is None:
            return await call_next(request)

        inst_id = institution["institution_id"]
        tier = institution.get("subscription_tier", "STARTER")
        tier_limits = TIER_LIMITS.get(tier, TIER_LIMITS["STARTER"])

        per_minute = institution.get("rate_limit_per_minute") or tier_limits["per_minute"]
        per_day = institution.get("rate_limit_per_day") or tier_limits["per_day"]

        redis = await _get_redis()

        # Sliding window: 1-minute window
        minute_key = f"rl:min:{inst_id}:{int(time.time()) // 60}"
        minute_count = await redis.incr(minute_key)
        if minute_count == 1:
            await redis.expire(minute_key, 120)  # 2-minute TTL for safety

        if minute_count > per_minute:
            reset_at = (int(time.time()) // 60 + 1) * 60
            return _rate_limit_response(request, per_minute, 0, reset_at, "minute")

        # Daily window
        if per_day is not None:
            day_key = f"rl:day:{inst_id}:{_current_day_key()}"
            day_count = await redis.incr(day_key)
            if day_count == 1:
                await redis.expire(day_key, 90000)  # 25-hour TTL

            if day_count > per_day:
                reset_at = _next_midnight_ts()
                return _rate_limit_response(request, per_day, 0, reset_at, "day")

            remaining_day = max(0, per_day - day_count)
        else:
            remaining_day = -1  # unlimited

        remaining_minute = max(0, per_minute - minute_count)
        reset_at = (int(time.time()) // 60 + 1) * 60

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining_minute)
        response.headers["X-RateLimit-Reset"] = str(reset_at)
        response.headers["X-RateLimit-Window"] = "60"
        if remaining_day >= 0:
            response.headers["X-RateLimit-Daily-Remaining"] = str(remaining_day)
        return response


def _current_day_key() -> str:
    from datetime import date
    return date.today().isoformat()


def _next_midnight_ts() -> int:
    from datetime import date, datetime, timezone
    today = date.today()
    midnight = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)
    from datetime import timedelta
    return int((midnight + timedelta(days=1)).timestamp())


def _rate_limit_response(request: Request, limit: int, remaining: int, reset_at: int, window: str) -> Response:
    retry_after = max(0, reset_at - int(time.time()))
    body = json.dumps({
        "type": "https://api.idintel.com.gh/errors/rate-limit-exceeded",
        "title": "Rate Limit Exceeded",
        "status": 429,
        "detail": f"You have exceeded your per-{window} quota of {limit} requests. Reset in {retry_after} seconds.",
        "retry_after": retry_after,
        "request_id": getattr(request.state, "request_id", "unknown"),
    })
    return Response(
        content=body,
        status_code=429,
        media_type="application/json",
        headers={
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(reset_at),
            "Retry-After": str(retry_after),
        },
    )
