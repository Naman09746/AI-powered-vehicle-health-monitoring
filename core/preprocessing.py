"""
Data preprocessing pipeline - cleaning, feature engineering, synthetic labeling.
Every transformation step is logged for auditability.
"""

from datetime import UTC

import numpy as np
import pandas as pd

from core.config import (
    PREPROCESSING,
    SENSOR_COLUMNS,
    SENSOR_THRESHOLDS,
    SYNTHETIC_LABEL_MIN_ANOMALIES,
)


def preprocess(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    Full preprocessing pipeline on uploaded sensor data.

    Steps:
    1. Remove duplicates
    2. Handle missing values (median imputation)
    3. Detect outliers (IQR-based flagging)
    4. Feature engineering (rolling avg, rate-of-change, anomaly flags)
    5. Generate synthetic failure labels (if no user-provided label)

    Returns:
        (cleaned_df, log_entries): The processed DataFrame and a list of
        human-readable log entries describing each step.
    """
    log = []
    original_rows = len(df)
    log.append(f"**Input:** {original_rows} rows, {len(df.columns)} columns")

    # Step 1: Remove duplicates
    df, dup_log = _remove_duplicates(df)
    log.append(dup_log)

    # Step 2: Handle missing values
    df, missing_logs = _handle_missing_values(df)
    log.extend(missing_logs)

    # Step 3: Detect outliers
    df, outlier_logs = _detect_outliers(df)
    log.extend(outlier_logs)

    # Step 4: Feature engineering
    df, feat_logs = _engineer_features(df)
    log.extend(feat_logs)

    # Step 5: Synthetic labeling
    has_user_label = (
        "failure_label" in df.columns and df["failure_label"].notna().sum() > 0
    )
    if has_user_label:
        # Check if user-provided labels are valid (0/1)
        unique_labels = df["failure_label"].dropna().unique()
        if set(unique_labels).issubset({0, 1}):
            df["failure_label"] = df["failure_label"].fillna(0).astype(int)
            log.append(
                f"**Labels:** Using user-provided `failure_label` column "
                f"(0: {(df['failure_label'] == 0).sum()}, 1: {(df['failure_label'] == 1).sum()})"
            )
        else:
            log.append(
                f"**Labels warning:** `failure_label` column has unexpected values {unique_labels}. "
                "Falling back to synthetic labeling."
            )
            df = _generate_synthetic_labels(df)
            log.append(_synthetic_label_summary(df))
    else:
        df = _generate_synthetic_labels(df)
        log.append(_synthetic_label_summary(df))

    final_rows = len(df)
    log.append(
        f"**Output:** {final_rows} rows, {len(df.columns)} columns "
        f"({original_rows - final_rows} rows removed)"
    )

    return df, log


def _remove_duplicates(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """Remove duplicate rows."""
    dup_count = df.duplicated().sum()
    if dup_count > 0:
        df = df.drop_duplicates().reset_index(drop=True)
        return df, f"**Duplicates:** Removed {dup_count} duplicate rows"
    return df, "**Duplicates:** No duplicates found"


def _handle_missing_values(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Handle missing values with median imputation for sensor columns."""
    logs = []
    threshold = PREPROCESSING["missing_value_threshold"]

    total_missing = df[SENSOR_COLUMNS].isnull().sum()
    cols_with_missing = total_missing[total_missing > 0]

    if cols_with_missing.empty:
        logs.append("**Missing Values:** No missing values detected in sensor columns")
        return df, logs

    flagged_cols = []
    imputed_cols = []

    for col in SENSOR_COLUMNS:
        missing_count = df[col].isnull().sum()
        if missing_count == 0:
            continue

        missing_pct = missing_count / len(df)

        if missing_pct > threshold:
            flagged_cols.append(f"{col} ({missing_pct:.0%})")

        # Impute with median regardless (but flag high-missing columns)
        median_val = df[col].median()
        df[col] = df[col].fillna(median_val)
        imputed_cols.append(f"{col} (median={median_val:.2f}, {missing_count} values)")

    if imputed_cols:
        logs.append(
            f"**Missing Values:** Imputed {len(imputed_cols)} columns with median: "
            + ", ".join(imputed_cols)
        )

    if flagged_cols:
        logs.append(
            f"**High Missing Rate (>{threshold:.0%}):** {', '.join(flagged_cols)} - "
            "results may be less reliable for these sensors"
        )

    return df, logs


def _detect_outliers(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Detect outliers using IQR method. Flag but don't drop."""
    logs = []
    method = PREPROCESSING["outlier_method"]
    total_outliers = 0

    for col in SENSOR_COLUMNS:
        if method == "iqr":
            Q1 = df[col].quantile(0.25)
            Q3 = df[col].quantile(0.75)
            IQR = Q3 - Q1
            multiplier = PREPROCESSING["iqr_multiplier"]
            lower = Q1 - multiplier * IQR
            upper = Q3 + multiplier * IQR
            outlier_mask = (df[col] < lower) | (df[col] > upper)
        else:  # zscore
            z_scores = np.abs((df[col] - df[col].mean()) / df[col].std())
            outlier_mask = z_scores > PREPROCESSING["zscore_threshold"]

        df[f"{col}_outlier"] = outlier_mask.astype(int)
        n_outliers = outlier_mask.sum()
        total_outliers += n_outliers

    logs.append(
        f"**Outliers ({method.upper()}):** Flagged {total_outliers} total outlier values "
        f"across {len(SENSOR_COLUMNS)} sensors (not dropped - flagged for review)"
    )

    return df, logs


def _engineer_features(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Create rolling averages, rate-of-change, and anomaly flag features."""
    logs = []
    window = PREPROCESSING["rolling_window"]
    new_features = 0

    # Sort by timestamp for temporal features
    if "timestamp" in df.columns:
        df = df.sort_values("timestamp").reset_index(drop=True)

    for col in SENSOR_COLUMNS:
        # Rolling average
        df[f"{col}_rolling_avg"] = df[col].rolling(window=window, min_periods=1).mean()
        new_features += 1

        # Rate of change (first difference)
        df[f"{col}_rate_of_change"] = df[col].diff().fillna(0)
        new_features += 1

        # Anomaly flag: 1 if outside normal range from core.config thresholds
        thresholds = SENSOR_THRESHOLDS[col]
        df[f"{col}_anomaly"] = (
            (df[col] < thresholds["min"]) | (df[col] > thresholds["max"])
        ).astype(int)
        new_features += 1

    logs.append(
        f"**Feature Engineering:** Created {new_features} new features "
        f"(rolling avg window={window}, rate-of-change, anomaly flags per sensor)"
    )

    return df, logs


def _generate_synthetic_labels(df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate synthetic failure labels from threshold-based rules.
    Label = 1 (failure risk) if:
    - >= SYNTHETIC_LABEL_MIN_ANOMALIES sensors have anomaly flags active, OR
    - Any sensor is in the critical range.
    """
    anomaly_cols = [
        f"{col}_anomaly" for col in SENSOR_COLUMNS if f"{col}_anomaly" in df.columns
    ]

    if not anomaly_cols:
        # Anomaly columns have not been created yet.
        for col in SENSOR_COLUMNS:
            thresholds = SENSOR_THRESHOLDS[col]
            df[f"{col}_anomaly"] = (
                (df[col] < thresholds["min"]) | (df[col] > thresholds["max"])
            ).astype(int)
        anomaly_cols = [f"{col}_anomaly" for col in SENSOR_COLUMNS]

    # Count anomalous sensors per row
    anomaly_count = df[anomaly_cols].sum(axis=1)

    # Check critical range
    critical_mask = pd.Series(False, index=df.index)
    for col in SENSOR_COLUMNS:
        thresholds = SENSOR_THRESHOLDS[col]
        critical_mask = critical_mask | (
            (df[col] < thresholds["critical_min"])
            | (df[col] > thresholds["critical_max"])
        )

    # Label: 1 if enough anomalies OR any critical reading
    df["failure_label"] = (
        (anomaly_count >= SYNTHETIC_LABEL_MIN_ANOMALIES) | critical_mask
    ).astype(int)

    return df


def _synthetic_label_summary(df: pd.DataFrame) -> str:
    """Generate a summary of synthetic labels."""
    count_0 = (df["failure_label"] == 0).sum()
    count_1 = (df["failure_label"] == 1).sum()
    pct_1 = count_1 / len(df) * 100 if len(df) > 0 else 0
    return (
        f"**Synthetic Labels:** Generated from threshold rules - "
        f"Normal: {count_0}, Failure Risk: {count_1} ({pct_1:.1f}%)"
    )


def get_feature_columns(df: pd.DataFrame) -> list[str]:
    """Get the list of feature columns suitable for ML training."""
    exclude = {"timestamp", "failure_label", "maintenance_needed", "id"}
    # Include base sensor columns + engineered features, exclude outlier flags & label
    feature_cols = [
        col for col in df.columns if col not in exclude and not col.endswith("_outlier")
    ]
    return feature_cols


def preprocess_single_reading(payload: dict) -> tuple[dict, list[str]]:
    """
    Validate and clean a single sensor reading (not a full DataFrame).

    This is the streaming / MQTT equivalent of :func:`preprocess`.  It
    checks that sensor values are within plausible ranges and fills any
    missing columns with ``None``.

    Args:
        payload: Dict with keys like ``engine_temp``, ``timestamp``, etc.

    Returns:
        ``(cleaned_dict, errors)`` — ``errors`` is empty if the reading is valid.
    """
    errors = []

    # Normalise keys (lowercase, strip)
    cleaned = {k.strip().lower(): v for k, v in payload.items()}

    # Map aliases
    from core.config import COLUMN_ALIASES

    for alias, canonical in COLUMN_ALIASES.items():
        if alias in cleaned and canonical not in cleaned:
            cleaned[canonical] = cleaned.pop(alias)

    # Ensure required sensor columns exist (fill missing with None)
    for col in SENSOR_COLUMNS:
        if col not in cleaned:
            cleaned[col] = None

    # Validate each sensor value
    for col in SENSOR_COLUMNS:
        val = cleaned.get(col)
        if val is None:
            continue  # missing is acceptable for single readings

        try:
            val = float(val)
            cleaned[col] = val
        except (ValueError, TypeError):
            errors.append(f"{col}: non-numeric value '{val}'")
            continue

        thresholds = SENSOR_THRESHOLDS[col]
        # Soft range check — warn but don't reject
        if val < thresholds["critical_min"] or val > thresholds["critical_max"]:
            from core.logger import get_logger
            get_logger("preprocessing").warning(
                f"{col}: value {val} outside critical range "
                f"[{thresholds['critical_min']}, {thresholds['critical_max']}]"
            )

    # Ensure timestamp
    if "timestamp" not in cleaned or not cleaned["timestamp"]:
        from datetime import datetime

        cleaned["timestamp"] = datetime.now(UTC).isoformat()

    return cleaned, errors
