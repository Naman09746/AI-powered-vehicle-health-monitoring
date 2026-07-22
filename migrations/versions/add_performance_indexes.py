"""add_performance_indexes

Add composite and partial indexes for common query patterns:

- sensor_readings: (user_id, vehicle_id, timestamp DESC)
- alerts:         (user_id, is_dismissed, created_at DESC)
- predictions:    (vehicle_id, predicted_at DESC)
- trained_models: (vehicle_id) WHERE is_champion = TRUE   (partial)
- audit_logs:     (user_id, action, created_at DESC)

Existing indexes that already cover similar access patterns:
  ix_sensor_readings_vehicle_timestamp  (vehicle_id, timestamp)
  ix_alerts_user_dismissed              (user_id, is_dismissed)
  ix_predictions_vehicle_created        (vehicle_id, predicted_at)
  ix_webhook_logs_webhook               (webhook_id, created_at)
  ix_alerts_vehicle_created             (vehicle_id, created_at)

Revision ID: add_performance_indexes
Revises: add_api_keys_and_webhooks
Create Date: 2026-07-14 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "add_performance_indexes"
down_revision: Union[str, None] = "add_api_keys_and_webhooks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add composite and partial indexes."""
    # -- sensor_readings -------------------------------------------------------
    # Existing ix_sensor_readings_vehicle_timestamp covers (vehicle_id, timestamp).
    # This wider index supports user-scoped queries that filter by user_id first
    # and then sort by timestamp descending (the most common dashboard pattern).
    op.create_index(
        "ix_sensor_readings_user_vehicle_ts",
        "sensor_readings",
        ["user_id", "vehicle_id", sa.text("timestamp DESC")],
    )

    # -- alerts ----------------------------------------------------------------
    # ix_alerts_user_dismissed covers (user_id, is_dismissed).
    # Extend with created_at DESC for the "undismissed alerts, newest first"
    # pattern used by the dashboard and notification views.
    op.create_index(
        "ix_alerts_user_dismissed_created",
        "alerts",
        ["user_id", "is_dismissed", sa.text("created_at DESC")],
    )

    # -- predictions -----------------------------------------------------------
    # ix_predictions_vehicle_created exists as (vehicle_id, predicted_at).
    # This index adds explicit DESC ordering on predicted_at so the planner
    # can use a backward index scan for "most recent predictions first".
    op.create_index(
        "ix_predictions_vehicle_predicted_desc",
        "predictions",
        ["vehicle_id", sa.text("predicted_at DESC")],
    )

    # -- trained_models --------------------------------------------------------
    # Partial index on (vehicle_id) WHERE is_champion = TRUE.
    # Speeds up the common query: "find the current champion model for vehicle X".
    # Only a single row per vehicle will satisfy is_champion = TRUE, so the index
    # stays extremely small.
    op.create_index(
        "ix_trained_models_vehicle_champion",
        "trained_models",
        ["vehicle_id"],
        postgresql_where=sa.text("is_champion = TRUE"),
    )

    # -- audit_logs ------------------------------------------------------------
    # Composite index covering the two most common audit-log access patterns:
    # "all actions for a user" and "actions of a specific type for a user",
    # both sorted newest-first.
    op.create_index(
        "ix_audit_logs_user_action_created",
        "audit_logs",
        ["user_id", "action", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    """Remove indexes added in upgrade()."""
    op.drop_index("ix_sensor_readings_user_vehicle_ts", table_name="sensor_readings")
    op.drop_index("ix_alerts_user_dismissed_created", table_name="alerts")
    op.drop_index("ix_predictions_vehicle_predicted_desc", table_name="predictions")
    op.drop_index("ix_trained_models_vehicle_champion", table_name="trained_models")
    op.drop_index("ix_audit_logs_user_action_created", table_name="audit_logs")
