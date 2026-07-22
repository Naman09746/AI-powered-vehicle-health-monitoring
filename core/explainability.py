"""
SHAP-based explainability for ML predictions.

Provides feature contribution analysis with plain-language explanations,
waterfall visualisations, and top risk factor ranking.

Supports:
- TreeExplainer (Random Forest, XGBoost, Decision Tree) — fast
- LinearExplainer (Logistic Regression) — exact
- KernelExplainer (SVM, any model) — universal fallback
"""

from __future__ import annotations

import io

import numpy as np

from core.config import SENSOR_THRESHOLDS
from core.logger import get_logger

log = get_logger("explainability")


def explain_prediction(
    model, X_input: np.ndarray, feature_names: list[str], model_name: str = ""
) -> dict:
    """
    Explain a prediction using SHAP or model-native feature importances.

    Args:
        model: Trained sklearn/xgboost model.
        X_input: Scaled input features (2D array).
        feature_names: List of feature column names.
        model_name: Name of the model (for choosing explainer).

    Returns:
        Dict with:
        - ``shap_values``: raw SHAP values (or None if fallback)
        - ``top_features``: ranked list with plain-language descriptions
        - ``method``: string describing which explainer was used
        - ``feature_names``: copy of the input list
        - ``error``: present only on fallback
        - ``expected_value``: model expected value (baseline)
    """
    try:
        import shap

        # Choose appropriate explainer
        if hasattr(model, "feature_importances_"):
            # Tree-based: use TreeExplainer (fast, exact)
            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(X_input)
            expected_value = explainer.expected_value

            # Handle multi-output (binary classification)
            if isinstance(shap_values, list):
                # shap_values[0] = negative class, [1] = positive class
                shap_values = shap_values[1]
                if isinstance(expected_value, list):
                    expected_value = expected_value[1]

            method = "TreeExplainer"

        elif hasattr(model, "coef_"):
            # Linear model: use LinearExplainer
            explainer = shap.LinearExplainer(model, X_input)
            shap_values = explainer.shap_values(X_input)
            expected_value = explainer.expected_value
            method = "LinearExplainer"

        else:
            # Fallback: KernelExplainer (slow but universal)
            background = shap.sample(X_input, min(50, len(X_input)))
            explainer = shap.KernelExplainer(
                model.predict_proba,
                background,
            )
            shap_values = explainer.shap_values(X_input)
            expected_value = explainer.expected_value

            if isinstance(shap_values, list):
                shap_values = shap_values[1]
                if isinstance(expected_value, list):
                    expected_value = expected_value[1]

            method = "KernelExplainer"

        if len(shap_values.shape) > 1 and shap_values.shape[0] > 1:
            # Average across all input rows
            avg_shap = np.abs(shap_values).mean(axis=0)
        else:
            avg_shap = (
                np.abs(shap_values).ravel()
                if len(shap_values.shape) > 1
                else np.abs(shap_values)
            )

        # Build top features
        top_features = _build_top_features(avg_shap, feature_names, method="shap")

        return {
            "shap_values": shap_values,
            "expected_value": float(expected_value)
            if isinstance(expected_value, (int, float, np.generic))
            else float(expected_value[0]),
            "top_features": top_features,
            "method": method,
            "feature_names": feature_names,
        }

    except ImportError:
        log.warning("shap package not installed — using feature importances")
        return _fallback_explanation(model, feature_names, error="shap not installed")
    except Exception as exc:
        log.warning("SHAP explainer failed for %s: %s", model_name, exc)
        return _fallback_explanation(model, feature_names, error=str(exc))


