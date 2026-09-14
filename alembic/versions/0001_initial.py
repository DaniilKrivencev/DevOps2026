"""Initial migration — create all tables.

Revision ID: 0001
Revises:
Create Date: 2026-09-14
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # deputies
    op.create_table(
        "deputies",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("party", sa.String(100)),
        sa.Column("district", sa.String(100)),
        sa.Column("elected_on", sa.Date()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # commissions
    op.create_table(
        "commissions",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("description", sa.Text()),
        sa.Column("chair_id", sa.Integer(), sa.ForeignKey("deputies.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # commission_members
    op.create_table(
        "commission_members",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("commission_id", sa.Integer(), sa.ForeignKey("commissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("deputy_id", sa.Integer(), sa.ForeignKey("deputies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("joined_on", sa.Date()),
        sa.UniqueConstraint("commission_id", "deputy_id"),
    )

    # sessions
    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("commission_id", sa.Integer(), sa.ForeignKey("commissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("held_on", sa.Date(), nullable=False),
        sa.Column("topic", sa.String(500), nullable=False),
        sa.Column(
            "status",
            sa.Enum("planned", "held", "cancelled", name="sessionstatus"),
            nullable=False,
            server_default="planned",
        ),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # attendances
    op.create_table(
        "attendances",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("deputy_id", sa.Integer(), sa.ForeignKey("deputies.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "status",
            sa.Enum("present", "absent", "excused", name="attendancestatus"),
            nullable=False,
            server_default="present",
        ),
        sa.Column("note", sa.String(300)),
        sa.UniqueConstraint("session_id", "deputy_id"),
    )


def downgrade() -> None:
    op.drop_table("attendances")
    op.drop_table("sessions")
    op.drop_table("commission_members")
    op.drop_table("commissions")
    op.drop_table("deputies")
    op.execute("DROP TYPE IF EXISTS sessionstatus")
    op.execute("DROP TYPE IF EXISTS attendancestatus")
