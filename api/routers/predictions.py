"""
Prediction router — run and retrieve failure predictions.
Dispatches webhooks on prediction completion.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from api.db_proxy import (
    async_get_predictions_for_vehicle,
    async_get_sensor_readings,
    async_get_vehicle_by_id,
    async_save_prediction,
)
from api.dependencies import get_current_user
from api.schemas.vehicle import PredictionResponse

router = APIRouter(prefix="/api/v1/predictions", tags=["predictions"])


@router.post("/run", response_model=dict)
async def run_prediction(
    vehicle_id: int,
    background_tasks: BackgroundTasks,
    user: dict[str, Any] = Depends(get_current_user),
):
    """Run a failure prediction using the champion model for a vehicle."""
    from ml.ml_models import predict
    from ml.ml_registry import registry

    vehicle = await async_get_vehicle_by_id(vehicle_id, user["id"])
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    import os
    champion = registry.get_champion(vehicle_id, user["id"])
    if not champion or not getattr(champion, "model_path", None) or not os.path.exists(champion.model_path):
        from ml.ml_models import train_models
        from api.dependencies import sync_to_async

        # Auto-seed sensor data if empty
        df_readings = await async_get_sensor_readings(vehicle_id, user["id"])
        if df_readings.empty or len(df_readings) < 5:
            from api.routers.simulator import ensure_vehicle_simulation
            v_name = getattr(vehicle, "vehicle_id_display", f"VH-{vehicle_id}")
            ensure_vehicle_simulation(vehicle_id, user["id"], v_name)
            df_readings = await async_get_sensor_readings(vehicle_id, user["id"])

        from core.preprocessing import preprocess
        df_clean_train, _ = await sync_to_async(preprocess, df_readings)
        train_res = await sync_to_async(train_models, df_clean_train, user["id"], vehicle_id)
        await sync_to_async(registry.register, train_res, vehicle_id, user["id"])
        champion = registry.get_champion(vehicle_id, user["id"])

    if not champion:
        raise HTTPException(
            status_code=400,
            detail="No trained model found. Train a model first.",
        )

    # Get latest sensor readings
    df = await async_get_sensor_readings(vehicle_id, user["id"])
    if df.empty:
        try:
            from api.routers.simulator import ensure_vehicle_simulation
            v_name = getattr(vehicle, "vehicle_id_display", f"VH-{vehicle_id}")
            ensure_vehicle_simulation(vehicle_id, user["id"], v_name)
            df = await async_get_sensor_readings(vehicle_id, user["id"])
        except Exception:
            pass

    if df.empty:
        raise HTTPException(
            status_code=400,
            detail="No sensor data available for prediction.",
        )

    from core.preprocessing import preprocess, get_feature_columns
    df_clean, _ = preprocess(df)

    feature_columns = json.loads(getattr(champion, "feature_columns_json", "[]") or "[]")
    if not feature_columns:
        feature_columns = get_feature_columns(df_clean)

    # Use the most recent preprocessed reading
    latest = df_clean.iloc[-1:]
    result = predict(
        model_path=champion.model_path,
        scaler_path=champion.scaler_path or "",
        input_df=latest,
        feature_columns=feature_columns,
    )

    # Save prediction
    pred = await async_save_prediction(
        user_id=user["id"],
        vehicle_id=vehicle_id,
        model_id=champion.id,
        prediction=result["prediction_class"],
        failure_prob=result["failure_prob"],
        health_score=0.0,
        top_features=json.dumps(result.get("feature_importances", [])),
    )

    # ── Dispatch webhook in background ──
    from api.webhooks import dispatch_webhook

    background_tasks.add_task(
        dispatch_webhook,
        event="prediction.complete",
        payload={
            "prediction_id": pred.id,
            "prediction_class": result["prediction_class"],
            "failure_prob": result["failure_prob"],
            "confidence": result["confidence"],
        },
        user_id=user["id"],
        vehicle_id=vehicle_id,
    )

    return {
        "prediction_id": pred.id,
        "prediction_class": result["prediction_class"],
        "failure_prob": result["failure_prob"],
        "confidence": result["confidence"],
        "top_features": result.get("feature_importances", [])[:5],
    }


@router.get("", response_model=list[PredictionResponse])
async def list_predictions(
    vehicle_id: int,
    user: dict[str, Any] = Depends(get_current_user),
):
    """List all predictions for a vehicle."""
    vehicle = await async_get_vehicle_by_id(vehicle_id, user["id"])
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return await async_get_predictions_for_vehicle(vehicle_id, user["id"])
