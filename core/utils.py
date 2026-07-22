"""
Shared utility functions - CSV validation, formatters, common helpers.
"""

import pandas as pd

from core.config import COLUMN_ALIASES, REQUIRED_COLUMNS, SENSOR_COLUMNS


def validate_and_normalize_csv(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame | None, list[str]]:
    """
    Validate an uploaded CSV DataFrame against the expected sensor schema.

    Steps:
    1. Lowercase + strip all column names.
    2. Apply column aliases to map alternative names to canonical names.
    3. Check that all required columns are present.

    Returns:
        (normalized_df, errors) - if errors is non-empty, normalized_df is None.
    """
    errors = []

    if df.empty:
        return None, ["The uploaded file is empty."]

    # Normalize column names
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

    # Apply aliases
    rename_map = {}
    for col in df.columns:
        if col in COLUMN_ALIASES:
            rename_map[col] = COLUMN_ALIASES[col]
    if rename_map:
        df = df.rename(columns=rename_map)

    # Check required columns
    present = set(df.columns)
    missing = REQUIRED_COLUMNS - present
    extra = present - REQUIRED_COLUMNS - {"failure_label", "maintenance_needed"}

    if missing:
        errors.append(f"**Missing required columns:** {', '.join(sorted(missing))}")

    if extra:
        # Not an error, just informational.
        pass

    if errors:
        return None, errors

    # Keep only required columns + optional label columns
    keep_cols = list(REQUIRED_COLUMNS)
    if "failure_label" in df.columns:
        keep_cols.append("failure_label")
    if "maintenance_needed" in df.columns:
        keep_cols.append("maintenance_needed")
    df = df[keep_cols]

    # Try to parse timestamp
    try:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    except Exception:
        errors.append(
            "Could not parse the `timestamp` column. Ensure it contains "
            "valid date/time values."
        )
        return None, errors

    # Ensure sensor columns are numeric
    for col in SENSOR_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df, errors


def format_number(value: float, decimals: int = 1) -> str:
    """Format a number with specified decimal places."""
    if pd.isna(value):
        return "N/A"
    return f"{value:,.{decimals}f}"


def get_failure_class(prob: float) -> dict:
    """Get failure class info from probability."""
    from core.config import FAILURE_CLASSES

    if prob < 0.4:
        return FAILURE_CLASSES["healthy"]
    elif prob < 0.7:
        return FAILURE_CLASSES["maintenance"]
    else:
        return FAILURE_CLASSES["high_risk"]


def get_health_band(score: float) -> dict:
    """Get health band info from score."""
    from core.config import HEALTH_BANDS

    for band_name, band_info in HEALTH_BANDS.items():
        if band_info["min"] <= score <= band_info["max"]:
            return {"name": band_name, **band_info}
    return {"name": "Critical", **HEALTH_BANDS["Critical"]}


def get_priority(failure_prob: float) -> str:
    """Get priority level from failure probability."""
    if failure_prob < 0.4:
        return "Low"
    elif failure_prob < 0.7:
        return "Medium"
    else:
        return "High"
