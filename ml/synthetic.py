"""
Synthetic data generation for failure-scenario simulation and data augmentation.

Extends ``generate_data.py`` with failure-mode-specific profiles,
SMOTE-like oversampling for rare failures, and noise injection.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core.config import SENSOR_COLUMNS

# ── Optional imbalanced-learn import ──────────────────────────────────────
try:
    from imblearn.over_sampling import SMOTE

    _SMOTE_AVAILABLE = True
except ImportError:
    _SMOTE_AVAILABLE = False
    SMOTE = None  # type: ignore[assignment,misc]

# ---------------------------------------------------------------------------
# Failure profiles — each defines how sensor values evolve over n_rows steps
# ---------------------------------------------------------------------------

# Each profile lists (sensor, start_val_fn, end_val_fn, noise_std)
# where start_val_fn and end_val_fn accept step index (0..n_rows-1)
# and return a float.


def _uniform(lo: float, hi: float) -> float:
    return np.random.uniform(lo, hi)


def _drift_up(start_lo: float, start_hi: float, end_lo: float, end_hi: float):
    """Return a callable that drifts linearly from (start_lo..start_hi) to (end_lo..end_hi)."""

    def _fn(step_idx: int, total: int) -> float:
        frac = step_idx / max(total - 1, 1)
        lo = start_lo + (end_lo - start_lo) * frac
        hi = start_hi + (end_hi - start_hi) * frac
        return np.random.uniform(lo, hi)

    return _fn


def _spike(
    spike_step: int,
    normal_lo: float,
    normal_hi: float,
    spike_lo: float,
    spike_hi: float,
):
    """Normal values except for a sudden spike at spike_step."""

    def _fn(step_idx: int, total: int) -> float:
        if step_idx == spike_step:
            return np.random.uniform(spike_lo, spike_hi)
        return np.random.uniform(normal_lo, normal_hi)

    return _fn


def _intermittent(
    normal_lo: float,
    normal_hi: float,
    fault_lo: float,
    fault_hi: float,
    p_fault: float = 0.15,
):
    """Mostly normal with random intermittent fault spikes."""

    def _fn(step_idx: int, total: int) -> float:
        if np.random.random() < p_fault:
            return np.random.uniform(fault_lo, fault_hi)
        return np.random.uniform(normal_lo, normal_hi)

    return _fn


_FAILURE_PROFILES: dict[str, dict] = {
    "coolant_leak": {
        "label": "Coolant Leak",
        "sensors": {
            "coolant_temp": _drift_up(80, 100, 115, 130),
            "engine_temp": _drift_up(80, 100, 110, 125),
            "engine_load": lambda i, t: np.random.uniform(40, 75),
            "speed": lambda i, t: np.random.uniform(30, 100),
        },
        "noise_std": 1.5,
    },
    "battery_degradation": {
        "label": "Battery Degradation",
        "sensors": {
            "battery_voltage": _drift_up(12.6, 14.4, 10.5, 11.8),
            "engine_rpm": lambda i, t: np.random.uniform(700, 1200),
            "engine_load": lambda i, t: np.random.uniform(20, 60),
        },
        "noise_std": 0.15,
    },
    "oil_pressure_drop": {
        "label": "Oil Pressure Drop",
        "sensors": {
            "oil_pressure": _drift_up(30, 55, 10, 20),
            "engine_temp": _drift_up(80, 100, 105, 120),
            "engine_rpm": lambda i, t: np.random.uniform(800, 3000),
            "engine_load": lambda i, t: np.random.uniform(30, 70),
        },
        "noise_std": 2.0,
    },
    "sensor_spike": {
        "label": "Sensor Spike / Intermittent Fault",
        "sensors": {
            "vibration": _intermittent(0.5, 2.5, 4.5, 6.5, p_fault=0.12),
            "fuel_consumption": _intermittent(6.0, 12.0, 18.0, 28.0, p_fault=0.10),
            "engine_temp": _intermittent(80, 100, 115, 135, p_fault=0.08),
            "coolant_temp": lambda i, t: np.random.uniform(80, 100),
            "speed": lambda i, t: np.random.uniform(20, 110),
        },
        "noise_std": 0.5,
    },
    "normal_operation": {
        "label": "Normal Operation",
        "sensors": {
            "engine_temp": lambda i, t: np.random.uniform(80, 100),
            "oil_pressure": lambda i, t: np.random.uniform(30, 55),
            "coolant_temp": lambda i, t: np.random.uniform(80, 100),
            "engine_rpm": lambda i, t: np.random.uniform(700, 3500),
            "vibration": lambda i, t: np.random.uniform(0.5, 2.5),
            "fuel_consumption": lambda i, t: np.random.uniform(6.0, 12.0),
            "battery_voltage": lambda i, t: np.random.uniform(12.6, 14.4),
            "tire_pressure": lambda i, t: np.random.uniform(30, 35),
            "speed": lambda i, t: np.random.uniform(0, 120),
            "engine_load": lambda i, t: np.random.uniform(15, 70),
        },
        "noise_std": 0.3,
    },
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_failure_scenario(profile: str, n_rows: int = 200) -> pd.DataFrame:
    """Generate sensor data for a specific failure mode.

    Args:
        profile: One of ``"coolant_leak"``, ``"battery_degradation"``,
            ``"oil_pressure_drop"``, ``"sensor_spike"``, ``"normal_operation"``.
        n_rows: Number of rows to generate.

    Returns:
        DataFrame with sensor columns matching ``SENSOR_COLUMNS`` plus
        a ``profile`` column and a ``failure_label`` (1 for failure profiles,
        0 for normal_operation).
    """
    profile_def = _FAILURE_PROFILES.get(profile)
    if profile_def is None:
        valid = list(_FAILURE_PROFILES.keys())
        raise ValueError(f"Unknown profile '{profile}'. Valid: {valid}")

    data: dict[str, list[float]] = {"timestamp": []}
    noise_std = profile_def["noise_std"]

    # Build timestamp index: ~hourly intervals
    start_ts = pd.Timestamp.now() - pd.Timedelta(hours=n_rows)
    data["timestamp"] = [
        (start_ts + pd.Timedelta(hours=i)).isoformat() for i in range(n_rows)
    ]

    # Initialise all sensor columns with normal baseline values
    normal_sensors = _FAILURE_PROFILES["normal_operation"]["sensors"]
    for col in SENSOR_COLUMNS:
        value_fn = normal_sensors.get(col, lambda i, t: 50.0)
        vals = [_round_sensor(col, value_fn(i, n_rows) + np.random.normal(0, 0.3)) for i in range(n_rows)]
        data[col] = vals

    # Populate/override specific sensors modified by this failure profile
    for sensor, value_fn in profile_def["sensors"].items():
        if sensor not in data:
            continue
        vals = []
        for i in range(n_rows):
            base = value_fn(i, n_rows)
            noise = np.random.normal(0, noise_std)
            vals.append(_round_sensor(sensor, base + noise))
        data[sensor] = vals

    df = pd.DataFrame(data)
    df["profile"] = profile
    df["failure_label"] = 1 if profile != "normal_operation" else 0

    return df


def augment_rare_failures(df: pd.DataFrame, target_ratio: float = 0.3) -> pd.DataFrame:
    """Oversample the minority failure class using SMOTE-like synthesis.

    Falls back to random oversampling if ``imbalanced-learn`` is not installed.

    Args:
        df: DataFrame with sensor columns and a ``failure_label`` column.
        target_ratio: Desired minority / majority ratio after augmentation.

    Returns:
        Augmented DataFrame with a balanced ``failure_label`` distribution.
    """
    if "failure_label" not in df.columns:
        raise ValueError("DataFrame must contain a 'failure_label' column.")

    counts = df["failure_label"].value_counts()
    if len(counts) < 2:
        return df  # already a single class — nothing to balance

    majority_label = counts.idxmax()
    minority_label = counts.idxmin()
    majority_count = counts[majority_label]
    minority_count = counts[minority_label]

    desired_minority = int(majority_count * target_ratio)
    if minority_count >= desired_minority:
        return df  # already balanced enough

    n_synthetic = desired_minority - minority_count

    # Prepare numeric feature matrix
    feature_cols = [c for c in SENSOR_COLUMNS if c in df.columns]
    minority_df = df[df["failure_label"] == minority_label].copy()
    X_min = minority_df[feature_cols].fillna(0).values

    use_smote = _SMOTE_AVAILABLE and X_min.shape[0] > 1
    if use_smote:
        # SMOTE on minority class itself to generate neighbours
        try:
            y_min = minority_df["failure_label"].values
            smote = SMOTE(
                sampling_strategy={minority_label: desired_minority},
                random_state=42,
                k_neighbors=min(5, X_min.shape[0] - 1),
            )
            X_res, y_res = smote.fit_resample(X_min, y_min)
            synthetic_df = pd.DataFrame(X_res, columns=feature_cols)
            synthetic_df["failure_label"] = y_res
        except Exception:
            # SMOTE may fail on very small datasets; fall through to simple method
            use_smote = False

    if not use_smote:
        # Fallback: random oversampling with jitter
        synthetic_rows = []
        for _ in range(n_synthetic):
            row = minority_df.sample(1).iloc[0].to_dict()
            for col in feature_cols:
                val = row.get(col, 0)
                if pd.notna(val):
                    noise = np.random.normal(0, abs(val) * 0.02 + 0.01)
                    row[col] = max(0, val + noise)
            synthetic_rows.append(row)
        synthetic_df = pd.DataFrame(synthetic_rows)

    # Ensure consistent columns, then concatenate
    for col in df.columns:
        if col not in synthetic_df.columns:
            synthetic_df[col] = df[col].iloc[0] if len(df) else None

    result = pd.concat([df, synthetic_df], ignore_index=True)
    return result


def add_noise(df: pd.DataFrame, noise_level: float = 0.02) -> pd.DataFrame:
    """Add Gaussian noise to all sensor columns for robustness testing.

    Noise is proportional to the column's standard deviation (scaled by
    ``noise_level``). Columns with zero stddev get absolute noise
    equal to ``noise_level``.

    Args:
        df: Input DataFrame.
        noise_level: Fraction of column stddev to add as noise.

    Returns:
        Copy of ``df`` with noise added to each sensor column.
    """
    result = df.copy()

    for col in SENSOR_COLUMNS:
        if col not in result.columns:
            continue
        vals = result[col]
        std = vals.std()
        if pd.isna(std) or std == 0:
            std = 1.0
        noise = np.random.normal(0, noise_level * std, size=len(vals))
        # NaN-safe: only add noise to non-null cells
        mask = vals.notna()
        result.loc[mask, col] = vals[mask] + noise[: mask.sum()]

    return result


# ── Internal helpers ──────────────────────────────────────────────────────


def _round_sensor(sensor: str, value: float) -> float:
    if sensor in ("engine_rpm", "speed"):
        return round(value, 0)
    elif sensor == "battery_voltage":
        return round(value, 2)
    return round(value, 1)
