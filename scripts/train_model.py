"""
Dataset Generator & ML Model Trainer.

Generates a realistic multi-profile vehicle telemetry dataset
and trains predictive maintenance ML models (Random Forest, XGBoost, etc.).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np

from ml.synthetic import generate_failure_scenario, augment_rare_failures
from ml.ml_models import train_models


def main():
    print("🚗 Generating multi-profile vehicle telemetry dataset...")

    profiles = [
        ("normal_operation", 500),
        ("coolant_leak", 200),
        ("battery_degradation", 200),
        ("oil_pressure_drop", 200),
        ("sensor_spike", 150),
    ]

    dfs = []
    for profile, n_rows in profiles:
        print(f"   -> Generating {n_rows} rows for profile '{profile}'...")
        df_p = generate_failure_scenario(profile=profile, n_rows=n_rows)
        dfs.append(df_p)

    full_df = pd.concat(dfs, ignore_index=True)
    full_df = augment_rare_failures(full_df, target_ratio=0.4)

    # Save to data directory
    os.makedirs("data", exist_ok=True)
    csv_path = "data/sample_vehicle_telemetry.csv"
    full_df.to_csv(csv_path, index=False)
    print(f"\n✅ Dataset successfully generated & saved to '{csv_path}'")
    print(f"   Total rows: {len(full_df)}")
    print(f"   Failure breakdown:\n{full_df['failure_label'].value_counts().to_string()}\n")

    # Train Models
    print("🤖 Training predictive maintenance ML models...")
    res = train_models(
        df=full_df,
        user_id=1,
        vehicle_id=1,
        target_col="failure_label",
    )

    best_name = res.get("best_model", "None")
    reason = res.get("best_reason", "")

    print("\n🎉 ML Model Training Complete!")
    print("──────────────────────────────────────────────")
    print(f"Best Model Selected : {best_name}")
    print(f"Selection Reason   : {reason}")
    print("──────────────────────────────────────────────")

    for item in res.get("results", []):
        name = item.get("name")
        metrics = item.get("metrics")
        if metrics:
            print(f"\nModel: {name}")
            print(f"  - Accuracy  : {metrics.get('accuracy', 0):.4f}")
            print(f"  - Precision : {metrics.get('precision', 0):.4f}")
            print(f"  - Recall    : {metrics.get('recall', 0):.4f}")
            print(f"  - F1 Score  : {metrics.get('f1', 0):.4f}")
            print(f"  - ROC AUC   : {metrics.get('roc_auc', 0):.4f}")
        elif item.get("error"):
            print(f"\nModel: {name} (Error: {item.get('error')})")


if __name__ == "__main__":
    main()
