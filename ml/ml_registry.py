"""
Model registry for versioning trained models.

Each model version is stored with:
- Metadata (training date, data hash, performance metrics)
- Feature column list (for schema validation at prediction time)
- Champion vs Challenger designation

The registry manages the lifecycle:

    register()          → save a new model (always a "challenger")
    promote_champion()  → mark a challenger as the champion
    get_champion()      → retrieve the current champion for a vehicle
    list_models()       → all versions for a vehicle
    rollback()          → revert to the previous champion
"""

from __future__ import annotations

import hashlib
import json

import core.db as database
from core.logger import get_logger

log = get_logger("ml_registry")


class ModelRegistry:
    """Manages model versioning with champion/challenger semantics."""

    # ── Register ─────────────────────────────────────────────────────────

    def register(self, model_result: dict, vehicle_id: int, user_id: int) -> str | None:
        """
        Register a newly trained model.

        The model is saved as a **challenger** — it won't be used for
        predictions until explicitly promoted.

        Args:
            model_result: Dict from ``train_models()``.
            vehicle_id: Vehicle ID.
            user_id: User ID.

        Returns:
            The model_id (as a string) if saved, or None on failure.
        """
        best_result = self._find_best_result(model_result)
        if best_result is None:
            log.warning("No valid model result to register")
            return None

        # Compute training data hash for reproducibility
        data_hash = self._compute_data_hash(model_result)

        # Determine next version number
        current_version = self._next_version(vehicle_id, user_id)

        # Get champion metrics for delta computation
        champion = self.get_champion(vehicle_id, user_id)
        champion_metric = (champion.f1 or 0) if champion else None

        best_metric = (
            best_result["metrics"].get("f1")
            or best_result["metrics"].get("roc_auc")
            or 0
        )
        delta = None
        if champion_metric is not None:
            delta = round(best_metric - champion_metric, 4)

        # Persist
        try:
            tm = database.save_trained_model(
                user_id=user_id,
                vehicle_id=vehicle_id,
                model_name=best_result["name"],
                model_path=best_result["model_path"],
                scaler_path=model_result.get("scaler_path", ""),
                metrics=best_result["metrics"],
                is_best=False,
            )
            # Re-query to attach to a new session, then update registry fields
            session = database.get_session()
            try:
                model = session.query(database.TrainedModel).filter_by(id=tm.id).first()
                if model is None:
                    log.error("Registered model %s not found for update", tm.id)
                    return None
                model.model_version = current_version
                model.training_data_hash = data_hash
                model.feature_columns_json = json.dumps(
                    model_result.get("feature_columns", [])
                )
                model.is_champion = False
                model.challenger_vs_champion_delta = delta
                session.commit()
                log.info(
                    "Registered model v%s for vehicle %s (delta=%s)",
                    current_version,
                    vehicle_id,
                    delta,
                )
                returned_id = str(model.id)
            finally:
                session.close()
            return returned_id
        except Exception:
            log.exception("Failed to register model")
            return None

    # ── Champion management ──────────────────────────────────────────────

    def promote_champion(self, model_id: int, vehicle_id: int, user_id: int) -> bool:
        """
        Promote a challenger model to champion.

        All other models for this vehicle are demoted to non-champion.
        """
        session = database.get_session()
        try:
            # Demote current champion(s)
            session.query(database.TrainedModel).filter(
                database.TrainedModel.vehicle_id == vehicle_id,
                database.TrainedModel.user_id == user_id,
                database.TrainedModel.is_champion,
            ).update({"is_champion": False, "is_best": False})

            # Promote the selected model
            model = (
                session.query(database.TrainedModel)
                .filter_by(
                    id=model_id,
                    vehicle_id=vehicle_id,
                    user_id=user_id,
                )
                .first()
            )
            if not model:
                log.warning("Model %s not found for promotion", model_id)
                return False

            model.is_champion = True
            model.is_best = True
            session.commit()
            log.info(
                "Promoted model %s (v%s) to champion for vehicle %s",
                model_id,
                model.model_version,
                vehicle_id,
            )
            return True
        except Exception:
            session.rollback()
            log.exception("Failed to promote model %s", model_id)
            return False
        finally:
            session.close()

    def get_champion(
        self, vehicle_id: int, user_id: int
    ) -> database.TrainedModel | None:
        """
        Get the current champion model for a vehicle.

        Falls back to ``is_best`` if no champion flag is set (legacy).
        """
        session = database.get_session()
        try:
            model = (
                session.query(database.TrainedModel)
                .filter_by(
                    vehicle_id=vehicle_id,
                    user_id=user_id,
                    is_champion=True,
                )
                .order_by(database.TrainedModel.trained_at.desc())
                .first()
            )
            if model:
                return model
            # Fallback to legacy is_best flag
            return (
                session.query(database.TrainedModel)
                .filter_by(
                    vehicle_id=vehicle_id,
                    user_id=user_id,
                    is_best=True,
                )
                .order_by(database.TrainedModel.trained_at.desc())
                .first()
            )
        finally:
            session.close()

    def list_models(self, vehicle_id: int, user_id: int) -> list[database.TrainedModel]:
        """List all model versions for a vehicle, newest first."""
        session = database.get_session()
        try:
            return (
                session.query(database.TrainedModel)
                .filter_by(
                    vehicle_id=vehicle_id,
                    user_id=user_id,
                )
                .order_by(database.TrainedModel.trained_at.desc())
                .all()
            )
        finally:
            session.close()

    def rollback(self, vehicle_id: int, user_id: int) -> bool:
        """
        Rollback to the previous champion.

        The current champion is demoted and the most recent non-champion
        model is promoted in its place.
        """
        session = database.get_session()
        try:
            models = (
                session.query(database.TrainedModel)
                .filter_by(
                    vehicle_id=vehicle_id,
                    user_id=user_id,
                )
                .order_by(database.TrainedModel.trained_at.desc())
                .all()
            )

            current_champion = None
            previous_candidate = None

            for m in models:
                if m.is_champion:
                    current_champion = m
                elif previous_candidate is None and not m.is_champion:
                    previous_candidate = m

            if current_champion is None or previous_candidate is None:
                log.warning("Cannot rollback — no previous model found")
                return False

            current_champion.is_champion = False
            current_champion.is_best = False
            previous_candidate.is_champion = True
            previous_candidate.is_best = True
            session.commit()
            log.info(
                "Rolled back from v%s to v%s for vehicle %s",
                current_champion.model_version,
                previous_candidate.model_version,
                vehicle_id,
            )
            return True
        except Exception:
            session.rollback()
            log.exception("Rollback failed")
            return False
        finally:
            session.close()

    # ── Internal helpers ─────────────────────────────────────────────────

    def _find_best_result(self, model_result: dict) -> dict | None:
        """Find the best model result from training output."""
        results = model_result.get("results", [])
        if model_result.get("best_model"):
            for r in results:
                if r.get("name") == model_result["best_model"]:
                    return r
        return results[0] if results else None

    def _compute_data_hash(self, model_result: dict) -> str:
        """Compute a reproducible hash for the training data config."""
        raw = json.dumps(
            {
                "feature_columns": model_result.get("feature_columns", []),
                "selection_metric": model_result.get("selection_metric", "f1"),
            },
            sort_keys=True,
        )
        return hashlib.md5(raw.encode()).hexdigest()

    def _next_version(self, vehicle_id: int, user_id: int) -> str:
        """Determine the next semantic version for this vehicle's models."""
        session = database.get_session()
        try:
            latest = (
                session.query(database.TrainedModel)
                .filter_by(
                    vehicle_id=vehicle_id,
                    user_id=user_id,
                )
                .order_by(database.TrainedModel.trained_at.desc())
                .first()
            )
            if latest and latest.model_version:
                parts = latest.model_version.split(".")
                major, minor = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
                return f"{major}.{minor + 1}.0"
            return "1.0.0"
        finally:
            session.close()


# Singleton for cross-module use
registry = ModelRegistry()
