"""
Celery task for auto-retraining ML models.

Triggers when:
1. 200+ new readings have accumulated since the last training, OR
2. Data drift is detected (distribution shift beyond threshold).

Champion/Challenger: new models are only promoted if they improve
F1 by at least 2 % over the current champion.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from typing import Any

# Ensure project root is on path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from core.config import ML_CONFIG, REDIS_URL
from core.logger import get_logger, log_event

log = get_logger("retrain_task")

try:
    from celery import Celery

    app = Celery(
        "vhm_retrain",
        broker=REDIS_URL,
        backend=REDIS_URL,
    )
    _celery_available = True
except ImportError:
    app = None  # type: ignore
    _celery_available = False
    log.warning("Celery not available — retrain tasks are stubbed")


def should_retrain(vehicle_id: int, user_id: int) -> tuple[bool, str]:
    """
    Check whether a vehicle qualifies for auto-retraining.

    Returns (should_retrain, reason).
    """
    import core.db as database

    session = database.get_session()
    try:
        # Count readings since last training
        last_model = (
            session.query(database.TrainedModel)
            .filter_by(
                vehicle_id=vehicle_id,
                user_id=user_id,
            )
            .order_by(database.TrainedModel.trained_at.desc())
            .first()
        )

        last_train_time = last_model.trained_at if last_model else datetime(2000, 1, 1)
        new_readings = (
            session.query(database.SensorReading)
            .filter(
                database.SensorReading.vehicle_id == vehicle_id,
                database.SensorReading.user_id == user_id,
                database.SensorReading.timestamp > last_train_time,
            )
            .count()
        )

        if new_readings >= 200:
            return True, f"{new_readings} new readings since last training"

        # Check drift if champion exists
        if last_model and last_model.feature_columns_json:
            from ml.ml_models import evaluate_drift

            # Get recent and reference data
            df_all = database.get_sensor_readings(vehicle_id, user_id)
            if len(df_all) >= 100:
                split = len(df_all) // 2
                reference_df = df_all.iloc[:split]
                current_df = df_all.iloc[split:]
                drift_result = evaluate_drift(
                    reference_df,
                    current_df,
                    feature_columns=None,
                )
                if drift_result["drift_detected"]:
                    return (
                        True,
                        f"Data drift detected ({len(drift_result['drifted_features'])} features)",
                    )

        return False, "No retrain trigger"
    finally:
        session.close()


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def auto_retrain(self, vehicle_id: int, user_id: int) -> dict[str, Any]:
    """
    Celery task: auto-retrain models for a specific vehicle.

    Returns a dict with status and model info.
    """
    import core.db as database
    from ml.ml_models import train_models
    from ml.ml_registry import registry

    log.info("Auto-retrain started for vehicle %s (user %s)", vehicle_id, user_id)
    log_event("ml-retrain-start", vehicle_id=vehicle_id, user_id=user_id)

    try:
        should, reason = should_retrain(vehicle_id, user_id)
        if not should:
            log.info("Auto-retrain skipped for vehicle %s: %s", vehicle_id, reason)
            return {"status": "skipped", "reason": reason}

        # Fetch data
        df = database.get_sensor_readings(vehicle_id, user_id)
        if df.empty:
            return {"status": "skipped", "reason": "No sensor data"}

        # Validate
        valid, msg = _validate(df)
        if not valid:
            log.warning("Auto-retrain validation failed: %s", msg)
            return {"status": "failed", "reason": msg}

        # Run preprocessing
        from core.preprocessing import preprocess

        df_clean, _ = preprocess(df)

        # Train models
        result = train_models(df_clean, user_id, vehicle_id)

        if result["best_model"] is None:
            return {"status": "failed", "reason": "No model trained successfully"}

        # Register as challenger
        model_id = registry.register(result, vehicle_id, user_id)
        if model_id is None:
            return {"status": "failed", "reason": "Registry registration failed"}

        # Promote if delta > 2% over champion
        champion = registry.get_champion(vehicle_id, user_id)
        if (
            champion
            and champion.challenger_vs_champion_delta is not None
            and champion.challenger_vs_champion_delta > 0.02
        ):
            registry.promote_champion(int(model_id), vehicle_id, user_id)
            log.info(
                "Champion promoted (delta = %.4f)",
                champion.challenger_vs_champion_delta,
            )

        log_event(
            "ml-retrain-complete",
            vehicle_id=vehicle_id,
            user_id=user_id,
            model_id=model_id,
            best_model=result["best_model"],
        )
        return {
            "status": "success",
            "model_id": model_id,
            "best_model": result["best_model"],
            "reason": reason,
        }
    except Exception as exc:
        log.exception("Auto-retrain failed for vehicle %s", vehicle_id)
        log_event("ml-retrain-error", vehicle_id=vehicle_id, error=str(exc))
        raise self.retry(exc=exc) from exc


def _validate(df) -> tuple[bool, str]:
    """Validate that data is suitable for training."""
    if len(df) < ML_CONFIG["min_rows_for_training"]:
        return False, f"Insufficient data ({len(df)} rows)"
    if "failure_label" not in df.columns:
        return False, "Missing failure_label column"
    unique = df["failure_label"].dropna().unique()
    if len(unique) < 2:
        return False, f"Only one class: {unique}"
    return True, "ok"


# ── For development/testing without Celery ──


def retrain_now(vehicle_id: int, user_id: int) -> dict[str, Any]:
    """Run the retrain synchronously (no Celery broker needed)."""
    if _celery_available:
        return auto_retrain.delay(vehicle_id, user_id).get(timeout=300)
    else:
        return auto_retrain(vehicle_id, user_id)
