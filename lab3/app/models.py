"""SQLAlchemy ORM models for City Duma application.

Entities:
  Deputy      — member of the city council
  Commission  — standing committee; has a chairperson (Deputy)
  CommissionMember — M2M: which deputies belong to which commission
  Session     — a formal meeting of a commission
  Attendance  — per-deputy attendance record for a session
"""

from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ─── Enumerations ─────────────────────────────────────────────────────────────


class AttendanceStatus(str, enum.Enum):
    present = "present"
    absent = "absent"
    excused = "excused"


class SessionStatus(str, enum.Enum):
    planned = "planned"
    held = "held"
    cancelled = "cancelled"


# ─── Deputy ──────────────────────────────────────────────────────────────────


class Deputy(Base):
    """City council deputy."""

    __tablename__ = "deputies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    party: Mapped[str | None] = mapped_column(String(100))
    district: Mapped[str | None] = mapped_column(String(100))
    elected_on: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Reverse relations
    chaired_commissions: Mapped[list[Commission]] = relationship(
        "Commission", back_populates="chair", foreign_keys="Commission.chair_id"
    )
    memberships: Mapped[list[CommissionMember]] = relationship(
        "CommissionMember", back_populates="deputy"
    )
    attendances: Mapped[list[Attendance]] = relationship(
        "Attendance", back_populates="deputy"
    )

    def __repr__(self) -> str:
        return f"<Deputy id={self.id} name={self.full_name!r}>"


# ─── Commission ───────────────────────────────────────────────────────────────


class Commission(Base):
    """Standing committee of the city council."""

    __tablename__ = "commissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    # Business rule: chair MUST be a member of the commission (enforced in API)
    chair_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("deputies.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    chair: Mapped[Deputy | None] = relationship(
        "Deputy", back_populates="chaired_commissions", foreign_keys=[chair_id]
    )
    members: Mapped[list[CommissionMember]] = relationship(
        "CommissionMember", back_populates="commission", cascade="all, delete-orphan"
    )
    sessions: Mapped[list[Session]] = relationship(
        "Session", back_populates="commission"
    )

    def __repr__(self) -> str:
        return f"<Commission id={self.id} name={self.name!r}>"


# ─── CommissionMember (M2M) ───────────────────────────────────────────────────


class CommissionMember(Base):
    """Association table: deputy ↔ commission."""

    __tablename__ = "commission_members"
    __table_args__ = (UniqueConstraint("commission_id", "deputy_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    commission_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("commissions.id", ondelete="CASCADE"), nullable=False
    )
    deputy_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("deputies.id", ondelete="CASCADE"), nullable=False
    )
    joined_on: Mapped[date | None] = mapped_column(Date)

    commission: Mapped[Commission] = relationship(
        "Commission", back_populates="members"
    )
    deputy: Mapped[Deputy] = relationship("Deputy", back_populates="memberships")


# ─── Session ─────────────────────────────────────────────────────────────────


class Session(Base):
    """Formal meeting of a commission."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    commission_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("commissions.id", ondelete="CASCADE"), nullable=False
    )
    held_on: Mapped[date] = mapped_column(Date, nullable=False)
    topic: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus), default=SessionStatus.planned, nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    commission: Mapped[Commission] = relationship(
        "Commission", back_populates="sessions"
    )
    attendances: Mapped[list[Attendance]] = relationship(
        "Attendance", back_populates="session", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Session id={self.id} held_on={self.held_on}>"


# ─── Attendance ───────────────────────────────────────────────────────────────


class Attendance(Base):
    """Per-deputy attendance record for a session."""

    __tablename__ = "attendances"
    __table_args__ = (UniqueConstraint("session_id", "deputy_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    deputy_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("deputies.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus), default=AttendanceStatus.present, nullable=False
    )
    note: Mapped[str | None] = mapped_column(String(300))

    session: Mapped[Session] = relationship("Session", back_populates="attendances")
    deputy: Mapped[Deputy] = relationship("Deputy", back_populates="attendances")
