"""Root cause analysis — sensor correlation & failure attribution (AF-10)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from core.config import SENSOR_COLUMNS, SENSOR_THRESHOLDS


def analyze_sensor_correlations(readings_df: pd.DataFrame) -> dict[str, Any]:
    """Analyze sensor correlations to identify likely root causes.

    Computes pairwise correlations and flags strong relationships
    that suggest cascading failures.
    """

    sensor_cols = [c for c in SENSOR_COLUMNS if c in readings_df.columns]
    if len(readings_df) < 10 or len(sensor_cols) < 2:
        return {"correlations": [], "root_causes": [], "confidence": 0}

    corr_matrix = readings_df[sensor_cols].corr()
    high_corrs = []

    for i, col1 in enumerate(sensor_cols):
        for col2 in sensor_cols[i + 1 :]:
            val = corr_matrix.loc[col1, col2]
            if abs(val) > 0.7:
                high_corrs.append(
                    {
                        "sensor_a": col1,
                        "label_a": SENSOR_THRESHOLDS.get(col1, {}).get("label", col1),
                        "sensor_b": col2,
                        "label_b": SENSOR_THRESHOLDS.get(col2, {}).get("label", col2),
                        "correlation": round(float(val), 3),
                        "direction": "positive" if val > 0 else "negative",
                        "strength": "strong" if abs(val) > 0.85 else "moderate",
                    }
                )

    # Find root causes: sensors that deviate first
    root_causes = _find_early_deviators(readings_df, sensor_cols)

    return {
        "pairwise_correlations": high_corrs,
        "root_causes": root_causes,
        "total_correlations": len(high_corrs),
        "analysis_depth": f"{len(readings_df)} readings across {len(sensor_cols)} sensors",
    }


def _find_early_deviators(df, sensor_cols: list[str]) -> list[dict]:
    """Identify which sensors deviated first (earliest root causes)."""
    results = []
    for col in sensor_cols:
        thresholds = SENSOR_THRESHOLDS.get(col)
        if not thresholds:
            continue
        deviations = []
        for idx, row in df.iterrows():
            val = row[col]
            if val is None:
                continue
            if val > thresholds["max"] or val < thresholds["min"]:
                deviations.append(
                    {
                        "index": idx,
                        "value": float(val),
                        "magnitude": abs(float(val) - thresholds["max"])
                        if val > thresholds["max"]
                        else abs(float(val) - thresholds["min"]),
                    }
                )
        if deviations:
            results.append(
                {
                    "sensor": col,
                    "label": thresholds.get("label", col),
                    "first_deviation_at": deviations[0]["index"],
                    "peak_deviation": max(d["magnitude"] for d in deviations),
                    "deviation_count": len(deviations),
                }
            )

    results.sort(key=lambda r: r["first_deviation_at"])
    return results[:5]


def trace_failure_chain(
    anomaly_sensors: list[str], correlations: list[dict]
) -> dict[str, Any]:
    """Trace likely failure propagation path from anomalous sensors."""
    if not anomaly_sensors:
        return {"chain": [], "likely_root": None}

    # Find the sensor most correlated with others as likely root
    sensor_scores = {s: 0 for s in anomaly_sensors}
    for c in correlations:
        a, b = c.get("sensor_a"), c.get("sensor_b")
        if a in sensor_scores:
            sensor_scores[a] += abs(c["correlation"])
        if b in sensor_scores:
            sensor_scores[b] += abs(c["correlation"])

    likely_root = max(sensor_scores, key=sensor_scores.get) if sensor_scores else None

    chain = [
        {
            "step": i + 1,
            "sensor": s,
            "role": "root cause" if s == likely_root else "affected",
        }
        for i, s in enumerate(anomaly_sensors)
    ]

    return {
        "chain": chain,
        "likely_root": likely_root,
        "confidence": "high" if sensor_scores.get(likely_root, 0) > 2 else "medium",
    }
