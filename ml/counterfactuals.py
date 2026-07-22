"""Counterfactual explanations — "what would change this prediction?" """

from typing import Any

import numpy as np

from core.config import SENSOR_THRESHOLDS


def find_counterfactuals(
    model,
    X_input: np.ndarray,
    feature_names: list[str],
    original_prediction: int,
    num_counterfactuals: int = 3,
) -> dict[str, Any]:
    """Find minimal changes that would flip the prediction.

    Uses a simple grid-search approach: for each feature, find the smallest
    change that flips the prediction. Returns the top N counterfactuals.
    """
    counterfactuals = []
    original_prob = _predict_proba(model, X_input)[0]

    for i, name in enumerate(feature_names):
        modified = X_input.copy()
        thresholds = SENSOR_THRESHOLDS.get(name, {})

        # Try adjusting up and down
        for direction, delta in [("increase", 0.1), ("decrease", -0.1)]:
            test_val = modified[0, i] * (1 + delta)
            # Clamp to realistic range
            if thresholds:
                if direction == "increase":
                    test_val = min(
                        test_val, thresholds.get("critical_max", test_val * 2)
                    )
                else:
                    test_val = max(
                        test_val, thresholds.get("critical_min", test_val * 0.5)
                    )

            modified[0, i] = test_val
            new_prob = _predict_proba(model, modified)[0]
            new_class = 1 if new_prob > 0.5 else 0

            if new_class != original_prediction:
                change_pct = abs(
                    (test_val - X_input[0, i]) / (X_input[0, i] or 1) * 100
                )
                counterfactuals.append(
                    {
                        "feature": name,
                        "current_value": round(float(X_input[0, i]), 2),
                        "suggested_value": round(float(test_val), 2),
                        "direction": direction,
                        "change_pct": round(float(change_pct), 1),
                        "resulting_prob": round(float(new_prob), 3),
                    }
                )
                break

    # Sort by minimal change required
    counterfactuals.sort(key=lambda x: x["change_pct"])
    return {
        "original_prediction": "failure" if original_prediction == 1 else "healthy",
        "original_probability": round(float(original_prob), 3),
        "counterfactuals": counterfactuals[:num_counterfactuals],
        "total_found": len(counterfactuals),
        "method": "feature_grid_search",
    }


def _predict_proba(model, X: np.ndarray) -> np.ndarray:
    """Get probability predictions, handling different model APIs."""
    try:
        return model.predict_proba(X)[:, 1]
    except AttributeError:
        return model.predict(X)
