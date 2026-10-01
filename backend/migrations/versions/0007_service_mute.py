"""mute accepted risks per service

Revision ID: 0007
Revises: 0006
"""
import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("services", sa.Column("muted", sa.Boolean(), server_default="false", nullable=False))


def downgrade() -> None:
    op.drop_column("services", "muted")
