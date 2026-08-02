"""
Vehicle Health Score computation helper.
Calculates a 0 (critical) – 100 (perfect) health score on-the-fly based on sensor telemetry.
"""

from __future__ import annotations

from typing import Any

HEALTHY_RANGES = {
    "engine_temp": (70.0, 95.0),       # Celsius
    "oil_pressure": (25.0, 65.0),      # PSI
    "coolant_temp": (80.0, 105.0),     # Celsius
    "battery_voltage": (12.4, 14.8),   # Volts
    "engine_rpm": (700.0, 3500.0),     # RPM
    "vibration": (0.0, 0.4),           # g-force
    "tire_pressure": (30.0, 36.0),     # PSI
    "fuel_consumption": (5.0, 14.0),   # L/100km
}

WEIGHTS = {
    "engine_temp": 0.20,
    "oil_pressure": 0.20,
    "coolant_temp": 0.15,
    "battery_voltage": 0.15,
    "engine_rpm": 0.10,
    "vibration": 0.10,
    "tire_pressure": 0.05,
    "fuel_consumption": 0.05,
}


def compute_health_score(reading: dict[str, Any] | None) -> int:
    """
    Computes a vehicle health score between 0 and 100.
    Returns 100 for perfect health, 0 for severe failure conditions.
    """
    if not reading:
        return 100

    total_weight = 0.0
    weighted_score = 0.0

    for sensor, (lo, hi) in HEALTHY_RANGES.items():
        val = reading.get(sensor)
        if val is None:
            continue

        weight = WEIGHTS.get(sensor, 0.05)
        mid = (lo + hi) / 2.0
        half_range = (hi - lo) / 2.0

        if half_range <= 0:
            sensor_score = 1.0
        else:
            # Score decreases proportionally to distance from healthy midpoint
            distance = abs(float(val) - mid)
            sensor_score = max(0.0, 1.0 - (distance / (half_range * 1.5)))

        weighted_score += sensor_score * weight
        total_weight += weight

    if total_weight == 0:
        return 100

    final_score = int(round((weighted_score / total_weight) * 100))
    return max(0, min(100, final_score))


def get_health_status(score: int) -> str:
    """Returns 'good', 'warning', or 'critical' based on health score."""
    if score >= 75:
        return "good"
    if score >= 45:
        return "warning"
    return "critical"


def calculate_health_score(sensor_data: Any = None, failure_prob: float | None = None) -> dict[str, Any]:
    """Compatibility function returning dict with score, band_name, and status."""
    if hasattr(sensor_data, "to_dict"):
        reading_dict = sensor_data.to_dict()
    elif isinstance(sensor_data, dict):
        reading_dict = sensor_data
    else:
        reading_dict = {}

    score = compute_health_score(reading_dict)
    if failure_prob is not None and failure_prob > 0.5:
        score = min(score, int(round((1.0 - float(failure_prob)) * 100)))

    status = get_health_status(score)
    return {
        "score": score,
        "band_name": status.capitalize(),
        "status": status,
    }


def compute_driver_score(readings: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Evaluates driver behavior score (0-100) based on telemetry patterns.
    """
    if not readings:
        return {
            "score": 95,
            "rating": "Smooth & Efficient",
            "harsh_acceleration_events": 0,
            "over_rev_events": 0,
            "excessive_idle_count": 0,
        }

    over_revs = 0
    harsh_accel = 0
    idle_count = 0

    for r in readings:
        rpm = float(r.get("engine_rpm", 0) or 0)
        vibration = float(r.get("vibration", 0) or 0)
        speed = float(r.get("speed", 0) or 0)
        load = float(r.get("engine_load", 0) or 0)

        if rpm > 3800:
            over_revs += 1
        if vibration > 2.2:
            harsh_accel += 1
        if speed < 2 and load > 40:
            idle_count += 1

    deduction = (over_revs * 4) + (harsh_accel * 5) + (idle_count * 3)
    score = max(35, min(100, 100 - deduction))

    if score >= 85:
        rating = "Smooth & Efficient"
    elif score >= 65:
        rating = "Moderate"
    else:
        rating = "Aggressive"

    return {
        "score": score,
        "rating": rating,
        "harsh_acceleration_events": harsh_accel,
        "over_rev_events": over_revs,
        "excessive_idle_count": idle_count,
    }


