"""add_api_keys_and_webhooks

Revision ID: add_api_keys_and_webhooks
Revises: 14f8a4ff9712
Create Date: 2026-07-13 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'add_api_keys_and_webhooks'
down_revision: Union[str, None] = '14f8a4ff9712'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # API Keys table
    op.create_table('api_keys',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('prefix', sa.String(), nullable=False),
        sa.Column('key_hash', sa.String(), nullable=False),
        sa.Column('scopes', sa.Text(), nullable=True, server_default='[]'),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key_hash'),
    )

    # Webhook subscriptions table
    op.create_table('webhook_subscriptions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('url', sa.String(), nullable=False),
        sa.Column('secret', sa.String(), nullable=True),
        sa.Column('events', sa.Text(), nullable=False, server_default='["*"]'),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('retry_count', sa.Integer(), nullable=True, server_default='3'),
        sa.Column('timeout_seconds', sa.Integer(), nullable=True, server_default='10'),
        sa.Column('last_triggered_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_webhook_subscriptions_user', 'webhook_subscriptions', ['user_id', 'is_active'])

    # Webhook logs table
    op.create_table('webhook_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('webhook_id', sa.Integer(), nullable=False),
        sa.Column('event', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('response_body', sa.Text(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('attempt', sa.Integer(), nullable=True, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['webhook_id'], ['webhook_subscriptions.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_webhook_logs_webhook', 'webhook_logs', ['webhook_id', 'created_at'])

    # Add database indexes for performance
    op.create_index('ix_alerts_vehicle_created', 'alerts', ['vehicle_id', 'created_at'])
    op.create_index('ix_predictions_vehicle_created', 'predictions', ['vehicle_id', 'predicted_at'])
    op.create_index('ix_readings_timestamp', 'sensor_readings', ['timestamp'])
    op.create_index('ix_vehicles_user_created', 'vehicles', ['user_id', 'created_at'])

    # Add soft-delete column to vehicles
    op.add_column('vehicles', sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('vehicles', sa.Column('deleted_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_index('ix_vehicles_user_created', table_name='vehicles')
    op.drop_index('ix_readings_timestamp', table_name='sensor_readings')
    op.drop_index('ix_predictions_vehicle_created', table_name='predictions')
    op.drop_index('ix_alerts_vehicle_created', table_name='alerts')
    op.drop_index('ix_webhook_logs_webhook', table_name='webhook_logs')
    op.drop_table('webhook_logs')
    op.drop_index('ix_webhook_subscriptions_user', table_name='webhook_subscriptions')
    op.drop_table('webhook_subscriptions')
    op.drop_table('api_keys')
    op.drop_column('vehicles', 'deleted_at')
    op.drop_column('vehicles', 'is_deleted')