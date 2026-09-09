"""Allow faithfully preserved undated source realized-gain records.

Revision ID: f290c48d531a
Revises: ccec6252b6b9
"""

from alembic import op
import sqlalchemy as sa

revision = "f290c48d531a"
down_revision = "ccec6252b6b9"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("transactions") as batch:
        batch.alter_column("date", existing_type=sa.Date(), nullable=True)


def downgrade():
    connection = op.get_bind()
    if connection.scalar(
        sa.text("SELECT COUNT(*) FROM transactions WHERE date IS NULL")
    ):
        raise RuntimeError(
            "Cannot downgrade while undated source records exist; preserve or reconcile them first."
        )
    with op.batch_alter_table("transactions") as batch:
        batch.alter_column("date", existing_type=sa.Date(), nullable=False)
