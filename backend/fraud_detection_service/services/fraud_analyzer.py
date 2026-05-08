"""Fraud analysis service: feature extraction + risk scoring + pattern detection."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...shared.models.identity import AuditEvent, FraudScoreRecord, IdentityRecord
from ..models.feature_extractor import FeatureExtractor
from ..models.risk_scorer import RiskScorer, ScoreResult


class FraudAnalyzer:
    def __init__(self, db: AsyncSession):
        self._db = db
        self._extractor = FeatureExtractor()
        self._scorer = RiskScorer()

    async def score_identity(
        self,
        identity_id: str,
        context: dict,
        purpose_code: str,
        institution: dict,
        include_shap: bool = False,
    ) -> ScoreResult:
        identity = await self._load_identity(identity_id)
        if identity is None:
            return ScoreResult(overall_score=0, risk_band="UNKNOWN", interpretation="Identity not found")

        # Extract features from identity + audit history + context
        velocity_features = await self._extract_velocity_features(identity.id)
        network_features = await self._extract_network_features(identity_id)

        features = self._extractor.extract(
            identity=identity,
            velocity=velocity_features,
            network=network_features,
            context=context,
        )

        # Score using ML model
        result = self._scorer.score(features, include_shap=include_shap)

        # Persist score to history
        await self._persist_score(identity, result, purpose_code, institution, context)

        return result

    async def analyze_network_pattern(
        self,
        identity_ids: list[str],
        analysis_type: str,
        time_window_days: int,
        institution: dict,
    ) -> dict:
        results = {}
        for identity_id in identity_ids:
            score_result = await self.score_identity(
                identity_id=identity_id,
                context={"analysis_type": analysis_type},
                purpose_code="FRAUD_INVESTIGATION",
                institution=institution,
            )
            results[identity_id] = {
                "score": score_result.overall_score,
                "risk_band": score_result.risk_band,
            }

        # Detect if multiple identities form a fraud ring
        high_risk_count = sum(1 for r in results.values() if r["score"] > 500)
        fraud_ring_probability = high_risk_count / max(len(identity_ids), 1)

        return {
            "individual_scores": results,
            "fraud_ring_probability": round(fraud_ring_probability, 2),
            "pattern_detected": fraud_ring_probability > 0.5,
            "analysis_type": analysis_type,
            "identities_analyzed": len(identity_ids),
            "high_risk_count": high_risk_count,
        }

    async def _load_identity(self, identity_id: str) -> IdentityRecord | None:
        result = await self._db.execute(
            select(IdentityRecord).where(IdentityRecord.idintel_id == identity_id)
        )
        return result.scalar_one_or_none()

    async def _extract_velocity_features(self, identity_pk) -> dict:
        now = datetime.now(timezone.utc)

        async def count_queries(window_hours: int) -> int:
            cutoff = now - timedelta(hours=window_hours)
            result = await self._db.execute(
                select(func.count(AuditEvent.id)).where(
                    AuditEvent.identity_id == identity_pk,
                    AuditEvent.created_at >= cutoff,
                )
            )
            return result.scalar() or 0

        count_1h = await count_queries(1)
        count_24h = await count_queries(24)
        count_30d = await count_queries(30 * 24)

        # Unique institutions in 30d
        inst_result = await self._db.execute(
            select(func.count(AuditEvent.institution_id.distinct())).where(
                AuditEvent.identity_id == identity_pk,
                AuditEvent.created_at >= now - timedelta(days=30),
            )
        )
        unique_institutions_30d = inst_result.scalar() or 0

        # Detect simultaneous applications (same identity, multiple institutions, within 48h)
        simultaneous = count_24h > 3 and unique_institutions_30d > 2

        return {
            "query_count_1h": count_1h,
            "query_count_24h": count_24h,
            "query_count_30d": count_30d,
            "unique_institutions_30d": unique_institutions_30d,
            "simultaneous_applications_flag": int(simultaneous),
        }

    async def _extract_network_features(self, identity_id: str) -> dict:
        """Extract network risk features from Neo4j graph database."""
        # In production: query Neo4j for connected identities and their risk scores
        return {
            "high_risk_associate_count": 0,
            "fraud_ring_proximity": 0,
            "shared_device_count": 0,
            "shared_phone_count": 0,
            "network_risk_score": 0.0,
        }

    async def _persist_score(
        self,
        identity: IdentityRecord,
        result: ScoreResult,
        purpose_code: str,
        institution: dict,
        context: dict,
    ) -> None:
        import uuid

        score_record = FraudScoreRecord(
            id=uuid.uuid4(),
            identity_id=identity.id,
            institution_id=institution.get("institution_id", "unknown"),
            request_id=str(uuid.uuid4()),
            overall_score=result.overall_score,
            risk_band=result.risk_band,
            contributing_factors=result.contributing_factors,
            shap_values=result.shap_values,
            watchlist_status=result.watchlist_status,
            sanctions_status=result.sanctions_status,
            model_version=result.model_version,
            context=context,
            purpose_code=purpose_code,
        )
        self._db.add(score_record)
        await self._db.flush()
