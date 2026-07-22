"""
Synthetic sensor data generation module.
Provides row-by-row and batch realistic data generation for vehicle health monitoring.
"""

from __future__ import annotations

import random
import time
from typing import Any

import numpy as np
import pandas as pd

from core.config import SENSOR_COLUMNS

BASE_RANGES: dict[str, tuple[float, float]] = {
    "engine_temp": (80.0, 98.0),
    "oil_pressure": (35.0, 50.0),
    "coolant_temp": (82.0, 95.0),
    "engine_rpm": (800.0, 3000.0),
    "vibration": (0.5, 2.0),
    "fuel_consumption": (6.0, 11.0),
    "battery_voltage": (12.8, 14.2),
    "tire_pressure": (30.0, 34.0),
    "speed": (0.0, 110.0),
    "engine_load": (20.0, 65.0),
}


def generate_realistic_row(
    vehicle_profile: str = "normal_operation",
    tick: int = 0,
    seed: int | None = None,
) -> dict[str, Any]:
    """
    Generate a single realistic sensor reading dict for a given vehicle profile and tick.
    """
    if seed is not None:
        np.random.seed((seed + tick) % 2**32)
        random.seed((seed + tick) % 2**32)

    profile = (vehicle_profile or "normal_operation").lower()
    row: dict[str, Any] = {}

    for sensor in SENSOR_COLUMNS:
        lo, hi = BASE_RANGES.get(sensor, (10.0, 50.0))
        val = float(np.random.uniform(lo, hi))

        # Apply profile modifiers
        if profile in ("degrading", "coolant_leak") and sensor in ("engine_temp", "coolant_temp"):
            drift = min(tick * 0.5, 30.0)
            val += drift
        elif profile in ("battery_degradation",) and sensor == "battery_voltage":
            drift = min(tick * 0.05, 3.0)
            val -= drift
        elif profile in ("critical", "oil_pressure_drop") and sensor == "oil_pressure":
            val = max(5.0, val - min(tick * 0.8, 25.0))
        elif profile in ("intermittent_fault", "sensor_spike") and random.random() < 0.2:
            if sensor in ("vibration", "engine_temp"):
                val *= 1.8

        # Rounding
        if sensor in ("engine_rpm", "speed"):
            val = round(val, 0)
        elif sensor == "battery_voltage":
            val = round(val, 2)
        else:
            val = round(val, 1)

        row[sensor] = val

    return row


def generate_sample_data(
    n_rows: int = 20,
    seed: int | None = 42,
    profile: str = "normal_operation",
) -> pd.DataFrame:
    """
    Generate a DataFrame of sample sensor readings.
    """
    rows = []
    base_ts = time.time() - (n_rows * 60)
    for i in range(n_rows):
        r = generate_realistic_row(vehicle_profile=profile, tick=i, seed=seed)
        r["timestamp"] = pd.Timestamp(base_ts + i * 60, unit="s").isoformat()
        rows.append(r)

    df = pd.DataFrame(rows)
    cols = ["timestamp"] + [c for c in SENSOR_COLUMNS if c in df.columns]
    return df[cols]
