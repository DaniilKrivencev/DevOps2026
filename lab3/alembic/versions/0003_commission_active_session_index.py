"""Add commissions.is_active and index on sessions.held_on.

Существующие комиссии получают is_active = true через server_default,
поэтому миграция безопасна для БД, уже содержащей данные.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("commissions") as batch:
        batch.add_column(
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true())
        )
    op.create_index("ix_sessions_held_on", "sessions", ["held_on"])


def downgrade() -> None:
    op.drop_index("ix_sessions_held_on", table_name="sessions")
    with op.batch_alter_table("commissions") as batch:
        batch.drop_column("is_active")
