"""
Vehicle Health Score computation.
Composite score from sensor deviations + model failure probability.
Formula is fully documented and configurable via config.py.
"""

import numpy as np
import pandas as pd

from core.config import HEALTH_BANDS, HEALTH_SCORE_WEIGHTS, SENSOR_COLUMNS, SENSOR_THRESHOLDS


def calculate_health_score(
    sensor_data: pd.Series | dict, failure_prob: float | None = None
) -> dict:
    """
    Calculate a composite vehicle health score (0–100).

    Formula:
        health_score = W_sensor * avg_sensor_health + W_model * (1 - failure_prob) * 100

    Where:
        - avg_sensor_health = mean of per-sensor health scores (0–100 each)
        - per-sensor health = 100 if within normal range, decreasing as it deviates
        - W_sensor and W_model are configurable weights from core.config.py

    If no failure_prob is provided (no model trained yet), uses sensor health alone.

    Returns:
        dict with: score, band_name, band_color, sensor_scores, breakdown
    """
    # Calculate per-sensor health scores
    sensor_scores = {}
    for col in SENSOR_COLUMNS:
        value = sensor_data.get(col)
        if value is None or (isinstance(value, float) and np.isnan(value)):
            sensor_scores[col] = {
                "score": 50,
                "status": "Unknown",
            }  # neutral if missing
            continue

        thresholds = SENSOR_THRESHOLDS[col]
        score = _compute_sensor_health(float(value), thresholds)
        sensor_scores[col] = {
            "score": score,
            "value": float(value),
            "unit": thresholds["unit"],
            "label": thresholds["label"],
            "status": _score_to_status(score),
        }

    # Average sensor health
    avg_sensor_health = np.mean([s["score"] for s in sensor_scores.values()])

    # Composite score
    if failure_prob is not None:
        w_sensor = HEALTH_SCORE_WEIGHTS["sensor_health"]
        w_model = HEALTH_SCORE_WEIGHTS["model_prediction"]
        model_score = (1 - failure_prob) * 100
        health_score = w_sensor * avg_sensor_health + w_model * model_score
    else:
        health_score = avg_sensor_health
        w_sensor = 1.0
        w_model = 0.0
        model_score = None

    health_score = max(0, min(100, health_score))

    # Determine band
    band = _get_band(health_score)

    return {
        "score": round(health_score, 1),
        "band_name": band["name"],
        "band_color": band["color"],
        "sensor_scores": sensor_scores,
        "avg_sensor_health": round(avg_sensor_health, 1),
        "model_score": round(model_score, 1) if model_score is not None else None,
        "breakdown": {
            "sensor_weight": w_sensor,
            "model_weight": w_model,
            "formula": (
                f"{w_sensor:.0%} × Sensor Health ({avg_sensor_health:.1f}) + "
                f"{w_model:.0%} × Model Score ({model_score:.1f})"
                if model_score is not None
                else f"100% × Sensor Health ({avg_sensor_health:.1f}) (no model trained)"
            ),
        },
    }


def calculate_fleet_health(vehicles_data: list[dict]) -> dict:
    """
    Calculate fleet-wide aggregate health metrics.

    Args:
        vehicles_data: list of dicts, each with 'sensor_data' and optional 'failure_prob'

    Returns:
        dict with: avg_score, healthy_count, at_risk_count, critical_count, scores_list
    """
    scores = []
    for v in vehicles_data:
        result = calculate_health_score(v.get("sensor_data", {}), v.get("failure_prob"))
        scores.append(result["score"])

    if not scores:
        return {
            "avg_score": 0,
            "healthy_count": 0,
            "at_risk_count": 0,
            "critical_count": 0,
            "scores_list": [],
        }

    return {
        "avg_score": round(np.mean(scores), 1),
        "healthy_count": sum(1 for s in scores if s >= 80),
        "at_risk_count": sum(1 for s in scores if 60 <= s < 80),
        "critical_count": sum(1 for s in scores if s < 60),
        "scores_list": scores,
    }


def _compute_sensor_health(value: float, thresholds: dict) -> float:
    """
    Compute a 0–100 health score for a single sensor reading.

    - 100: Within normal range
    - Decreasing linearly toward 0 as value approaches critical limits
    - 0: At or beyond critical limit
    """
    normal_min = thresholds["min"]
    normal_max = thresholds["max"]
    critical_min = thresholds["critical_min"]
    critical_max = thresholds["critical_max"]

    # Within normal range
    if normal_min <= value <= normal_max:
        return 100.0

    # Below normal
    if value < normal_min:
        if value <= critical_min:
            return 0.0
        # Linear interpolation between critical_min (0) and normal_min (100)
        range_width = normal_min - critical_min
        if range_width == 0:
            return 0.0
        return max(0, (value - critical_min) / range_width * 100)

    # Above normal
    if value > normal_max:
        if value >= critical_max:
            return 0.0
        # Linear interpolation between normal_max (100) and critical_max (0)
        range_width = critical_max - normal_max
        if range_width == 0:
            return 0.0
        return max(0, (1 - (value - normal_max) / range_width) * 100)

    return 50.0  # fallback


def _score_to_status(score: float) -> str:
    """Convert a sensor health score to a status string."""
    if score >= 95:
        return "Excellent"
    elif score >= 80:
        return "Good"
    elif score >= 60:
        return "Fair"
    elif score >= 30:
        return "Poor"
    else:
        return "Critical"


def _get_band(score: float) -> dict:
    """Get the health band for a given score."""
    for band_name, band_info in HEALTH_BANDS.items():
        if band_info["min"] <= score <= band_info["max"]:
            return {"name": band_name, "color": band_info["color"]}
    return {"name": "Critical", "color": HEALTH_BANDS["Critical"]["color"]}
