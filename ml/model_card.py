"""Model card generation — intended use, performance, limitations."""

from datetime import datetime
from typing import Any


def generate_model_card(
    model_name: str,
    metrics: dict[str, float] | None,
    training_date: str | None = None,
    feature_count: int = 0,
    training_rows: int = 0,
    model_version: str = "1.0.0",
) -> str:
    """Generate a markdown model card for documentation."""
    date_str = training_date or datetime.utcnow().strftime("%Y-%m-%d")

    sections = [
        f"# Model Card: {model_name}",
        "",
        f"- **Version:** {model_version}",
        f"- **Date:** {date_str}",
        "- **Type:** Classification (Failure Prediction)",
        f"- **Features:** {feature_count}",
        f"- **Training Samples:** {training_rows:,}",
        "",
        "## Intended Use",
        "",
        "This model predicts the probability of vehicle component failure",
        "based on real-time sensor telemetry. It is designed for use in",
        "predictive maintenance applications to identify vehicles that",
        "require immediate or scheduled maintenance intervention.",
        "",
        "## Factors & Performance",
        "",
    ]

    if metrics:
        sections += [
            "| Metric | Value |",
            "|--------|-------|",
        ]
        for k, v in sorted(metrics.items()):
            if isinstance(v, float):
                sections.append(f"| {k} | {v:.4f} |")
            else:
                sections.append(f"| {k} | {v} |")
        sections.append("")

    sections += [
        "## Limitations",
        "",
        "- Performance depends on sensor data quality and completeness.",
        "- Model may not generalize to vehicle types or operating conditions",
        "  not represented in the training data.",
        "- Predictions are probabilistic — always validate with physical inspection.",
        "",
        "## Ethics",
        "",
        "- This model is a decision-support tool, not a replacement for",
        "  qualified mechanical inspection.",
        "- Training data may contain biases towards common failure modes;",
        "  rare or novel failures may not be detected.",
        "- Regular re-evaluation on production data is required.",
    ]

    return "\n".join(sections)


def model_card_to_dict(
    model_name: str, metrics: dict[str, float] | None, **kwargs
) -> dict[str, Any]:
    """Generate model card as structured data (for API responses)."""
    return {
        "model_name": model_name,
        "version": kwargs.get("version", "1.0.0"),
        "intended_use": "Predictive maintenance failure classification",
        "performance": metrics or {},
        "features": kwargs.get("feature_count", 0),
        "training_rows": kwargs.get("training_rows", 0),
        "limitations": [
            "Depends on sensor data quality",
            "May not generalize to unseen vehicle types",
            "Probabilistic — validate with physical inspection",
        ],
        "generated_at": datetime.utcnow().isoformat(),
    }
