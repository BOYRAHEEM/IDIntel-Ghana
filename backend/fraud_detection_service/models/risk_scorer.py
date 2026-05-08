"""XGBoost + Isolation Forest fraud risk scoring model."""
from __future__ import annotations

import os
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

MODEL_DIR = Path(os.getenv("MODEL_DIR", "/app/models"))

_xgb_model = None
_isolation_forest = None
_feature_names: list[str] = []


def _load_models():
    global _xgb_model, _isolation_forest, _feature_names
    if _xgb_model is not None:
        return

    xgb_path = MODEL_DIR / "fraud_xgb_v3.pkl"
    iso_path = MODEL_DIR / "anomaly_iso_v3.pkl"
    features_path = MODEL_DIR / "feature_names.pkl"

    if xgb_path.exists():
        with open(xgb_path, "rb") as f:
            _xgb_model = pickle.load(f)

    if iso_path.exists():
        with open(iso_path, "rb") as f:
            _isolation_forest = pickle.load(f)

    if features_path.exists():
        with open(features_path, "rb") as f:
            _feature_names = pickle.load(f)


@dataclass
class ScoreResult:
    overall_score: int
    risk_band: str
    interpretation: str
    contributing_factors: list[dict] = field(default_factory=list)
    shap_values: dict = field(default_factory=dict)
    watchlist_status: str = "CLEAR"
    sanctions_status: str = "CLEAR"
    anomaly_score: float = 0.0
    model_version: str = "fraud-v3.2.1"


class RiskScorer:
    """Computes a 0-1000 fraud risk score from extracted features."""

    def score(self, features: dict[str, float], include_shap: bool = False) -> ScoreResult:
        _load_models()

        feature_vector = self._build_feature_vector(features)

        # XGBoost fraud probability
        if _xgb_model is not None:
            fraud_prob = float(_xgb_model.predict_proba([feature_vector])[0][1])
        else:
            fraud_prob = self._rule_based_score(features) / 1000.0

        # Isolation Forest anomaly score
        anomaly_score = 0.0
        if _isolation_forest is not None:
            iso_score = _isolation_forest.decision_function([feature_vector])[0]
            anomaly_score = max(0.0, min(1.0, -iso_score))

        # Combine: 70% XGBoost fraud probability + 30% anomaly score
        combined = (fraud_prob * 0.7) + (anomaly_score * 0.3)
        raw_score = int(combined * 1000)

        # Apply watchlist/sanctions penalties
        watchlist_penalty = 0
        sanctions_penalty = 0

        if features.get("interpol_flag", 0) or features.get("ghana_police_wanted_flag", 0):
            watchlist_penalty = 300
        if features.get("ofac_sdn_flag", 0):
            sanctions_penalty = 400

        final_score = min(1000, raw_score + watchlist_penalty + sanctions_penalty)

        risk_band, interpretation = _score_to_band(final_score)
        contributing_factors = self._build_contributing_factors(features, fraud_prob)

        shap_values: dict = {}
        if include_shap and _xgb_model is not None:
            shap_values = self._compute_shap(feature_vector)

        return ScoreResult(
            overall_score=final_score,
            risk_band=risk_band,
            interpretation=interpretation,
            contributing_factors=contributing_factors,
            shap_values=shap_values,
            watchlist_status="FLAGGED" if watchlist_penalty > 0 else "CLEAR",
            sanctions_status="MATCH" if sanctions_penalty > 0 else "CLEAR",
            anomaly_score=anomaly_score,
        )

    def _build_feature_vector(self, features: dict) -> list[float]:
        if _feature_names:
            return [float(features.get(name, 0.0)) for name in _feature_names]
        return list(features.values())

    def _rule_based_score(self, features: dict) -> int:
        """Fallback rule-based scoring when ML model isn't loaded (development)."""
        score = 100

        # Velocity signals
        if features.get("query_count_1h", 0) > 10:
            score += 200
        elif features.get("query_count_1h", 0) > 5:
            score += 100

        if features.get("simultaneous_applications_flag", 0):
            score += 250

        # Consistency
        consistency = features.get("cross_source_consistency_score", 1.0)
        score += int((1.0 - consistency) * 300)

        # Network risk
        if features.get("high_risk_associate_count", 0) > 2:
            score += 150

        # Document age
        card_age = features.get("card_age_days", 365)
        if card_age < 30:
            score += 100

        return min(1000, score)

    def _build_contributing_factors(
        self, features: dict, fraud_prob: float
    ) -> list[dict]:
        factors = []

        # Velocity
        q1h = features.get("query_count_1h", 0)
        factors.append({
            "factor": "query_velocity",
            "weight": min(0.25, q1h * 0.05),
            "value": "HIGH" if q1h > 5 else "NORMAL",
            "explanation": f"{int(q1h)} queries in last hour — {'unusual velocity' if q1h > 5 else 'within normal range'}",
        })

        # Cross-source consistency
        consistency = features.get("cross_source_consistency_score", 1.0)
        factors.append({
            "factor": "document_consistency",
            "weight": round(1.0 - consistency, 2),
            "value": "HIGH" if consistency > 0.95 else ("MEDIUM" if consistency > 0.80 else "LOW"),
            "explanation": f"Data consistency across sources: {consistency*100:.0f}%",
        })

        # Simultaneous applications
        if features.get("simultaneous_applications_flag", 0):
            factors.append({
                "factor": "simultaneous_applications",
                "weight": 0.30,
                "value": "FLAGGED",
                "explanation": "Multiple simultaneous financial applications detected — strong fraud signal",
            })

        # Network risk
        high_risk = int(features.get("high_risk_associate_count", 0))
        if high_risk > 0:
            factors.append({
                "factor": "network_risk",
                "weight": min(0.20, high_risk * 0.05),
                "value": "HIGH" if high_risk > 2 else "MEDIUM",
                "explanation": f"{high_risk} high-risk associate(s) in identity network",
            })

        return factors

    def _compute_shap(self, feature_vector: list[float]) -> dict:
        try:
            import shap
            explainer = shap.TreeExplainer(_xgb_model)
            shap_vals = explainer.shap_values(np.array([feature_vector]))[0]
            if _feature_names and len(_feature_names) == len(shap_vals):
                return {_feature_names[i]: float(shap_vals[i]) for i in range(len(shap_vals))}
        except Exception:
            pass
        return {}


def _score_to_band(score: int) -> tuple[str, str]:
    if score <= 200:
        return "LOW", "Low risk. No significant fraud indicators detected. Proceed normally."
    if score <= 500:
        return "MEDIUM", "Moderate risk. Additional verification recommended before proceeding."
    if score <= 750:
        return "HIGH", "High risk. Manual review by compliance officer required before proceeding."
    return "CRITICAL", "Critical risk. Decline transaction. Flag for investigation."
