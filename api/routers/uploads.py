"""
Upload router — CSV ingestion, sample CSV download, upload history.
"""

from __future__ import annotations

import io
import os
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

import core.db as database
from api.dependencies import get_current_user
from core.logger import get_logger
from core.preprocessing import preprocess

log = get_logger("api.uploads")
router = APIRouter(prefix="/api/v1/uploads", tags=["uploads"])

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@router.post("/{vehicle_id}")
async def upload_csv(
    vehicle_id: int,
    file: UploadFile = File(...),
    user: dict[str, Any] = Depends(get_current_user),
):
    """Upload a CSV file of sensor readings."""
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")

    contents = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {e}")

    from core.config import REQUIRED_COLUMNS

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        # Try column alias mapping
        from core.config import COLUMN_ALIASES

        df = df.rename(
            columns={
                k: v
                for k, v in COLUMN_ALIASES.items()
                if k in df.columns and v not in df.columns
            }
        )
        missing = REQUIRED_COLUMNS - set(df.columns)
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required columns: {missing}. Required: {REQUIRED_COLUMNS}",
            )

    row_count_raw = len(df)

    # Run data validation
    from ml.quality import generate_quality_report
    from ml.validation import validate_sensor_data

    validation = validate_sensor_data(df)
    quality = generate_quality_report(df)
    log.info(
        "Upload validation: valid=%s, errors=%d, quality=%.1f",
        validation["valid"],
        len(validation["errors"]),
        quality["quality_score"],
    )

    if not validation["valid"]:
        raise HTTPException(
            status_code=400,
            detail=f"Validation failed: {'; '.join(validation['errors'])}",
        )

    # Preprocess
    df_clean, log_entries = preprocess(df)
    row_count_clean = len(df_clean)

    # Save upload record
    import json

    preprocessing_log_json = json.dumps(
        {"preprocessing": log_entries, "validation": validation, "quality": quality}
    )
    upload = database.create_sensor_upload(
        vehicle_id=vehicle_id,
        user_id=user["id"],
        filename=file.filename,
        row_count_raw=row_count_raw,
        row_count_clean=row_count_clean,
        preprocessing_log=preprocessing_log_json,
    )

    # Save readings to database
    database.save_sensor_readings(
        upload_id=upload.id, vehicle_id=vehicle_id, user_id=user["id"], df=df_clean
    )

    return {
        "upload_id": upload.id,
        "filename": file.filename,
        "row_count_raw": row_count_raw,
        "row_count_clean": row_count_clean,
        "log_entries": log_entries,
        "validation": validation,
        "quality_score": quality["quality_score"],
        "preview": df_clean.head(10).to_dict(orient="records"),
    }


@router.get("/sample-csv")
async def download_sample_csv():
    """Download a sample CSV template."""
    from scripts.generate_data import generate_sample_data

    df = generate_sample_data(n_rows=20, seed=42)
    output = io.StringIO()
    df.to_csv(output, index=False)
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sample_sensor_data.csv"},
    )


@router.get("/{vehicle_id}")
async def upload_history(
    vehicle_id: int,
    user: dict[str, Any] = Depends(get_current_user),
):
    """List all uploads for a vehicle."""
    return database.get_uploads_for_vehicle(vehicle_id, user["id"])


@router.delete("/{upload_id}")
async def delete_upload(
    upload_id: int,
    user: dict[str, Any] = Depends(get_current_user),
):
    """Delete an upload record and its sensor readings."""
    from api.dependencies import sync_to_async

    success = await sync_to_async(database.delete_sensor_upload, upload_id, user["id"])
    if not success:
        raise HTTPException(status_code=404, detail="Upload not found.")
    return {"status": "success", "message": "Upload and associated readings deleted."}
