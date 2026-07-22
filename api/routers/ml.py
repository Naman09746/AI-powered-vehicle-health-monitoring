"""
ML router — train models, list models, promote champion.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

import core.db as database
from api.dependencies import get_current_user
from core.logger import get_logger

log = get_logger("api.ml")
router = APIRouter(prefix="/api/v1/ml", tags=["ml"])


@router.post("/train/{vehicle_id}")
async def train(
    vehicle_id: int,
    background_tasks: BackgroundTasks,
    tuning_mode: str = "quick",
    user: dict[str, Any] = Depends(get_current_user),
):
    """Train models for a vehicle."""
    from api.dependencies import sync_to_async
    from core.preprocessing import preprocess

    df = await sync_to_async(database.get_sensor_readings, vehicle_id, user["id"])
    if df.empty:
        raise HTTPException(status_code=400, detail="No sensor data available.")

    df_clean, log_entries = await sync_to_async(preprocess, df)
    valid, msg = await sync_to_async(_validate, df_clean)
    if not valid:
        raise HTTPException(status_code=400, detail=msg)

    if tuning_mode == "thorough":
        from ml.ml_models import train_models_with_tuning

        result = await sync_to_async(
            train_models_with_tuning,
            df_clean,
            user["id"],
            vehicle_id,
            tuning_mode="thorough",
        )
    else:
        from ml.ml_models import train_models

        result = await sync_to_async(train_models, df_clean, user["id"], vehicle_id)

    if result["best_model"] is None:
        raise HTTPException(status_code=500, detail="No model trained successfully.")

    # Register as challenger
    from ml.ml_registry import registry

    model_id = await sync_to_async(registry.register, result, vehicle_id, user["id"])

    # ── Dispatch webhook in background ──
    from api.webhooks import dispatch_webhook

    background_tasks.add_task(
        dispatch_webhook,
        event="training.done",
        payload={
            "model_id": model_id,
            "best_model": result["best_model"],
            "best_reason": result.get("best_reason", ""),
            "n_results": len(result["results"]),
            "tuning_mode": tuning_mode,
        },
        user_id=user["id"],
        vehicle_id=vehicle_id,
    )

    return {
        "status": "success",
        "best_model": result["best_model"],
        "best_reason": result.get("best_reason", ""),
        "n_results": len(result["results"]),
        "model_id": model_id,
        "results": [
            {"name": r["name"], "metrics": r.get("metrics"), "error": r.get("error")}
            for r in result["results"]
        ],
    }


@router.get("/models")
async def list_models(
    vehicle_id: int | None = None,
    user: dict[str, Any] = Depends(get_current_user),
):
    """List trained models, optionally filtered by vehicle."""
    if vehicle_id:
        from ml.ml_registry import registry

        return registry.list_models(vehicle_id, user["id"])
    return database.get_all_trained_models(user["id"])


@router.get("/models/{vehicle_id}")
async def list_vehicle_models(
    vehicle_id: int,
    user: dict[str, Any] = Depends(get_current_user),
):
    """List all model versions for a vehicle."""
    from ml.ml_registry import registry

    return registry.list_models(vehicle_id, user["id"])


@router.post("/models/{model_id}/promote")
async def promote_model(
    model_id: int,
    vehicle_id: int,
    user: dict[str, Any] = Depends(get_current_user),
):
    """Promote a model to champion."""
    from ml.ml_registry import registry

    success = registry.promote_champion(model_id, vehicle_id, user["id"])
    if not success:
        raise HTTPException(status_code=400, detail="Failed to promote model.")
    return {"status": "success", "model_id": model_id, "is_champion": True}


@router.delete("/models/{model_id}")
async def delete_model(
    model_id: int,
    user: dict[str, Any] = Depends(get_current_user),
):
    """Delete a trained model record."""
    from api.dependencies import sync_to_async

    success = await sync_to_async(database.delete_trained_model, model_id, user["id"])
    if not success:
        raise HTTPException(status_code=404, detail="Model not found.")
    return {"status": "success", "message": "Trained model deleted successfully."}


def _validate(df) -> tuple[bool, str]:
    from ml.ml_models import validate_training_data

    return validate_training_data(df)
