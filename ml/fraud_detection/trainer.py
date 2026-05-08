"""
Fraud detection model training pipeline.

Usage:
  python -m ml.fraud_detection.trainer --data-path /data/fraud_training.parquet
"""
from __future__ import annotations

import argparse
import pickle
import uuid
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.preprocessing import StandardScaler
import xgboost as xgb

from .features import FEATURE_COLUMNS, build_features

MODEL_OUTPUT_DIR = Path("ml/models")
MODEL_VERSION = f"fraud-v4.{datetime.now().strftime('%Y%m%d')}"


def train(data_path: str, output_dir: Path = MODEL_OUTPUT_DIR) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Loading training data from {data_path}...")
    df = pd.read_parquet(data_path)

    print(f"Dataset: {len(df):,} rows, {df['is_fraud'].sum():,} fraud cases ({df['is_fraud'].mean()*100:.2f}%)")

    # Feature engineering
    X, feature_names = build_features(df)
    y = df["is_fraud"].values

    # Train/validation split (time-based)
    if "event_date" in df.columns:
        cutoff = df["event_date"].quantile(0.85)
        train_mask = df["event_date"] <= cutoff
        X_train, X_val = X[train_mask], X[~train_mask]
        y_train, y_val = y[train_mask], y[~train_mask]
    else:
        from sklearn.model_selection import train_test_split
        X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.15, stratify=y, random_state=42)

    print(f"Train: {len(X_train):,} | Val: {len(X_val):,}")

    # Compute scale_pos_weight for class imbalance
    neg_count = (y_train == 0).sum()
    pos_count = (y_train == 1).sum()
    scale_pos_weight = neg_count / max(pos_count, 1)
    print(f"Class imbalance ratio: {scale_pos_weight:.1f}:1")

    # -----------------------------------------------------------------------
    # XGBoost Fraud Classifier
    # -----------------------------------------------------------------------
    print("Training XGBoost fraud classifier...")
    xgb_model = xgb.XGBClassifier(
        n_estimators=500,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=scale_pos_weight,
        eval_metric=["auc", "aucpr"],
        early_stopping_rounds=50,
        random_state=42,
        n_jobs=-1,
        tree_method="hist",
    )

    xgb_model.fit(
        X_train,
        y_train,
        eval_set=[(X_val, y_val)],
        verbose=100,
    )

    # Evaluate
    y_pred_proba = xgb_model.predict_proba(X_val)[:, 1]
    y_pred = (y_pred_proba >= 0.5).astype(int)

    print("\n--- XGBoost Evaluation ---")
    print(f"AUROC:     {roc_auc_score(y_val, y_pred_proba):.4f}")
    print(f"AUCPR:     {average_precision_score(y_val, y_pred_proba):.4f}")
    print(f"Precision: {precision_score(y_val, y_pred):.4f}")
    print(f"Recall:    {recall_score(y_val, y_pred):.4f}")
    print(f"F1:        {f1_score(y_val, y_pred):.4f}")

    # -----------------------------------------------------------------------
    # Isolation Forest Anomaly Detector (on legitimate transactions only)
    # -----------------------------------------------------------------------
    print("\nTraining Isolation Forest anomaly detector...")
    X_legit = X_train[y_train == 0]
    iso_model = IsolationForest(
        n_estimators=200,
        contamination=0.05,
        max_features=0.8,
        random_state=42,
        n_jobs=-1,
    )
    iso_model.fit(X_legit)

    # Evaluate anomaly detector
    iso_scores = iso_model.decision_function(X_val)
    iso_pred = (iso_scores < iso_model.threshold_).astype(int)
    print(f"Isolation Forest F1 on val: {f1_score(y_val, iso_pred):.4f}")

    # -----------------------------------------------------------------------
    # Save models
    # -----------------------------------------------------------------------
    version_dir = output_dir / MODEL_VERSION
    version_dir.mkdir(exist_ok=True)

    xgb_path = version_dir / "fraud_xgb.pkl"
    iso_path = version_dir / "anomaly_iso.pkl"
    features_path = version_dir / "feature_names.pkl"
    scaler_path = version_dir / "scaler.pkl"
    meta_path = version_dir / "metadata.json"

    with open(xgb_path, "wb") as f:
        pickle.dump(xgb_model, f)
    with open(iso_path, "wb") as f:
        pickle.dump(iso_model, f)
    with open(features_path, "wb") as f:
        pickle.dump(feature_names, f)

    import json
    metadata = {
        "model_version": MODEL_VERSION,
        "trained_at": datetime.now().isoformat(),
        "training_size": len(X_train),
        "validation_size": len(X_val),
        "fraud_rate": float(y.mean()),
        "feature_count": len(feature_names),
        "auroc": float(roc_auc_score(y_val, y_pred_proba)),
        "aucpr": float(average_precision_score(y_val, y_pred_proba)),
        "precision": float(precision_score(y_val, y_pred)),
        "recall": float(recall_score(y_val, y_pred)),
        "f1": float(f1_score(y_val, y_pred)),
        "feature_names": feature_names,
        "xgb_best_iteration": xgb_model.best_iteration,
    }
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\nModels saved to {version_dir}")
    print(f"AUROC: {metadata['auroc']:.4f}")
    print("Training complete.")

    # Upload to S3 (production)
    _upload_to_s3(version_dir, MODEL_VERSION)


def _upload_to_s3(model_dir: Path, version: str) -> None:
    """Upload trained models to S3 model store."""
    try:
        import boto3
        import os

        bucket = os.getenv("MODEL_S3_BUCKET", "idintel-ghana-models")
        s3 = boto3.client("s3")

        for model_file in model_dir.iterdir():
            s3_key = f"fraud-models/{version}/{model_file.name}"
            s3.upload_file(str(model_file), bucket, s3_key)
            print(f"Uploaded: s3://{bucket}/{s3_key}")
    except Exception as e:
        print(f"S3 upload skipped: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train IDIntel Ghana fraud detection models")
    parser.add_argument("--data-path", required=True, help="Path to training data parquet file")
    parser.add_argument("--output-dir", default="ml/models", help="Output directory for models")
    args = parser.parse_args()
    train(args.data_path, Path(args.output_dir))
