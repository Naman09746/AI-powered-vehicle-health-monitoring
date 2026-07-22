"""Automated data quality reports on ingest."""

from typing import Any

import pandas as pd

from core.config import SENSOR_COLUMNS, SENSOR_THRESHOLDS


def generate_quality_report(df: pd.DataFrame) -> dict[str, Any]:
    """Generate a comprehensive data quality report for sensor data."""
    report: dict[str, Any] = {
        "summary": {
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "memory_kb": round(df.memory_usage(deep=True).sum() / 1024, 1),
            "duplicate_rows": int(df.duplicated().sum()),
        },
        "columns": {},
        "sensor_health": {},
        "drift_indicators": {},
        "quality_score": 0.0,
    }

    # Per-column stats for sensor columns
    for col in SENSOR_COLUMNS:
        if col not in df.columns:
            continue
        col_data = df[col]
        non_null = col_data.dropna()
        col_report: dict[str, Any] = {
            "null_count": int(col_data.isna().sum()),
            "null_pct": round(float(col_data.isna().mean() * 100), 1),
            "dtype": str(col_data.dtype),
            "unique": int(non_null.nunique()) if len(non_null) > 0 else 0,
        }

        if len(non_null) > 0:
            col_report.update(
                {
                    "min": round(float(non_null.min()), 2),
                    "max": round(float(non_null.max()), 2),
                    "mean": round(float(non_null.mean()), 2),
                    "std": round(float(non_null.std()), 2),
                    "p1": round(float(non_null.quantile(0.01)), 2),
                    "p99": round(float(non_null.quantile(0.99)), 2),
                }
            )

            # Check against sensor thresholds
            thresholds = SENSOR_THRESHOLDS.get(col)
            if thresholds:
                outside_range = (
                    (non_null < thresholds["min"]) | (non_null > thresholds["max"])
                ).sum()
                critical = (
                    (non_null < thresholds.get("critical_min", 0))
                    | (non_null > thresholds.get("critical_max", 999))
                ).sum()
                col_report["outside_normal_range"] = int(outside_range)
                col_report["outside_normal_pct"] = round(
                    float(outside_range / len(non_null) * 100), 1
                )
                col_report["critical_values"] = int(critical)

        report["columns"][col] = col_report

    # Sensor health
    total_warnings = 0
    for col, cr in report["columns"].items():
        if cr.get("critical_values", 0) > 0:
            total_warnings += 3
        elif cr.get("outside_normal_range", 0) > 0:
            total_warnings += 1
        if cr.get("null_pct", 0) > 10:
            total_warnings += 1

    max_warnings = len(SENSOR_COLUMNS) * 3
    report["quality_score"] = round(
        max(0, 100 - (total_warnings / max_warnings * 100)), 1
    )
    report["sensor_health"] = {
        "sensors_with_anomalies": sum(
            1
            for c in report["columns"].values()
            if c.get("outside_normal_range", 0) > 0
        ),
        "total_sensors": len(SENSOR_COLUMNS),
        "warning_level": "good"
        if report["quality_score"] >= 80
        else "fair"
        if report["quality_score"] >= 50
        else "poor",
    }

    return report


def compare_with_baseline(current_report: dict, baseline_report: dict) -> dict:
    """Compare current quality report against a baseline to detect drift."""
    changes = {}
    for col in SENSOR_COLUMNS:
        cur = current_report.get("columns", {}).get(col, {})
        base = baseline_report.get("columns", {}).get(col, {})
        if cur and base and "mean" in cur and "mean" in base:
            mean_shift = abs(cur["mean"] - base["mean"])
            std = base.get("std", 1) or 1
            changes[col] = {
                "mean_shift": round(mean_shift, 3),
                "std_devs": round(mean_shift / std, 2),
                "drifted": mean_shift > 2 * std,
            }
    return {
        "drifted_columns": [c for c, v in changes.items() if v.get("drifted")],
        "total_drifted": sum(1 for v in changes.values() if v.get("drifted")),
        "changes": changes,
    }
