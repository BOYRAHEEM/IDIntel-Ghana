"""Feature extraction for fraud scoring model."""
from __future__ import annotations

from datetime import date, datetime, timezone

from ...shared.models.identity import IdentityRecord


class FeatureExtractor:
    """Transforms raw identity + behavioral data into ML-ready feature vectors."""

    def extract(
        self,
        identity: IdentityRecord,
        velocity: dict,
        network: dict,
        context: dict,
    ) -> dict[str, float]:
        features: dict[str, float] = {}

        # Document features
        features.update(self._document_features(identity))
        # Velocity features (from audit history)
        features.update(velocity)
        # Network features (from Neo4j)
        features.update(network)
        # Context features
        features.update(self._context_features(context))
        # Consistency features
        features.update(self._consistency_features(identity))
        # Flag features
        features.update(self._flag_features(identity))

        return features

    def _document_features(self, identity: IdentityRecord) -> dict[str, float]:
        now = datetime.now(timezone.utc)
        features: dict[str, float] = {}

        # Card age in days
        if identity.ghana_card_issue_date:
            age_days = (date.today() - identity.ghana_card_issue_date).days
            features["card_age_days"] = float(age_days)
            features["card_is_new"] = float(age_days < 30)
            features["card_age_log"] = float(max(1, age_days)) ** 0.5
        else:
            features["card_age_days"] = 0.0
            features["card_is_new"] = 1.0
            features["card_age_log"] = 0.0

        # Document status encoding
        status_map = {"VALID": 1.0, "EXPIRED": 0.3, "SUSPENDED": 0.0, "CANCELLED": 0.0, "UNKNOWN": 0.2}
        features["card_status_score"] = status_map.get(
            identity.ghana_card_status.value if identity.ghana_card_status else "UNKNOWN", 0.2
        )

        # Multi-source coverage
        features["data_source_count"] = float(len(identity.data_sources or []))
        features["nia_verified"] = float(identity.nia_verified)
        features["gis_verified"] = float(identity.gis_verified)
        features["ssnit_verified"] = float(identity.ssnit_verified)

        # Photo availability (proxy for identity completeness)
        features["photo_available"] = float(bool(identity.photo_reference_id))

        # Time since last verification
        if identity.last_verified_at:
            days_since_verify = (now - identity.last_verified_at.replace(tzinfo=timezone.utc)).days
            features["days_since_last_verify"] = float(days_since_verify)
            features["recently_verified"] = float(days_since_verify < 7)
        else:
            features["days_since_last_verify"] = 999.0
            features["recently_verified"] = 0.0

        return features

    def _context_features(self, context: dict) -> dict[str, float]:
        features: dict[str, float] = {}

        # Channel risk (digital has higher fraud risk than in-person)
        channel_risk = {"branch": 0.1, "atm": 0.2, "digital": 0.4, "api": 0.3}
        features["channel_risk"] = channel_risk.get(context.get("channel", "api"), 0.3)

        # Night query flag
        features["is_night_query"] = _is_night_query()

        return features

    def _consistency_features(self, identity: IdentityRecord) -> dict[str, float]:
        confidence_scores = identity.source_confidence_scores or {}

        overall = identity.overall_confidence or 0.0
        nia_gis = confidence_scores.get("nia_gis_consistency", 1.0)
        nia_ssnit = confidence_scores.get("nia_ssnit_consistency", 1.0)

        return {
            "cross_source_consistency_score": float(overall),
            "nia_gis_consistency": float(nia_gis),
            "nia_ssnit_consistency": float(nia_ssnit),
        }

    def _flag_features(self, identity: IdentityRecord) -> dict[str, float]:
        return {
            "is_deceased_flag": float(identity.is_deceased),
            "is_blocked_flag": float(identity.is_blocked),
            # Watchlist flags would be populated from real-time screening
            "interpol_flag": 0.0,
            "ofac_sdn_flag": 0.0,
            "ghana_police_wanted_flag": 0.0,
            "eoco_flag": 0.0,
        }


def _is_night_query() -> float:
    """Returns 1.0 if current time is between 23:00 and 05:00 Ghana time (GMT+0)."""
    hour = datetime.now(timezone.utc).hour
    return float(hour >= 23 or hour < 5)