def generate_shap_waterfall(
    model, X_row: np.ndarray, feature_names: list[str]
) -> bytes | None:
    """
    Generate a SHAP waterfall plot as PNG bytes for a single prediction.

    Args:
        model: Trained sklearn/xgboost model.
        X_row: Single-row scaled feature array (shape ``(1, n_features)``).
        feature_names: List of feature column names.

    Returns:
        PNG image bytes, or None if SHAP is unavailable.
    """
    try:
        import matplotlib
        import shap

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        if hasattr(model, "feature_importances_"):
            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(X_row)
            expected_value = explainer.expected_value
        elif hasattr(model, "coef_"):
            explainer = shap.LinearExplainer(model, X_row)
            shap_values = explainer.shap_values(X_row)
            expected_value = explainer.expected_value
        else:
            return None

        if isinstance(shap_values, list):
            shap_values = shap_values[1]
            if isinstance(expected_value, list):
                expected_value = expected_value[1]

        # Create waterfall
        fig = plt.figure(figsize=(10, 6))
        shap.waterfall_plot(
            expected_value,
            shap_values[0] if len(shap_values.shape) > 1 else shap_values,
            feature_names=feature_names,
            show=False,
            max_display=10,
        )
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf.getvalue()
    except Exception as exc:
        log.warning("Waterfall plot failed: %s", exc)
        return None


def get_top_risk_factors(
    shap_values, feature_names: list[str], top_n: int = 5
) -> list[dict]:
    """
    Rank features by their SHAP contribution to failure risk.

    Only features with POSITIVE SHAP values (pushing toward failure) are
    included, sorted by magnitude.

    Args:
        shap_values: Raw SHAP values (1D or 2D array).
        feature_names: List of feature names.
        top_n: Number of top risk factors to return.

    Returns:
        List of dicts with feature, value, description.
    """
    if isinstance(shap_values, list):
        shap_values = shap_values[1] if len(shap_values) > 1 else shap_values[0]

    if len(shap_values.shape) > 1:
        shap_values = shap_values.mean(axis=0)

    risk_factors = []
    for feat, shval in zip(feature_names, shap_values, strict=False):
        if shval > 0:  # pushes toward failure
            risk_factors.append(
                {
                    "feature": feat,
                    "shap_value": float(shval),
                    "description": _feature_to_plain_language(feat, float(shval) * 100),
                    "direction": "increases risk",
                }
            )

    risk_factors.sort(key=lambda x: x["shap_value"], reverse=True)
    return risk_factors[:top_n]


def _fallback_explanation(model, feature_names: list[str], error: str = "") -> dict:
    """Fallback explanation using model-native feature importances."""
    importances = None

    if hasattr(model, "feature_importances_"):
        importances = model.feature_importances_
    elif hasattr(model, "coef_"):
        importances = np.abs(model.coef_[0])

    if importances is None:
        return {
            "shap_values": None,
            "expected_value": None,
            "top_features": [],
            "method": "No explainability available",
            "feature_names": feature_names,
            "error": error,
        }

    top_features = _build_top_features(importances, feature_names, method="importance")
    return {
        "shap_values": None,
        "expected_value": None,
        "top_features": top_features,
        "feature_names": feature_names,
        "method": "Feature Importances (SHAP fallback)",
        "error": error,
    }


def _build_top_features(
    importances: np.ndarray,
    feature_names: list[str],
    method: str = "shap",
    top_n: int = 5,
) -> list[dict]:
    """Build a sorted list of top contributing features with descriptions."""
    total = importances.sum()
    if total == 0:
        return []

    features = []
    for feat, imp in zip(feature_names, importances, strict=False):
        pct = float(imp / total * 100)
        features.append(
            {
                "feature": feat,
                "importance": float(imp),
                "contribution_pct": round(pct, 1),
                "description": _feature_to_plain_language(feat, pct),
            }
        )

    features.sort(key=lambda x: x["importance"], reverse=True)
    return features[:top_n]


def _feature_to_plain_language(feature_name: str, contribution_pct: float) -> str:
    """Convert a feature name + contribution to a plain-language explanation."""
    base_sensor = (
        feature_name.split("_rolling_avg")[0]
        .split("_rate_of_change")[0]
        .split("_anomaly")[0]
    )

    label = SENSOR_THRESHOLDS.get(base_sensor, {}).get(
        "label", feature_name.replace("_", " ").title()
    )

    if "_rolling_avg" in feature_name:
        desc = f"Average {label} trend"
    elif "_rate_of_change" in feature_name:
        desc = f"Rate of change in {label}"
    elif "_anomaly" in feature_name:
        desc = f"{label} anomaly flag"
    else:
        desc = label

    return f"{desc} contributed {contribution_pct:.0f}% to this prediction"
