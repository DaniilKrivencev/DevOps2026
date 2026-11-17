"""Add contact fields to deputies (email, phone).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # batch_alter_table — чтобы миграция работала и в SQLite (ALTER через пересоздание)
    with op.batch_alter_table("deputies") as batch:
        batch.add_column(sa.Column("email", sa.String(254), nullable=True))
        batch.add_column(sa.Column("phone", sa.String(20), nullable=True))
        batch.create_unique_constraint("uq_deputies_email", ["email"])


def downgrade() -> None:
    with op.batch_alter_table("deputies") as batch:
        batch.drop_constraint("uq_deputies_email", type_="unique")
        batch.drop_column("phone")
        batch.drop_column("email")
