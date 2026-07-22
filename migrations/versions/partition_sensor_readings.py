"""partition_sensor_readings

Partition the ``sensor_readings`` table by month using PostgreSQL
declarative range partitioning.

Partitioning strategy
---------------------
- **Method:** PostgreSQL declarative ``PARTITION BY RANGE (timestamp)``
- **Granularity:** One partition per calendar month
- **Partition key:** ``timestamp`` (set to ``NOT NULL`` during migration)
- **Primary key:** Changed from ``(id)`` to ``(id, timestamp)`` because
  PostgreSQL requires the partition key to be part of every unique
  constraint on a partitioned table.
- **Idempotent:** The migration checks ``pg_class.relkind`` before making
  any changes.  If ``sensor_readings`` is already a partitioned table
  (``relkind = 'p'``), the upgrade is a no-op.

Why range partitioning?
  The ``sensor_readings`` table is the largest table in the system.
  Dashboard and analysis queries almost always filter by a time window,
  so range partitioning by month lets the planner prune entire
  partitions.  Old partitions can be detached (not dropped) for
  archival without affecting the live table.

Data migration
--------------
Because PostgreSQL cannot ``ALTER`` an existing table to add declarative
partitioning, the migration:
  1. Renames the existing table to ``sensor_readings_old``
  2. Creates the new partitioned table as ``sensor_readings``
  3. Copies all data from the old table into the new partitions
  4. Drops ``sensor_readings_old``

This is a blocking operation on a live table -- schedule this migration
during a maintenance window if the table has more than a few million
rows.

Indexes
-------
Indexes created on the partitioned parent table are automatically
created on every attached partition.  The existing indexes are dropped
before the rename and recreated on the new partitioned parent after the
data copy.

Revision ID: partition_sensor_readings
Revises: add_performance_indexes
Create Date: 2026-07-14 10:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "partition_sensor_readings"
down_revision: Union[str, None] = "add_performance_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── Helpers ─────────────────────────────────────────────────────────────────

def _month_partition_name(year: int, month: int) -> str:
    """Return the partition table name for a given year/month."""
    return f"sensor_readings_{year}_{month:02d}"


def _partition_boundary(year: int, month: int) -> str:
    """Return the string timestamp for the start of the *next* month.

    Used as the exclusive upper bound of a range partition.
    """
    if month == 12:
        return f"{year + 1}-01-01 00:00:00"
    return f"{year}-{month + 1:02d}-01 00:00:00"


# ── Column / DDL constants ──────────────────────────────────────────────────

_COLUMNS_SQL = """
    id INTEGER NOT NULL,
    upload_id INTEGER NOT NULL,
    vehicle_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    "timestamp" TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    engine_temp DOUBLE PRECISION,
    oil_pressure DOUBLE PRECISION,
    coolant_temp DOUBLE PRECISION,
    engine_rpm DOUBLE PRECISION,
    vibration DOUBLE PRECISION,
    fuel_consumption DOUBLE PRECISION,
    battery_voltage DOUBLE PRECISION,
    tire_pressure DOUBLE PRECISION,
    speed DOUBLE PRECISION,
    engine_load DOUBLE PRECISION,
    failure_label INTEGER
