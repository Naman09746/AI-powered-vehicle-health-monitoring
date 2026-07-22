"""
Anomaly detection for vehicle sensor data.

Provides three detectors that range from lightweight statistical methods
to ML-backed isolation forests, plus an ensemble that combines them.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core.config import SENSOR_COLUMNS, SENSOR_THRESHOLDS

# ── Optional sklearn import ───────────────────────────────────────────────
try:
    from sklearn.ensemble import IsolationForest

    _SKLEARN_AVAILABLE = True
except ImportError:
    IsolationForest = None  # type: ignore[assignment,misc]
    _SKLEARN_AVAILABLE = False


# ===========================================================================
# Isolation Forest Detector
# ===========================================================================


class IsolationForestDetector:
    """Anomaly detector based on sklearn's IsolationForest.

    Falls back to a no-op stub if sklearn is not installed.
    """

    def __init__(
        self,
        contamination: float = 0.1,
        random_state: int = 42,
        n_estimators: int = 100,
    ):
        self.contamination = contamination
        self.random_state = random_state
        self.n_estimators = n_estimators
        self._model: IsolationForest | None = None
        self._fitted = False

    def train(self, X: np.ndarray) -> IsolationForestDetector:
        """Fit the detector on normal sensor data."""
        if not _SKLEARN_AVAILABLE:
            raise RuntimeError(
                "sklearn is not installed. Install it with: pip install scikit-learn"
            )
        self._model = IsolationForest(
            contamination=self.contamination,
            random_state=self.random_state,
            n_estimators=self.n_estimators,
        )
        self._model.fit(X)
        self._fitted = True
        return self

    def predict(self, X: np.ndarray) -> list[int]:
        """Return -1 for anomaly, 1 for normal."""
        if not self._fitted or self._model is None:
            raise RuntimeError("Detector must be trained before calling predict().")
        return self._model.predict(X).tolist()  # type: ignore[no-any-return]

    def get_anomaly_score(self, X: np.ndarray) -> list[float]:
        """Return raw anomaly scores (lower = more anomalous)."""
        if not self._fitted or self._model is None:
            raise RuntimeError(
                "Detector must be trained before calling get_anomaly_score()."
            )
        return self._model.score_samples(X).tolist()  # type: ignore[no-any-return]


# ===========================================================================
# Statistical Detector (z-score / IQR)
# ===========================================================================


class StatisticalDetector:
    """Simple threshold-based anomaly detection using config SENSOR_THRESHOLDS."""

    @staticmethod
    def detect(sensor_data: dict) -> dict:
        """Flag sensors whose values fall outside normal thresholds.

        Args:
            sensor_data: dict mapping sensor name -> current value.

        Returns:
            dict with flagged_sensors, total_flagged, all_normal flag.
        """
        flagged: list[dict] = []

        for sensor, value in sensor_data.items():
            if sensor not in SENSOR_THRESHOLDS:
                continue
            th = SENSOR_THRESHOLDS[sensor]
            lo, hi = th["min"], th["max"]
            crit_lo, crit_hi = th["critical_min"], th["critical_max"]

            if value < crit_lo or value > crit_hi:
                severity = "critical"
            elif value < lo or value > hi:
                severity = "warning"
            else:
                continue

            flagged.append(
                {
                    "sensor": sensor,
                    "label": th["label"],
                    "value": value,
                    "normal_range": f"{lo} - {hi}",
                    "severity": severity,
                    "unit": th["unit"],
                }
            )

        return {
            "flagged_sensors": flagged,
            "total_flagged": len(flagged),
            "all_normal": len(flagged) == 0,
        }

    @staticmethod
    def get_deviation_scores(readings_df: pd.DataFrame) -> dict:
        """Compute per-sensor deviation metrics across a DataFrame of readings.

        For each sensor the normalised deviation (distance from range centre
        divided by half the range width) is calculated and aggregated.

        Args:
            readings_df: DataFrame with sensor columns matching SENSOR_COLUMNS.

        Returns:
            dict keyed by sensor with mean_deviation, max_deviation,
            pct_outside_range, and status.
        """
        results: dict[str, dict] = {}

        for sensor in SENSOR_COLUMNS:
            if sensor not in readings_df.columns:
                continue

            th = SENSOR_THRESHOLDS[sensor]
            lo, hi = th["min"], th["max"]
            centre = (lo + hi) / 2.0
            half_range = (hi - lo) / 2.0

            vals = readings_df[sensor].dropna().values
            if len(vals) == 0:
                continue

            # Normalised deviation: 0 at centre, 1 at normal boundary, >1 outside
            deviations = np.abs((vals - centre) / half_range)
            outside = np.sum((vals < lo) | (vals > hi))

            mean_dev = float(np.mean(deviations))
            max_dev = float(np.max(deviations))

            if mean_dev > 1.5:
                status = "critical"
            elif mean_dev > 1.0:
                status = "warning"
            elif max_dev > 1.0:
                status = "intermittent"
            else:
                status = "normal"

            results[sensor] = {
                "label": th["label"],
                "unit": th["unit"],
                "mean_deviation": round(mean_dev, 4),
                "max_deviation": round(max_dev, 4),
                "pct_outside_range": round(float(outside / len(vals) * 100), 2),
                "status": status,
            }

        return results


# ===========================================================================
# Ensemble Anomaly Detector
# ===========================================================================


class EnsembleAnomalyDetector:
    """Combines IsolationForest (when available) with StatisticalDetector."""

    def __init__(self, isolation_kwargs: dict | None = None):
        self._isolation_kwargs = isolation_kwargs or {}
        self._if_detector: IsolationForestDetector | None = None
        self._stat_detector = StatisticalDetector()
        self._fitted = False

    def train(self, X: np.ndarray) -> EnsembleAnomalyDetector:
        """Train the IsolationForest component (if sklearn is available)."""
        if _SKLEARN_AVAILABLE:
            self._if_detector = IsolationForestDetector(**self._isolation_kwargs)
            self._if_detector.train(X)
            self._fitted = True
        return self

    def analyze(self, readings_df: pd.DataFrame) -> dict:
        """Run combined analysis on a DataFrame of sensor readings.

        Args:
            readings_df: DataFrame with sensor columns matching SENSOR_COLUMNS.

        Returns:
            dict with:
            - flagged_readings: rows flagged by either detector
            - anomaly_scores: per-row anomaly scores (-1 / 1) if IF available
            - sensor_deviations: per-sensor deviation stats
            - severity: overall severity assessment
            - methods_used: list of detector names that ran
        """
        methods_used: list[str] = []
        anomaly_labels: list[int] | None = None
        anomaly_scores: list[float] | None = None
        flagged_indices: set[int] = set()

        # ── IsolationForest pass ──
        if self._fitted and self._if_detector is not None:
            methods_used.append("isolation_forest")
            X = readings_df[SENSOR_COLUMNS].fillna(0).values
            anomaly_labels = self._if_detector.predict(X)
            anomaly_scores = self._if_detector.get_anomaly_score(X)
            flagged_indices.update(
                i for i, lbl in enumerate(anomaly_labels) if lbl == -1
            )

        # ── Statistical pass ──
        methods_used.append("statistical")
        try:
            deviation_results = self._stat_detector.get_deviation_scores(readings_df)
        except Exception:
            deviation_results = {}

        # Per-row statistical flagging: any sensor outside normal range
        for i, row in readings_df.iterrows():
            for sensor in SENSOR_COLUMNS:
                if sensor not in row or pd.isna(row[sensor]):
                    continue
                val = row[sensor]
                th = SENSOR_THRESHOLDS.get(sensor)
                if th is None:
                    continue
                if val < th["min"] or val > th["max"]:
                    flagged_indices.add(i)
                    break

        # ── Build per-flagged-row detail ──
        flagged_readings: list[dict] = []
        for i in sorted(flagged_indices):
            row = readings_df.iloc[i]
            entry: dict = {
                "index": i,
                "timestamp": str(row.get("timestamp", "")),
            }
            # Include sensor values that are out of range
            out_of_range = {}
            for sensor in SENSOR_COLUMNS:
                if sensor not in row or pd.isna(row[sensor]):
                    continue
                val = row[sensor]
                th = SENSOR_THRESHOLDS.get(sensor)
                if th and (val < th["min"] or val > th["max"]):
                    out_of_range[sensor] = {
                        "value": val,
                        "normal_range": f"{th['min']} - {th['max']}",
                    }
            entry["out_of_range_sensors"] = out_of_range
            if anomaly_scores is not None and i < len(anomaly_scores):
                entry["anomaly_score"] = round(anomaly_scores[i], 4)
                entry["is_anomaly"] = (
                    anomaly_labels[i] == -1 if anomaly_labels else None
                )
            flagged_readings.append(entry)

        # ── Overall severity ──
        n_rows = len(readings_df)
        n_flagged = len(flagged_indices)
        ratio = n_flagged / n_rows if n_rows > 0 else 0

        if ratio > 0.3:
            severity = "critical"
        elif ratio > 0.1:
            severity = "warning"
        elif n_flagged > 0:
            severity = "minor"
        else:
            severity = "normal"

        return {
            "flagged_readings": flagged_readings,
            "total_flagged": n_flagged,
            "total_readings": n_rows,
            "anomaly_ratio": round(ratio, 4),
            "severity": severity,
            "sensor_deviations": deviation_results,
            "methods_used": methods_used,
            "sklearn_available": _SKLEARN_AVAILABLE,
        }
