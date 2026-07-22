"""
ML training, evaluation, model persistence, and prediction.
Supports: Logistic Regression, Decision Tree, Random Forest, XGBoost, SVM.

Enhancements in Phase 4:
- Hyperparameter search (GridSearchCV / RandomizedSearchCV)
- Cross-validation scoring (5-fold stratified)
- Probability calibration via CalibratedClassifierCV
- Data drift detection via KS-test
- Confidence-aware predictions
"""

from __future__ import annotations

import datetime
import os

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import roc_curve
from sklearn.model_selection import StratifiedKFold, cross_val_score

from core.config import ML_CONFIG, MODEL_PARAMS
from core.logger import get_logger
from ml.tracking import tracker
from core.preprocessing import get_feature_columns

log = get_logger("ml_models")

# Ensure models directory exists
MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
os.makedirs(MODELS_DIR, exist_ok=True)


def _get_model_instances() -> dict:
    """Create fresh model instances with configured hyperparameters."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.svm import SVC
    from sklearn.tree import DecisionTreeClassifier
    from xgboost import XGBClassifier

    return {
        "Logistic Regression": LogisticRegression(**MODEL_PARAMS["LogisticRegression"]),
        "Decision Tree": DecisionTreeClassifier(**MODEL_PARAMS["DecisionTree"]),
        "Random Forest": RandomForestClassifier(**MODEL_PARAMS["RandomForest"]),
        "XGBoost": XGBClassifier(**MODEL_PARAMS["XGBoost"]),
        "SVM": SVC(**MODEL_PARAMS["SVM"]),
    }


def validate_training_data(
    df: pd.DataFrame, target_col: str = "failure_label"
) -> tuple[bool, str]:
    """
    Validate that data is suitable for ML training.
    Returns (is_valid, message).
    """

    min_rows = ML_CONFIG["min_rows_for_training"]

    if len(df) < min_rows:
        return False, (
            f"Insufficient data: {len(df)} rows found, minimum {min_rows} required. "
            "Upload more sensor data to enable model training."
        )

    if target_col not in df.columns:
        return False, f"Target column `{target_col}` not found in the data."

    unique_labels = df[target_col].dropna().unique()
    if len(unique_labels) < 2:
        return False, (
            f"Only one class found in `{target_col}` (value: {unique_labels}). "
            "Both normal (0) and failure (1) samples are needed for training."
        )

    return True, "Data is ready for training."


def train_models(
    df: pd.DataFrame,
    user_id: int,
    vehicle_id: int,
    target_col: str = "failure_label",
    model_names: list[str] | None = None,
) -> dict:
    """
    Train multiple classifiers and evaluate them.
    """
    import joblib
    import numpy as np
    from sklearn.metrics import (
        accuracy_score,
        confusion_matrix,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
    )
    from sklearn.model_selection import (
        train_test_split,
    )
    from sklearn.preprocessing import StandardScaler

    # Prepare features
    feature_cols = get_feature_columns(df)

    # Drop rows with NaN in features or target
    train_df = df[feature_cols + [target_col]].dropna()

    X = train_df[feature_cols].values
    y = train_df[target_col].values.astype(int)

    # Train/test split with stratification if possible
    unique_y, y_counts = np.unique(y, return_counts=True)
    min_class_count = min(y_counts) if len(y_counts) > 0 else 0
    use_stratify = y if min_class_count >= 2 else None

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=ML_CONFIG["test_size"],
        random_state=ML_CONFIG["random_state"],
        stratify=use_stratify,
    )

    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Save scaler
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    scaler_path = os.path.join(MODELS_DIR, f"scaler_{user_id}_{timestamp}.pkl")
    joblib.dump(scaler, scaler_path)

    # ── Start MLflow run ─────────────────────────────────────────────
    exp_name = tracker.experiment_name_for(vehicle_id)
    tracker.start_run(experiment_name=exp_name, run_name=f"train_{timestamp}")

    # Compute minority ratio safely (avoids walrus fragility inside dict literal)
    bincounts = np.bincount(y)
    minority_ratio = (
        round(min(bincounts) / max(len(y), 1), 4) if len(bincounts) > 1 else 0.0
    )

    tracker.log_params(
        {
            "test_size": ML_CONFIG["test_size"],
            "random_state": ML_CONFIG["random_state"],
            "min_rows_for_training": ML_CONFIG["min_rows_for_training"],
            "imbalance_threshold": ML_CONFIG["imbalance_threshold"],
            "feature_count": len(feature_cols),
            "training_rows": len(train_df),
            "target_column": target_col,
            "minority_ratio": minority_ratio,
        }
    )
    tracker.set_tags(
        {
            "vehicle_id": str(vehicle_id),
            "user_id": str(user_id),
            "training_timestamp": timestamp,
            "tuning_mode": "none",
        }
    )

    # Get models to train
    all_models = _get_model_instances()
    if model_names:
        models = {name: all_models[name] for name in model_names if name in all_models}
    else:
        models = all_models

    # Check for class imbalance
    use_roc_for_selection = minority_ratio < ML_CONFIG["imbalance_threshold"]
    selection_metric = "roc_auc" if use_roc_for_selection else "f1"

    results = []
    for name, model in models.items():
        try:
            # Train
            model.fit(X_train_scaled, y_train)

            # Predict
            y_pred = model.predict(X_test_scaled)
            y_prob = None
            if hasattr(model, "predict_proba"):
                y_prob = model.predict_proba(X_test_scaled)[:, 1]

            # Metrics
            metrics = {
                "accuracy": round(accuracy_score(y_test, y_pred), 4),
                "precision": round(precision_score(y_test, y_pred, zero_division=0), 4),
                "recall": round(recall_score(y_test, y_pred, zero_division=0), 4),
                "f1": round(f1_score(y_test, y_pred, zero_division=0), 4),
                "roc_auc": round(roc_auc_score(y_test, y_prob), 4)
                if y_prob is not None
                else None,
            }

            # Confusion matrix
            cm = confusion_matrix(y_test, y_pred)

            # ROC curve data
            roc_data = None
            if y_prob is not None:
                fpr, tpr, thresholds = roc_curve(y_test, y_prob)
                roc_data = {"fpr": fpr.tolist(), "tpr": tpr.tolist()}

            # Save model
            model_path = os.path.join(
                MODELS_DIR, f"{name.replace(' ', '_')}_{user_id}_{timestamp}.pkl"
            )
            joblib.dump(model, model_path)

            # ── Log to MLflow ──
            tracker.log_params(
                {
                    f"model.{name}.{k}": str(v)
                    for k, v in MODEL_PARAMS.get(name.replace(" ", ""), {}).items()
                }
            )
            tracker.log_metrics(
                {f"{name}.{k}": v for k, v in metrics.items() if v is not None}
            )
            tracker.log_artifact(model_path)
            tracker.log_artifact(scaler_path)

            results.append(
                {
                    "name": name,
                    "metrics": metrics,
                    "confusion_matrix": cm.tolist(),
                    "roc_data": roc_data,
                    "model_path": model_path,
                }
            )
        except Exception as e:
            log.warning("Model %s failed: %s", name, e)
            results.append(
                {
                    "name": name,
                    "error": str(e),
                    "metrics": None,
                }
            )

    # Determine best model
    valid_results = [r for r in results if r.get("metrics")]
    if not valid_results:
        tracker.set_tags(
            {"best_model": "none", "reason": "No models trained successfully."}
        )
        tracker.end_run()
        return {
            "results": results,
            "best_model": None,
            "best_reason": "No models trained successfully.",
            "scaler_path": scaler_path,
            "feature_columns": feature_cols,
        }

    best = max(valid_results, key=lambda r: r["metrics"].get(selection_metric, 0) or 0)
    best_name = best["name"]
    best_metric_val = best["metrics"][selection_metric]

    if use_roc_for_selection:
        reason = (
            f"**{best_name}** selected as best model based on **ROC-AUC = {best_metric_val:.4f}** "
            f"(class imbalance detected - minority class is {minority_ratio:.1%} of data, "
            "so ROC-AUC is preferred over F1)"
        )
    else:
        reason = (
            f"**{best_name}** selected as best model based on **F1 Score = {best_metric_val:.4f}** "
            f"(balanced classes - minority class is {minority_ratio:.1%} of data)"
        )

    # ── Finalise MLflow run ───────────────────────────────────────────
    tracker.set_tags(
        {
            "best_model": best_name,
            "selection_metric": selection_metric,
            "best_metric_value": str(best_metric_val),
        }
    )
    tracker.log_metrics(
        {
            "best_accuracy": best["metrics"].get("accuracy", 0),
            "best_precision": best["metrics"].get("precision", 0),
            "best_recall": best["metrics"].get("recall", 0),
            "best_f1": best["metrics"].get("f1", 0),
            "best_roc_auc": best["metrics"].get("roc_auc", 0) or 0,
        }
    )
    tracker.end_run()

    return {
        "results": results,
        "best_model": best_name,
        "best_reason": reason,
        "scaler_path": scaler_path,
        "feature_columns": feature_cols,
        "selection_metric": selection_metric,
    }


import functools

@functools.lru_cache(maxsize=16)
def _load_joblib_cached(path: str):
    import joblib
    return joblib.load(path)


def predict(
    model_path: str,
    scaler_path: str,
    input_df: pd.DataFrame,
    feature_columns: list[str],
) -> dict:
    """
    Make a prediction using a saved model.
    """
    model = _load_joblib_cached(model_path)
    scaler = _load_joblib_cached(scaler_path)

    # Ensure we have all required feature columns
    available_features = [col for col in feature_columns if col in input_df.columns]
    missing_features = set(feature_columns) - set(available_features)

    if missing_features:
        # Fill missing with 0 (they'll be scaled anyway)
        for col in missing_features:
            input_df[col] = 0

    X = input_df[feature_columns].values
    X_scaled = scaler.transform(X)

    # Get prediction and probability
    model.predict(X_scaled)

    failure_prob = 0.5  # default
    if hasattr(model, "predict_proba"):
        probs = model.predict_proba(X_scaled)
        # Average across all input rows
        avg_prob = probs[:, 1].mean()
        failure_prob = float(avg_prob)
    elif hasattr(model, "decision_function"):
        # SVM fallback: map decision function to probability-like score.
        decision = model.decision_function(X_scaled).mean()
        failure_prob = float(1 / (1 + np.exp(-decision)))

    # Determine class
    from core.utils import get_failure_class

    failure_class = get_failure_class(failure_prob)

    # Get feature importances
    importances = _get_feature_importances(model, feature_columns, X_scaled)

    return {
        "prediction_class": failure_class["label"],
        "prediction_icon": failure_class["icon"],
        "prediction_color": failure_class["color"],
        "failure_prob": failure_prob,
        "confidence": max(failure_prob, 1 - failure_prob),
        "feature_importances": importances,
    }


def _get_feature_importances(
    model, feature_columns: list[str], X_scaled: np.ndarray
) -> list[dict]:
    """Extract feature importances from a trained model."""
    import numpy as np

    importances = []

    if hasattr(model, "feature_importances_"):
        # Tree-based models
        raw_importances = model.feature_importances_
        total = raw_importances.sum()
        for feat, imp in zip(feature_columns, raw_importances, strict=False):
            importances.append(
                {
                    "feature": feat,
                    "importance": float(imp),
                    "contribution_pct": float(imp / total * 100) if total > 0 else 0,
                }
            )
    elif hasattr(model, "coef_"):
        # Linear models
        raw_importances = np.abs(model.coef_[0])
        total = raw_importances.sum()
        for feat, imp in zip(feature_columns, raw_importances, strict=False):
            importances.append(
                {
                    "feature": feat,
                    "importance": float(imp),
                    "contribution_pct": float(imp / total * 100) if total > 0 else 0,
                }
            )
    else:
        # Fallback: no importances available.
        return []

    # Sort by importance, return top 10
    importances.sort(key=lambda x: x["importance"], reverse=True)
    return importances[:10]


# ──────────────────────────────────────────────
# Hyperparameter search grids
# ──────────────────────────────────────────────

HPARAM_GRIDS = {
    "Random Forest": {
        "n_estimators": [50, 100, 200],
        "max_depth": [5, 10, 15, None],
        "min_samples_split": [2, 5, 10],
        "min_samples_leaf": [1, 2, 4],
    },
    "XGBoost": {
        "n_estimators": [50, 100, 200],
        "max_depth": [3, 6, 10],
        "learning_rate": [0.01, 0.1, 0.3],
        "subsample": [0.8, 1.0],
        "colsample_bytree": [0.8, 1.0],
    },
    "Logistic Regression": {
        "C": [0.01, 0.1, 1.0, 10.0],
        "penalty": ["l2"],
        "solver": ["lbfgs"],
    },
    "Decision Tree": {
        "max_depth": [3, 5, 10, 15, None],
        "min_samples_split": [2, 5, 10, 20],
        "min_samples_leaf": [1, 2, 4],
        "criterion": ["gini", "entropy"],
    },
    "SVM": {
        "C": [0.1, 1.0, 10.0],
        "kernel": ["rbf", "linear"],
        "gamma": ["scale", "auto"],
    },
}


def train_models_with_tuning(
    df: pd.DataFrame,
    user_id: int,
    vehicle_id: int,
    target_col: str = "failure_label",
    model_names: list[str] | None = None,
    tuning_mode: str = "quick",
    n_iter_search: int = 10,
) -> dict:
    """
    Train models with optional hyperparameter tuning and cross-validation.
    """
    import joblib
    import numpy as np
    from sklearn.metrics import (
        accuracy_score,
        confusion_matrix,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
    )
    from sklearn.model_selection import (
        GridSearchCV,
        RandomizedSearchCV,
        train_test_split,
    )
    from sklearn.preprocessing import StandardScaler

    # Prepare features
    feature_cols = get_feature_columns(df)
    train_df = df[feature_cols + [target_col]].dropna()
    X = train_df[feature_cols].values
    y = train_df[target_col].values.astype(int)

    # Train/test split with stratification if possible
    unique_y, y_counts = np.unique(y, return_counts=True)
    min_class_count = min(y_counts) if len(y_counts) > 0 else 0
    use_stratify = y if min_class_count >= 2 else None

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=ML_CONFIG["test_size"],
        random_state=ML_CONFIG["random_state"],
        stratify=use_stratify,
    )

    # Scale
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    scaler_path = os.path.join(MODELS_DIR, f"scaler_{user_id}_{timestamp}.pkl")
    joblib.dump(scaler, scaler_path)

    # ── Start MLflow run ─────────────────────────────────────────────
    exp_name = tracker.experiment_name_for(vehicle_id)
    tracker.start_run(experiment_name=exp_name, run_name=f"train_tuned_{timestamp}")

    # Compute minority ratio safely
    bincounts = np.bincount(y)
    minority_ratio = (
        round(min(bincounts) / max(len(y), 1), 4) if len(bincounts) > 1 else 0.0
    )

    tracker.log_params(
        {
            "test_size": ML_CONFIG["test_size"],
            "random_state": ML_CONFIG["random_state"],
            "min_rows_for_training": ML_CONFIG["min_rows_for_training"],
            "imbalance_threshold": ML_CONFIG["imbalance_threshold"],
            "feature_count": len(feature_cols),
            "training_rows": len(train_df),
            "target_column": target_col,
            "minority_ratio": minority_ratio,
            "tuning_mode": tuning_mode,
            "n_iter_search": n_iter_search,
        }
    )
    tracker.set_tags(
        {
            "vehicle_id": str(vehicle_id),
            "user_id": str(user_id),
            "training_timestamp": timestamp,
            "tuning_mode": tuning_mode,
        }
    )

    # Imbalance check
    use_roc_for_selection = minority_ratio < ML_CONFIG["imbalance_threshold"]
    selection_metric = "roc_auc" if use_roc_for_selection else "f1"

    # Determine which models to train
    all_base = _get_model_instances()
    if model_names:
        models_to_train = {n: all_base[n] for n in model_names if n in all_base}
    else:
        models_to_train = all_base

    results = []
    for name, base_model in models_to_train.items():
        try:
            hparams = HPARAM_GRIDS.get(name)
            model = base_model

            # ── Hyperparameter tuning ──
            tuning_params = None
            if hparams and len(hparams) > 1:
                if tuning_mode == "thorough":
                    searcher = GridSearchCV(
                        base_model,
                        hparams,
                        cv=3,
                        scoring=selection_metric,
                        n_jobs=-1,
                        verbose=0,
                    )
                else:
                    searcher = RandomizedSearchCV(
                        base_model,
                        hparams,
                        n_iter=min(n_iter_search, 20),
                        cv=3,
                        scoring=selection_metric,
                        n_jobs=-1,
                        verbose=0,
                        random_state=42,
                    )
                searcher.fit(X_train_scaled, y_train)
                model = searcher.best_estimator_
                tuning_params = searcher.best_params_

            # ── Train ──
            model.fit(X_train_scaled, y_train)

            # ── Calibrate probabilities ──
            if hasattr(model, "predict_proba"):
                calibrated = CalibratedClassifierCV(model, cv=3, method="sigmoid")
                calibrated.fit(X_train_scaled, y_train)
                model = calibrated

            # ── 5-fold cross-validation ──
            cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
            cv_scores = cross_val_score(
                model,
                X_train_scaled,
                y_train,
                cv=cv,
                scoring=selection_metric,
            )

            # ── Evaluate on test set ──
            y_pred = model.predict(X_test_scaled)
            y_prob = None
            if hasattr(model, "predict_proba"):
                y_prob = model.predict_proba(X_test_scaled)[:, 1]

            metrics = {
                "accuracy": round(accuracy_score(y_test, y_pred), 4),
                "precision": round(precision_score(y_test, y_pred, zero_division=0), 4),
                "recall": round(recall_score(y_test, y_pred, zero_division=0), 4),
                "f1": round(f1_score(y_test, y_pred, zero_division=0), 4),
                "roc_auc": round(roc_auc_score(y_test, y_prob), 4)
                if y_prob is not None
                else None,
            }

            cm = confusion_matrix(y_test, y_pred)

            roc_data = None
            if y_prob is not None:
                fpr, tpr, _ = roc_curve(y_test, y_prob)
                roc_data = {"fpr": fpr.tolist(), "tpr": tpr.tolist()}

            # Save model
            model_path = os.path.join(
                MODELS_DIR,
                f"{name.replace(' ', '_')}_{user_id}_{timestamp}.pkl",
            )
            joblib.dump(model, model_path)

            # ── Log to MLflow ──
            tracker.log_params(
                {
                    "cv_folds": 5,
                    "tuning_mode": tuning_mode,
                }
            )
            if tuning_params:
                tracker.log_params(
                    {f"{name}.tuned.{k}": str(v) for k, v in tuning_params.items()}
                )
            # Log cv scores as a metric
            tracker.log_metrics(
                {
                    f"{name}.cv_mean": float(cv_scores.mean()),
                    f"{name}.cv_std": float(cv_scores.std()),
                }
            )
            tracker.log_metrics(
                {f"{name}.{k}": v for k, v in metrics.items() if v is not None}
            )
            tracker.log_artifact(model_path)
            tracker.log_artifact(scaler_path)

            results.append(
                {
                    "name": name,
                    "metrics": metrics,
                    "confusion_matrix": cm.tolist(),
                    "roc_data": roc_data,
                    "model_path": model_path,
                    "cv_scores": {
                        "mean": round(float(cv_scores.mean()), 4),
                        "std": round(float(cv_scores.std()), 4),
                        "values": [round(float(s), 4) for s in cv_scores],
                    },
                    "tuning_params": tuning_params,
                }
            )
        except Exception as e:
            log.warning("Model %s failed: %s", name, e)
            results.append({"name": name, "error": str(e), "metrics": None})

    # Best model selection
    valid_results = [r for r in results if r.get("metrics")]
    if not valid_results:
        tracker.set_tags(
            {"best_model": "none", "reason": "No models trained successfully."}
        )
        tracker.end_run()
        return {
            "results": results,
            "best_model": None,
            "best_reason": "No models trained successfully.",
            "scaler_path": scaler_path,
            "feature_columns": feature_cols,
        }

    best = max(valid_results, key=lambda r: r["metrics"].get(selection_metric, 0) or 0)
    best_name = best["name"]
    best_metric_val = best["metrics"][selection_metric]

    if use_roc_for_selection:
        reason = (
            f"**{best_name}** selected based on **ROC-AUC = {best_metric_val:.4f}** "
            f"(class imbalance {minority_ratio:.1%}, using ROC-AUC)"
        )
    else:
        reason = (
            f"**{best_name}** selected based on **F1 Score = {best_metric_val:.4f}** "
            f"(CV mean: {best.get('cv_scores', {}).get('mean', 'N/A')})"
        )

    # ── Finalise MLflow run ───────────────────────────────────────────
    tracker.set_tags(
        {
            "best_model": best_name,
            "selection_metric": selection_metric,
            "best_metric_value": str(best_metric_val),
        }
    )
    tracker.log_metrics(
        {
            "best_accuracy": best["metrics"].get("accuracy", 0),
            "best_precision": best["metrics"].get("precision", 0),
            "best_recall": best["metrics"].get("recall", 0),
            "best_f1": best["metrics"].get("f1", 0),
            "best_roc_auc": best["metrics"].get("roc_auc", 0) or 0,
        }
    )
    if best.get("cv_scores"):
        tracker.log_metrics(
            {
                "best_cv_mean": best["cv_scores"]["mean"],
                "best_cv_std": best["cv_scores"]["std"],
            }
        )
    tracker.end_run()

    return {
        "results": results,
        "best_model": best_name,
        "best_reason": reason,
        "scaler_path": scaler_path,
        "feature_columns": feature_cols,
        "selection_metric": selection_metric,
        "tuning_mode": tuning_mode,
    }


# ──────────────────────────────────────────────
# Data Drift Detection
# ──────────────────────────────────────────────


def evaluate_drift(
    reference_df: pd.DataFrame,
    current_df: pd.DataFrame,
    feature_columns: list[str] | None = None,
    alpha: float = 0.05,
) -> dict:
    """
    Compare the distribution of new data against the training data using
    the Kolmogorov-Smirnov two-sample test.

    Returns:
        Dict with:
        - ``drift_detected``: True if any feature shows drift
        - ``drifted_features``: list of feature names with drift
        - ``results``: per-feature dicts with statistic and p-value
        - ``drift_score``: fraction of features that drifted (0-1)
    """
    import numpy as np
    from scipy.stats import ks_2samp

    if feature_columns is None:
        common = set(reference_df.select_dtypes(include=[np.number]).columns) & set(
            current_df.select_dtypes(include=[np.number]).columns
        )
        feature_columns = sorted(common)

    results = {}
    drifted_features = []

    for col in feature_columns:
        if col not in reference_df or col not in current_df:
            continue
        ref_vals = reference_df[col].dropna().values
        cur_vals = current_df[col].dropna().values
        if len(ref_vals) < 5 or len(cur_vals) < 5:
            continue

        stat, p_value = ks_2samp(ref_vals, cur_vals, alternative="two-sided")
        p_value = float(p_value)
        drifted = p_value < alpha

        results[col] = {
            "ks_statistic": round(float(stat), 4),
            "p_value": round(p_value, 6),
            "drifted": drifted,
            "ref_mean": float(ref_vals.mean()),
            "cur_mean": float(cur_vals.mean()),
        }
        if drifted:
            drifted_features.append(col)

    drift_score = len(drifted_features) / len(results) if results else 0.0

    return {
        "drift_detected": len(drifted_features) > 0,
        "drifted_features": drifted_features,
        "results": results,
        "drift_score": round(drift_score, 4),
        "n_features_checked": len(results),
        "alpha": alpha,
    }


# ──────────────────────────────────────────────
# Model Calibration
# ──────────────────────────────────────────────


def calibrate_model(
    model, X_train: np.ndarray, y_train: np.ndarray, method: str = "sigmoid"
) -> CalibratedClassifierCV:
    """
    Wrap a classifier with probability calibration.
    """
    from sklearn.calibration import CalibratedClassifierCV

    calibrated = CalibratedClassifierCV(model, cv=3, method=method)
    calibrated.fit(X_train, y_train)
    return calibrated


def get_sensor_deviations(row: pd.Series) -> list[dict]:
    """
    For a single reading row, compute how far each sensor is from its normal range.
    Returns a list sorted by deviation (worst first).
    """
    import pandas as pd

    from core.config import SENSOR_COLUMNS, SENSOR_THRESHOLDS

    deviations = []
    for col in SENSOR_COLUMNS:
        if col not in row or pd.isna(row[col]):
            continue
        value = row[col]
        thresholds = SENSOR_THRESHOLDS[col]
        normal_min = thresholds["min"]
        normal_max = thresholds["max"]
        normal_range = normal_max - normal_min

        if value < normal_min:
            deviation = (normal_min - value) / normal_range * 100
            status = "Below normal"
        elif value > normal_max:
            deviation = (value - normal_max) / normal_range * 100
            status = "Above normal"
        else:
            deviation = 0
            status = "Normal"

        deviations.append(
            {
                "sensor": col,
                "label": thresholds["label"],
                "value": value,
                "unit": thresholds["unit"],
                "normal_range": f"{normal_min}–{normal_max}",
                "deviation_pct": round(deviation, 1),
                "status": status,
            }
        )

    deviations.sort(key=lambda x: x["deviation_pct"], reverse=True)
    return deviations
