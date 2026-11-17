"""New feature: session agenda items with decisions.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agenda_items",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column(
            "decision",
            sa.Enum("pending", "adopted", "rejected", name="agendadecision"),
            nullable=False,
            server_default="pending",
        ),
        sa.UniqueConstraint("session_id", "position"),
    )


def downgrade() -> None:
    op.drop_table("agenda_items")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS agendadecision")
