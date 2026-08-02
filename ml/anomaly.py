"""
Unsupervised Anomaly Detection module using IsolationForest.
Detects abnormal sensor patterns and novel failure modes.
"""

from __future__ import annotations

import os
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from core.config import SENSOR_COLUMNS
from core.logger import get_logger

log = get_logger("ml.anomaly")

MODEL_DIR = os.getenv("MODEL_DIR", "model_artifacts")


def get_anomaly_model_path(vehicle_id: int, user_id: int) -> str:
    os.makedirs(MODEL_DIR, exist_ok=True)
    return os.path.join(MODEL_DIR, f"anomaly_v{vehicle_id}_u{user_id}.pkl")


def train_anomaly_model(df: pd.DataFrame, vehicle_id: int, user_id: int) -> dict[str, Any]:
    """
    Train an IsolationForest model on historical sensor readings for a vehicle.
    """
    if df.empty or len(df) < 5:
        return {"status": "error", "message": "At least 5 sensor readings required for anomaly training."}

    valid_cols = [c for c in SENSOR_COLUMNS if c in df.columns]
    X = df[valid_cols].dropna()

    if len(X) < 5:
        return {"status": "error", "message": "Not enough valid numeric readings."}

    model = IsolationForest(contamination=0.05, n_estimators=100, random_state=42)
    model.fit(X)

    path = get_anomaly_model_path(vehicle_id, user_id)
    joblib.dump({"model": model, "feature_columns": valid_cols}, path)
    log.info("Trained anomaly model for vehicle %d (samples=%d, path=%s)", vehicle_id, len(X), path)

    return {
        "status": "success",
        "vehicle_id": vehicle_id,
        "samples": len(X),
        "model_path": path,
    }


def predict_anomaly(vehicle_id: int, user_id: int, reading: dict[str, Any]) -> dict[str, Any]:
    """
    Evaluates a single reading for anomalies against the vehicle's trained IsolationForest model.
    """
    path = get_anomaly_model_path(vehicle_id, user_id)
    if not os.path.exists(path):
        return {
            "trained": False,
            "is_anomaly": False,
            "anomaly_score": 0.0,
            "message": "Anomaly model not trained yet",
        }

    try:
        artifact = joblib.load(path)
        model: IsolationForest = artifact["model"]
        feature_cols: list[str] = artifact["feature_columns"]

        X_input = np.array([[float(reading.get(col, 0.0)) for col in feature_cols]])
        
        # Decision function returns negative value for anomalies, positive for normal
        raw_score = float(model.decision_function(X_input)[0])
        prediction = model.predict(X_input)[0]  # -1 = anomaly, 1 = normal
        is_anomaly = bool(prediction == -1)

        # Normalize score into a friendly 0.0 to 1.0 risk range
        risk_score = round(max(0.0, min(1.0, 0.5 - raw_score)), 3)

        return {
            "trained": True,
            "is_anomaly": is_anomaly,
            "anomaly_score": risk_score,
            "raw_score": round(raw_score, 4),
            "status": "anomaly" if is_anomaly else "normal",
        }
    except Exception as exc:
        log.error("Anomaly prediction error for vehicle %d: %s", vehicle_id, exc)
        return {"trained": False, "is_anomaly": False, "anomaly_score": 0.0, "error": str(exc)}
