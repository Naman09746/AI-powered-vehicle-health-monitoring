"""
MLflow tracking wrapper for experiment logging.

Provides the ``MLflowTracker`` class that wraps MLflow's tracking API with
graceful degradation — if MLflow is unreachable the tracker silently falls
back to a no-op implementation so training never crashes.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from core.config import (
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    MLFLOW_EXPERIMENT_NAME_PREFIX,
    MLFLOW_S3_ENDPOINT_URL,
    MLFLOW_TRACKING_URI,
)

log = logging.getLogger("ml.tracking")


# ---------------------------------------------------------------------------
# Lazy import so the module can be loaded even when mlflow isn't installed
# ---------------------------------------------------------------------------
def _import_mlflow():
    """Import mlflow and configure it. Returns the module or None."""
    try:
        import mlflow
    except ImportError:
        log.info("mlflow package not installed — tracking is disabled")
        return None

    try:
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

        # Configure S3 / MinIO credentials when the endpoint is set
        if MLFLOW_S3_ENDPOINT_URL:
            os.environ.setdefault("MLFLOW_S3_ENDPOINT_URL", MLFLOW_S3_ENDPOINT_URL)
        if AWS_ACCESS_KEY_ID:
            os.environ.setdefault("AWS_ACCESS_KEY_ID", AWS_ACCESS_KEY_ID)
        if AWS_SECRET_ACCESS_KEY:
            os.environ.setdefault("AWS_SECRET_ACCESS_KEY", AWS_SECRET_ACCESS_KEY)

        return mlflow
    except Exception as exc:
        log.warning(
            "MLflow server at %s is not reachable: %s", MLFLOW_TRACKING_URI, exc
        )
        return None


# ---------------------------------------------------------------------------
# No-op implementations used when MLflow is unavailable
# ---------------------------------------------------------------------------
class _NoopRun:
    """Mimics an MLflow ActiveRun but does nothing."""

    def __init__(self):
        self.info = _NoopRunInfo()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class _NoopRunInfo:
    run_id = "noop"


class MLflowTracker:
    """
    Thin wrapper around MLflow's tracking API.

    Usage::

        tracker = MLflowTracker()
        tracker.start_run(experiment_name="vehicle_health", run_name="rf-v1")
        tracker.log_params({"n_estimators": 100})
        tracker.log_metrics({"accuracy": 0.95})
        tracker.log_artifact("/tmp/model.pkl")
        tracker.end_run()

    All public methods are safe to call even when MLflow is unavailable —
    they degrade to no-ops.
    """

    def __init__(self) -> None:
        self._mlflow = _import_mlflow()
        self._active_run = None
        self._enabled = self._mlflow is not None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_run(self, experiment_name: str, run_name: str | None = None) -> None:
        """
        Start a new MLflow run.

        If *experiment_name* does not exist it is created automatically.
        Safe to call when MLflow is unavailable — becomes a no-op.
        """
        if not self._enabled:
            self._active_run = _NoopRun()
            return

        try:
            client = self._mlflow.tracking.MlflowClient()
            exp = client.get_experiment_by_name(experiment_name)
            if exp is None:
                exp_id = client.create_experiment(experiment_name)
                log.info(
                    "Created MLflow experiment '%s' (id=%s)", experiment_name, exp_id
                )
            else:
                exp_id = exp.experiment_id

            self._active_run = self._mlflow.start_run(
                experiment_id=exp_id,
                run_name=run_name,
            )
            log.info(
                "Started MLflow run '%s' (id=%s) in experiment '%s'",
                run_name,
                self._active_run.info.run_id,
                experiment_name,
            )
        except Exception as exc:
            log.warning("Failed to start MLflow run: %s", exc)
            self._active_run = _NoopRun()

    def log_params(self, params: dict[str, Any]) -> None:
        """Log a dictionary of parameters to the current run."""
        if not self._enabled or self._active_run is None:
            return
        try:
            self._mlflow.log_params(params)
        except Exception as exc:
            log.warning("Failed to log params to MLflow: %s", exc)

    def log_metrics(self, metrics: dict[str, float], step: int | None = None) -> None:
        """Log a dictionary of metrics to the current run."""
        if not self._enabled or self._active_run is None:
            return
        try:
            self._mlflow.log_metrics(metrics, step=step)
        except Exception as exc:
            log.warning("Failed to log metrics to MLflow: %s", exc)

    def log_artifact(self, local_path: str) -> None:
        """Upload a local file as an artifact of the current run."""
        if not self._enabled or self._active_run is None:
            return
        try:
            self._mlflow.log_artifact(local_path)
        except Exception as exc:
            log.warning("Failed to log artifact %s to MLflow: %s", local_path, exc)

    def log_model(
        self,
        model,
        model_name: str,
        artifact_path: str = "model",
    ) -> None:
        """
        Log a trained model using MLflow's model registry.

        Args:
            model: A fitted sklearn-compatible estimator.
            model_name: Name to register the model under in the registry.
            artifact_path: Subdirectory within the run's artifact URI.
        """
        if not self._enabled or self._active_run is None:
            return
        try:
            self._mlflow.sklearn.log_model(
                sk_model=model,
                artifact_path=artifact_path,
                registered_model_name=model_name,
            )
            log.info("Logged model '%s' to MLflow (path=%s)", model_name, artifact_path)
        except Exception as exc:
            log.warning("Failed to log model to MLflow: %s", exc)

    def set_tags(self, tags: dict[str, str]) -> None:
        """Set tags on the current run."""
        if not self._enabled or self._active_run is None:
            return
        try:
            self._mlflow.set_tags(tags)
        except Exception as exc:
            log.warning("Failed to set tags on MLflow run: %s", exc)

    def end_run(self) -> None:
        """End the current MLflow run."""
        if not self._enabled or self._active_run is None:
            self._active_run = None
            return
        try:
            self._mlflow.end_run()
        except Exception as exc:
            log.warning("Failed to end MLflow run cleanly: %s", exc)
        finally:
            self._active_run = None

    @property
    def enabled(self) -> bool:
        """Whether MLflow is connected and usable."""
        return self._enabled

    @property
    def active_run_id(self) -> str | None:
        """Return the current run ID, or None if there is no active run."""
        if self._active_run is not None and self._enabled:
            return self._active_run.info.run_id
        return None

    # ------------------------------------------------------------------
    # Helper: build an experiment name from a vehicle_id
    # ------------------------------------------------------------------

    @staticmethod
    def experiment_name_for(vehicle_id: int) -> str:
        """Return the canonical MLflow experiment name for a vehicle."""
        return f"{MLFLOW_EXPERIMENT_NAME_PREFIX}_{vehicle_id}"


# Singleton for cross-module use
tracker = MLflowTracker()
