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


DTC_MAP: dict[str, list[str]] = {
    "critical": ["P0300", "P0171", "P0128", "P0217"],
    "degrading": ["P0420", "P0401", "P0442"],
    "intermittent_fault": ["P0455", "P0128"],
    "coolant_leak": ["P0128", "P0217"],
    "oil_pressure_drop": ["P0524"],
    "healthy": [],
    "normal_operation": [],
}

DTC_DESCRIPTIONS: dict[str, str] = {
    "P0300": "Random/Multiple Cylinder Misfire Detected",
    "P0171": "System Too Lean (Bank 1)",
    "P0128": "Coolant Thermostat Below Regulating Temp",
    "P0217": "Engine Coolant Over Temperature Condition",
    "P0420": "Catalyst System Efficiency Below Threshold",
    "P0401": "Exhaust Gas Recirculation (EGR) Insufficient",
    "P0442": "Evaporative Emission System Small Leak",
    "P0455": "Evaporative Emission System Gross Leak",
    "P0524": "Engine Oil Pressure Too Low",
}


import math

VEHICLE_TYPE_BASELINES: dict[str, dict[str, tuple[float, float]]] = {
    "gasoline": {
        "engine_temp": (80.0, 98.0),
        "engine_rpm": (800.0, 3500.0),
        "oil_pressure": (35.0, 55.0),
        "fuel_consumption": (7.0, 12.0),
    },
    "diesel": {
        "engine_temp": (85.0, 105.0),
        "engine_rpm": (600.0, 2400.0),
        "oil_pressure": (45.0, 75.0),
        "fuel_consumption": (12.0, 24.0),
    },
    "hybrid": {
        "engine_temp": (65.0, 88.0),
        "engine_rpm": (0.0, 2800.0),
        "oil_pressure": (30.0, 50.0),
        "fuel_consumption": (3.5, 6.5),
    },
    "electric": {
        "engine_temp": (25.0, 45.0),
        "engine_rpm": (0.0, 6000.0),
        "oil_pressure": (0.0, 0.0),
        "fuel_consumption": (0.0, 0.0),
        "battery_voltage": (350.0, 410.0),
    },
}


def generate_gps_point(vehicle_id: int = 1, tick: int = 0) -> tuple[float, float]:
    """Generates simulated GPS coordinates (lat, lng) moving along a realistic route."""
    base_lat, base_lng = 37.7749, -122.4194
    lat_offset = ((vehicle_id * 17) % 50 - 25) * 0.01
    lng_offset = ((vehicle_id * 31) % 50 - 25) * 0.01

    lat = base_lat + lat_offset + math.sin(tick * 0.1) * 0.005
    lng = base_lng + lng_offset + math.cos(tick * 0.1) * 0.005

    return round(lat, 6), round(lng, 6)


def generate_realistic_row(
    vehicle_profile: str = "normal_operation",
    tick: int = 0,
    seed: int | None = None,
    engine_type: str = "gasoline",
    vehicle_id: int = 1,
) -> dict[str, Any]:
    """
    Generate a single realistic sensor reading dict for a given vehicle profile, tick, and engine type.
    """
    if seed is not None:
        np.random.seed((seed + tick) % 2**32)
        random.seed((seed + tick) % 2**32)

    profile = (vehicle_profile or "normal_operation").lower()
    eng_baseline = VEHICLE_TYPE_BASELINES.get((engine_type or "gasoline").lower(), VEHICLE_TYPE_BASELINES["gasoline"])
    row: dict[str, Any] = {}

    for sensor in SENSOR_COLUMNS:
        lo, hi = eng_baseline.get(sensor, BASE_RANGES.get(sensor, (10.0, 50.0)))
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

    row["dtc_codes"] = DTC_MAP.get(profile, [])
    lat, lng = generate_gps_point(vehicle_id, tick)
    row["latitude"] = lat
    row["longitude"] = lng

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