"""

# Known FK constraint names on sensor_readings (from initial migration).
_FK_DEFINITIONS = [
    ("fk_sensor_readings_upload_id_sensor_uploads",
     "upload_id", "sensor_uploads(id)"),
    ("fk_sensor_readings_user_id_users",
     "user_id", "users(id)"),
    ("fk_sensor_readings_vehicle_id_vehicles",
     "vehicle_id", "vehicles(id)"),
]


# ── Upgrade ─────────────────────────────────────────────────────────────────

def upgrade() -> None:
    """Partition sensor_readings by month (PostgreSQL only)."""
    conn = op.get_bind()

    # ── Idempotency & dialect check ──────────────────────────────
    # Partitioning is PostgreSQL-specific.  Skip entirely on SQLite.
    if conn.dialect.name != "postgresql":
        return

    already_partitioned = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_catalog.pg_class "
            "WHERE relname = 'sensor_readings' AND relkind = 'p'"
        )
    ).fetchone()
    if already_partitioned:
        return

    # ── Step 1: Make timestamp NOT NULL ──────────────────────────
    # Partition key columns must be NOT NULL.
    conn.execute(
        sa.text(
            "UPDATE sensor_readings "
            "SET timestamp = '1970-01-01 00:00:00' "
            "WHERE timestamp IS NULL"
        )
    )
    op.alter_column("sensor_readings", "timestamp", nullable=False)

    # ── Step 2: Drop existing indexes ────────────────────────────
    # They will be recreated on the new partitioned parent in Step 7.
    for idx in (
        "ix_sensor_readings_vehicle_timestamp",
        "ix_sensor_readings_user_vehicle_ts",
        "ix_readings_timestamp",
    ):
        try:
            op.drop_index(idx, table_name="sensor_readings")
        except Exception:
            pass  # index may not exist yet (e.g. freshly created migration)

    # ── Step 3: Capture current max id for the sequence ─────────
    max_id = conn.execute(
        sa.text("SELECT COALESCE(MAX(id), 0) FROM sensor_readings")
    ).scalar()

    # ── Step 4: Rename old table out of the way ─────────────────
    op.rename_table("sensor_readings", "sensor_readings_old")

    # ── Step 5: Create the new partitioned table ─────────────────
    # Using raw SQL because Alembic's create_table does not support
    # PARTITION BY.  The column list must match the original exactly.
    op.execute(
        f"""
        CREATE TABLE sensor_readings (
            {_COLUMNS_SQL},
            PRIMARY KEY (id, "timestamp")
        ) PARTITION BY RANGE ("timestamp")
        """
    )

    # ── Step 6: Re-attach FK constraints ─────────────────────────
    for fk_name, fk_col, ref_clause in _FK_DEFINITIONS:
        op.execute(
            f"ALTER TABLE sensor_readings "
            f"ADD CONSTRAINT {fk_name} "
            f"FOREIGN KEY ({fk_col}) REFERENCES {ref_clause}"
        )

    # ── Step 7: Create monthly partitions ────────────────────────
    # Determine the time range of existing data.
    range_row = conn.execute(
        sa.text(
            "SELECT EXTRACT(YEAR FROM MIN(timestamp)), "
            "       EXTRACT(MONTH FROM MIN(timestamp)), "
            "       EXTRACT(YEAR FROM MAX(timestamp)), "
            "       EXTRACT(MONTH FROM MAX(timestamp)) "
            "FROM sensor_readings_old"
        )
    ).fetchone()

    if range_row and range_row[0] is not None:
        start_year = int(range_row[0])
        start_month = int(range_row[1])
        end_year = int(range_row[2])
        end_month = int(range_row[3])
    else:
        # Empty table -- create partitions for a default range.
        start_year, start_month = 2024, 1
        end_year, end_month = 2027, 12

    # Walk month by month from 3 months before start to 3 months after end.
    total_months = (
        (end_year - start_year) * 12 + (end_month - start_month) + 6
    )
    total_months = min(total_months, 48)  # cap at 4 years

    cy, cm = start_year, start_month
    # Go back 3 months
    for _ in range(3):
        cm -= 1
        if cm == 0:
            cm = 12
            cy -= 1

    for _ in range(total_months):
        part_name = _month_partition_name(cy, cm)
        from_ts = f"{cy}-{cm:02d}-01 00:00:00"
        to_ts = _partition_boundary(cy, cm)

        op.execute(
            f"CREATE TABLE IF NOT EXISTS {part_name} "
            f"PARTITION OF sensor_readings "
            f"FOR VALUES FROM ('{from_ts}') TO ('{to_ts}')"
        )

        # Advance one month
        cm += 1
        if cm == 13:
            cm = 1
            cy += 1

    # Catch-all default partition for any data outside planned ranges.
    op.execute(
        "CREATE TABLE IF NOT EXISTS sensor_readings_default "
        "PARTITION OF sensor_readings DEFAULT"
    )

    # ── Step 8: Copy data ────────────────────────────────────────
    # This is a single bulk INSERT.  For very large tables, consider
    # using batch INSERT or pg_chunk in production.
    op.execute(
        "INSERT INTO sensor_readings SELECT * FROM sensor_readings_old"
    )

    # ── Step 9: Recreate indexes on the new partitioned parent ───
    # These will be automatically propagated to existing and future
    # partitions.
    op.create_index(
        "ix_sensor_readings_vehicle_timestamp",
        "sensor_readings",
        ["vehicle_id", "timestamp"],
    )
    op.create_index(
        "ix_sensor_readings_user_vehicle_ts",
        "sensor_readings",
        ["user_id", "vehicle_id", sa.text('"timestamp" DESC')],
    )
    op.create_index(
        "ix_readings_timestamp",
        "sensor_readings",
        ["timestamp"],
    )

    # ── Step 10: Wire up the auto-increment sequence ─────────────
    op.execute("CREATE SEQUENCE sensor_readings_id_seq")
    op.execute(
        f"ALTER SEQUENCE sensor_readings_id_seq RESTART WITH {max_id + 1}"
    )
    op.execute(
        "ALTER TABLE sensor_readings ALTER COLUMN id "
        "SET DEFAULT nextval('sensor_readings_id_seq')"
    )
    op.execute(
        "ALTER SEQUENCE sensor_readings_id_seq OWNED BY sensor_readings.id"
    )

    # ── Step 11: Drop the old table ──────────────────────────────
    op.drop_table("sensor_readings_old")

    # ── Step 12: Auto-partition helper function ──────────────────
    # This function creates the next month's partition when called.
    # It can be invoked by a daily cron / pg_cron job:
    #   SELECT create_sensor_readings_partition();
    op.execute(
        """
        CREATE OR REPLACE FUNCTION create_sensor_readings_partition()
        RETURNS void
        LANGUAGE plpgsql AS
        $$
        DECLARE
            next_month date;
            part_name  text;
            from_ts    text;
            to_ts      text;
        BEGIN
            next_month := date_trunc('month', NOW()) + INTERVAL '1 month';
            part_name := 'sensor_readings_'
                         || to_char(next_month, 'YYYY_MM');
            from_ts   := to_char(next_month, 'YYYY-MM-DD" 00:00:00"');
            to_ts     := to_char(next_month + INTERVAL '1 month',
                                  'YYYY-MM-DD" 00:00:00"');

            IF NOT EXISTS (
                SELECT 1 FROM pg_catalog.pg_class WHERE relname = part_name
            ) THEN
                EXECUTE format(
                    'CREATE TABLE %I PARTITION OF sensor_readings '
                    'FOR VALUES FROM (%L) TO (%L)',
                    part_name, from_ts, to_ts
                );
            END IF;
        END;
        $$;
        """
    )


# ── Downgrade ───────────────────────────────────────────────────────────────

def downgrade() -> None:
    """Reverse the partition migration -- convert back to a regular table.

    WARNING: On tables with significant data this is a slow, blocking
    operation.  Prefer to keep the partitioned structure instead.
    """
    conn = op.get_bind()

    if conn.dialect.name != "postgresql":
        return

    # Drop the auto-partition helper.
    op.execute("DROP FUNCTION IF EXISTS create_sensor_readings_partition()")

    # Check current state.
    is_partitioned = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_catalog.pg_class "
            "WHERE relname = 'sensor_readings' AND relkind = 'p'"
        )
    ).fetchone()
    if not is_partitioned:
        return

    # Capture max id for the new sequence.
    max_id = conn.execute(
        sa.text("SELECT COALESCE(MAX(id), 0) FROM sensor_readings")
    ).scalar()

    # Create a new regular table with the same column layout.
    op.execute(
        f"""
        CREATE TABLE sensor_readings_new (
            {_COLUMNS_SQL},
            PRIMARY KEY (id)
        )
        """
    )

    # Copy data from the partitioned table.
    op.execute("INSERT INTO sensor_readings_new SELECT * FROM sensor_readings")

    # Drop the partitioned table (CASCADE removes all child partitions).
    op.execute("DROP TABLE sensor_readings CASCADE")

    # Rename the new table to take its place.
    op.rename_table("sensor_readings_new", "sensor_readings")

    # Recreate indexes.
    op.create_index(
        "ix_sensor_readings_vehicle_timestamp",
        "sensor_readings",
        ["vehicle_id", "timestamp"],
    )
    op.create_index(
        "ix_sensor_readings_user_vehicle_ts",
        "sensor_readings",
        ["user_id", "vehicle_id", sa.text('"timestamp" DESC')],
    )
    op.create_index(
        "ix_readings_timestamp",
        "sensor_readings",
        ["timestamp"],
    )

    # Recreate FK constraints.
    for fk_name, fk_col, ref_clause in _FK_DEFINITIONS:
        op.execute(
            f"ALTER TABLE sensor_readings "
            f"ADD CONSTRAINT {fk_name} "
            f"FOREIGN KEY ({fk_col}) REFERENCES {ref_clause}"
        )

    # Recreate the auto-increment sequence.
    op.execute("CREATE SEQUENCE sensor_readings_id_seq")
    op.execute(
        f"ALTER SEQUENCE sensor_readings_id_seq RESTART WITH {max_id + 1}"
    )
    op.execute(
        "ALTER TABLE sensor_readings ALTER COLUMN id "
        "SET DEFAULT nextval('sensor_readings_id_seq')"
    )
    op.execute(
        "ALTER SEQUENCE sensor_readings_id_seq OWNED BY sensor_readings.id"
    )
