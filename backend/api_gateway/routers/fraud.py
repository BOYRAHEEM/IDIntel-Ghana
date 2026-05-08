"""Fraud detection and risk scoring endpoints."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ...shared.database import get_db

router = APIRouter()


class FraudScoreContext(BaseModel):
    transaction_type: str | None = None
    channel: str | None = None
    device_fingerprint_hash: str | None = None
    ip_address_hash: str | None = None
    location_region: str | None = None
    query_velocity_window_minutes: int = 60


class FraudScoreRequest(BaseModel):
    identity_id: str = Field(..., min_length=5, max_length=50)
    context: FraudScoreContext | None = None
    purpose_code: str = Field(..., min_length=4, max_length=50)
    include_shap_explanation: bool = False


class ContributingFactor(BaseModel):
    factor: str
    weight: float
    value: str
    explanation: str


class FraudScoreDetail(BaseModel):
    overall_score: int = Field(..., ge=0, le=1000)
    score_band: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    score_interpretation: str
    contributing_factors: list[ContributingFactor]
    watchlist_status: Literal["CLEAR", "FLAGGED", "CONFIRMED"]
    sanctions_status: Literal["CLEAR", "MATCH", "POSSIBLE_MATCH"]
    model_version: str
    score_timestamp: str


class FraudScoreResponse(BaseModel):
    request_id: str
    identity_id: str
    fraud_score: FraudScoreDetail
    recommended_action: Literal["PROCEED", "REVIEW", "DECLINE", "ESCALATE"]
    audit_reference: str


class FraudPatternRequest(BaseModel):
    identity_ids: list[str] = Field(..., min_length=2, max_length=50)
    analysis_type: Literal["network_fraud_ring", "velocity_analysis", "cross_institution_pattern"]
    time_window_days: int = Field(default=90, ge=1, le=365)
    purpose_code: str


@router.post("/score", response_model=FraudScoreResponse)
async def get_fraud_score(
    request: Request,
    body: FraudScoreRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate a real-time ML-based fraud risk score for an identity."""
    _require_scope(request, "fraud:read")

    from ...fraud_detection_service.services.fraud_analyzer import FraudAnalyzer

    analyzer = FraudAnalyzer(db)
    score_result = await analyzer.score_identity(
        identity_id=body.identity_id,
        context=body.context.model_dump() if body.context else {},
        purpose_code=body.purpose_code,
        institution=request.state.institution,
        include_shap=body.include_shap_explanation,
    )

    import uuid
    from datetime import datetime, timezone

    recommended_action = _score_to_action(score_result.overall_score)

    return FraudScoreResponse(
        request_id=request.state.request_id,
        identity_id=body.identity_id,
        fraud_score=FraudScoreDetail(
            overall_score=score_result.overall_score,
            score_band=score_result.risk_band,
            score_interpretation=score_result.interpretation,
            contributing_factors=[
                ContributingFactor(**f) for f in score_result.contributing_factors
            ],
            watchlist_status=score_result.watchlist_status,
            sanctions_status=score_result.sanctions_status,
            model_version=score_result.model_version,
            score_timestamp=datetime.now(timezone.utc).isoformat(),
        ),
        recommended_action=recommended_action,
        audit_reference=str(uuid.uuid4()),
    )


@router.post("/analyze-pattern")
async def analyze_fraud_pattern(
    request: Request,
    body: FraudPatternRequest,
    db: AsyncSession = Depends(get_db),
):
    """Detect fraud patterns across multiple related identities."""
    _require_scope(request, "fraud:read")

    # Require at minimum ANALYST role for pattern analysis
    if request.state.user_role not in ("ANALYST", "COMPLIANCE_OFFICER", "INSTITUTION_ADMIN", "PLATFORM_ADMIN"):
        raise HTTPException(403, "Insufficient role for fraud pattern analysis")

    from ...fraud_detection_service.services.fraud_analyzer import FraudAnalyzer

    analyzer = FraudAnalyzer(db)
    pattern_result = await analyzer.analyze_network_pattern(
        identity_ids=body.identity_ids,
        analysis_type=body.analysis_type,
        time_window_days=body.time_window_days,
        institution=request.state.institution,
    )

    return {
        "request_id": request.state.request_id,
        "analysis_type": body.analysis_type,
        "result": pattern_result,
    }


def _require_scope(request: Request, scope: str) -> None:
    scopes = getattr(request.state, "scopes", [])
    if scope not in scopes and "admin" not in scopes:
        raise HTTPException(403, f"Missing required scope: {scope}")


def _score_to_action(score: int) -> str:
    if score <= 200:
        return "PROCEED"
    if score <= 500:
        return "REVIEW"
    if score <= 750:
        return "DECLINE"
    return "ESCALATE"
