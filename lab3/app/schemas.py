"""Pydantic schemas for request/response validation."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.models import AttendanceStatus, SessionStatus


# ─── Deputy ──────────────────────────────────────────────────────────────────


class DeputyBase(BaseModel):
    full_name: str
    party: Optional[str] = None
    district: Optional[str] = None
    elected_on: Optional[date] = None
    is_active: bool = True


class DeputyCreate(DeputyBase):
    @field_validator("full_name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("full_name must not be empty")
        return v.strip()


class DeputyUpdate(BaseModel):
    full_name: Optional[str] = None
    party: Optional[str] = None
    district: Optional[str] = None
    elected_on: Optional[date] = None
    is_active: Optional[bool] = None


class DeputyOut(DeputyBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


# ─── Commission ───────────────────────────────────────────────────────────────


class CommissionBase(BaseModel):
    name: str
    description: Optional[str] = None
    chair_id: Optional[int] = None


class CommissionCreate(CommissionBase):
    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be empty")
        return v.strip()


class CommissionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    chair_id: Optional[int] = None


class CommissionOut(CommissionBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


# ─── CommissionMember ─────────────────────────────────────────────────────────


class CommissionMemberCreate(BaseModel):
    deputy_id: int
    joined_on: Optional[date] = None


class CommissionMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    commission_id: int
    deputy_id: int
    joined_on: Optional[date]


# ─── Session ─────────────────────────────────────────────────────────────────


class SessionBase(BaseModel):
    commission_id: int
    held_on: date
    topic: str
    status: SessionStatus = SessionStatus.planned
    notes: Optional[str] = None


class SessionCreate(SessionBase):
    @field_validator("topic")
    @classmethod
    def topic_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("topic must not be empty")
        return v.strip()


class SessionUpdate(BaseModel):
    held_on: Optional[date] = None
    topic: Optional[str] = None
    status: Optional[SessionStatus] = None
    notes: Optional[str] = None


class SessionOut(SessionBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


# ─── Attendance ───────────────────────────────────────────────────────────────


class AttendanceCreate(BaseModel):
    session_id: int
    deputy_id: int
    status: AttendanceStatus = AttendanceStatus.present
    note: Optional[str] = None


class AttendanceUpdate(BaseModel):
    status: Optional[AttendanceStatus] = None
    note: Optional[str] = None


class AttendanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    session_id: int
    deputy_id: int
    status: AttendanceStatus
    note: Optional[str]


# ─── Health ───────────────────────────────────────────────────────────────────


class HealthOut(BaseModel):
    status: str
    database: str
    version: str
