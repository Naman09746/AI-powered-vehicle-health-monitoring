"""
Remaining Useful Life (RUL) estimation module.
Extrapolates sensor degradation trends to predict days and mileage remaining before component failure.
"""

from __future__ import annotations

import math
from typing import Any
import pandas as pd
import numpy as np


def estimate_rul(readings_df: pd.DataFrame | list[dict[str, Any]]) -> dict[str, Any]:
    """
    Estimates Remaining Useful Life (RUL) based on recent sensor reading trends and overall health.
    Returns estimated days, estimated km/miles remaining, urgency level, and summary message.
    """
    if isinstance(readings_df, list):
        if not readings_df:
            return {
                "rul_days": None,
                "urgency": "unknown",
                "message": "Insufficient telemetry data for RUL calculation.",
            }
        df = pd.DataFrame(readings_df)
    else:
        df = readings_df

    if df.empty or len(df) < 3:
        return {
            "rul_days": None,
            "urgency": "unknown",
            "message": "Insufficient telemetry data for RUL calculation (minimum 3 readings required).",
        }

    # Calculate degradation trend across engine temp, oil pressure, vibration
    scores = []
    for _, row in df.iterrows():
        temp = float(row.get("engine_temp", 85.0) or 85.0)
        oil = float(row.get("oil_pressure", 40.0) or 40.0)
        vib = float(row.get("vibration", 1.0) or 1.0)

        penalty = 0.0
        if temp > 95.0:
            penalty += (temp - 95.0) * 2.0
        if oil < 30.0:
            penalty += (30.0 - oil) * 2.5
        if vib > 2.0:
            penalty += (vib - 2.0) * 15.0

        scores.append(max(0.0, 100.0 - penalty))

    y = np.array(scores)
    x = np.arange(len(y))

    # Fit linear regression trend
    if len(x) > 1:
        slope, intercept = np.polyfit(x, y, 1)
    else:
        slope, intercept = 0.0, y[-1]

    latest_score = float(y[-1])

    # Dynamic RUL computation bounded by vehicle health status & slope
    if latest_score < 40.0:
        rul_days = 2.0
        urgency = "critical"
        message = "Critical degradation: Failure predicted within 48 hours. Service required immediately."
    elif slope < -0.2:
        # Rapid degradation rate
        steps_left = max(1.0, (latest_score - 30.0) / abs(slope))
        rul_days = min(30.0, max(1.0, round(steps_left * 0.5, 1)))
        urgency = "warning" if rul_days > 5 else "critical"
        message = f"Accelerated wear detected: Estimated {rul_days} operating days before threshold failure."
    elif slope < -0.01:
        # Moderate degradation rate
        steps_left = (latest_score - 30.0) / abs(slope)
        health_cap = max(10.0, round((latest_score / 100.0) * 60.0, 1))
        rul_days = min(health_cap, max(3.0, round(steps_left * 0.2, 1)))
        urgency = "warning" if latest_score < 75 or rul_days < 30 else "good"
        message = f"Predictive Maintenance Forecast: ~{rul_days} operating days remaining before service."
    else:
        # Stable operation - RUL scaled by current health score (max 90 days)
        rul_days = round(min(90.0, max(15.0, (latest_score / 100.0) * 90.0)), 1)
        if latest_score < 75:
            urgency = "warning"
            rul_days = min(rul_days, 35.0)
            message = f"Warning: Sub-optimal vehicle health ({int(latest_score)}%). Estimated ~{rul_days} operating days remaining."
        else:
            urgency = "good"
            message = f"Optimal operating baseline: No accelerated degradation detected (~{rul_days} days clear)."

    estimated_km = int(rul_days * 45.0)  # Average 45 km/day driving rate

    return {
        "rul_days": rul_days,
        "estimated_km_remaining": estimated_km,
        "degradation_rate_per_day": round(abs(float(slope)), 2),
        "urgency": urgency,
        "message": message,
    }

