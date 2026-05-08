"""Feature engineering for fraud detection model training."""
from __future__ import annotations

import numpy as np
import pandas as pd

FEATURE_COLUMNS = [
    # Document features
    "card_age_days",
    "card_is_new",
    "card_age_log",
    "card_status_score",
    "data_source_count",
    "nia_verified",
    "gis_verified",
    "ssnit_verified",
    "photo_available",
    "days_since_last_verify",
    "recently_verified",
    # Velocity features
    "query_count_1h",
    "query_count_24h",
    "query_count_30d",
    "unique_institutions_30d",
    "simultaneous_applications_flag",
    # Cross-source consistency
    "cross_source_consistency_score",
    "nia_gis_consistency",
    "nia_ssnit_consistency",
    # Behavioral
    "channel_risk",
    "is_night_query",
    "weekend_query_ratio",
    "night_query_ratio_7d",
    # Network risk
    "high_risk_associate_count",
    "fraud_ring_proximity",
    "shared_device_count",
    "shared_phone_count",
    "network_risk_score",
    # Watchlist / sanctions
    "interpol_flag",
    "ofac_sdn_flag",
    "ghana_police_wanted_flag",
    "eoco_flag",
    # Institutional history
    "prior_fraud_reports_count",
    "declined_applications_30d",
    "account_closure_count_1y",
    # Additional
    "address_change_count_90d",
    "dob_cross_source_consistency",
]


def build_features(df: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    """Build feature matrix from raw event DataFrame."""
    feature_df = pd.DataFrame(index=df.index)

    for col in FEATURE_COLUMNS:
        if col in df.columns:
            feature_df[col] = df[col].fillna(0).astype(float)
        else:
            feature_df[col] = 0.0

    # Derived features
    feature_df["velocity_ratio"] = (
        feature_df["query_count_1h"] / (feature_df["query_count_30d"].clip(lower=1))
    )
    feature_df["institution_concentration"] = (
        feature_df["unique_institutions_30d"] / (feature_df["query_count_30d"].clip(lower=1))
    )
    feature_df["source_coverage_score"] = (
        feature_df["nia_verified"] * 0.5
        + feature_df["gis_verified"] * 0.3
        + feature_df["ssnit_verified"] * 0.2
    )

    all_features = FEATURE_COLUMNS + ["velocity_ratio", "institution_concentration", "source_coverage_score"]
    X = feature_df[all_features].values

    return X, all_features
