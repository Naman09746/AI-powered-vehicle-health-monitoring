"""Data validation schemas for sensor data ingestion. Zero extra deps."""

from typing import Any

import pandas as pd

from core.config import PREPROCESSING, REQUIRED_COLUMNS, SENSOR_COLUMNS

ValidationResult = dict[str, Any]


def validate_sensor_data(df: "pd.DataFrame") -> ValidationResult:
    """Validate incoming sensor data against schema rules."""

    errors: list[str] = []
    warnings: list[str] = []
    stats: dict[str, Any] = {"rows": len(df), "columns": len(df.columns)}

    # Required columns
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        errors.append(f"Missing required columns: {', '.join(sorted(missing))}")
        return {"valid": False, "errors": errors, "warnings": warnings, "stats": stats}

    # Type checks
    for col in SENSOR_COLUMNS:
        if col in df.columns:
            non_null = df[col].dropna()
            if non_null.empty:
                warnings.append(f"Column '{col}' is all null")
                continue
            if not pd.api.types.is_numeric_dtype(df[col]):
                warnings.append(
                    f"Column '{col}' should be numeric, got {df[col].dtype}"
                )

    # Missing value ratio
    for col in df.columns:
        null_ratio = df[col].isna().mean()
        if null_ratio > PREPROCESSING["missing_value_threshold"]:
            warnings.append(
                f"Column '{col}' has {null_ratio:.0%} missing values (>{PREPROCESSING['missing_value_threshold']:.0%})"
            )

    # Row count
    min_rows = PREPROCESSING.get("min_rows_for_training", 30)
    if len(df) < min_rows:
        warnings.append(f"Only {len(df)} rows (minimum {min_rows} for training)")

    stats.update(
        {
            "missing_pct": round(df.isna().mean().mean() * 100, 1),
            "non_null_rows": len(df.dropna()),
        }
    )
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "stats": stats,
    }


def validate_prediction_input(features: dict[str, float]) -> ValidationResult:
    """Validate a single prediction input row."""
    errors = []
    for col in SENSOR_COLUMNS:
        if col not in features:
            errors.append(f"Missing feature: {col}")
    return {"valid": len(errors) == 0, "errors": errors}
