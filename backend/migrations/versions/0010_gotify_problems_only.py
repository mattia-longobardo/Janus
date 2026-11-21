"""notifications: Gotify off by default for events that are not problems

Revision ID: 0010
Revises: 0009
"""
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

EVENTS = "('device.approved', 'device.blocked', 'infra.up')"


def upgrade() -> None:
    op.execute(f"UPDATE notification_rules SET enabled = false WHERE channel = 'gotify' AND event_type IN {EVENTS}")


def downgrade() -> None:
    op.execute(f"UPDATE notification_rules SET enabled = true WHERE channel = 'gotify' AND event_type IN {EVENTS}")
