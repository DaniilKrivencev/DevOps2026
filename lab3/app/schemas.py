"""Pydantic schemas for request/response validation."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import AttendanceStatus, SessionStatus

# Простая проверка формата e-mail без внешних зависимостей
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
PHONE_PATTERN = r"^\+?[0-9\-\s()]{5,20}$"

# ─── Deputy ──────────────────────────────────────────────────────────────────


class DeputyBase(BaseModel):
    full_name: str
    party: str | None = None
    district: str | None = None
    elected_on: date | None = None
    is_active: bool = True
    email: str | None = Field(default=None, max_length=254, pattern=EMAIL_PATTERN)
    phone: str | None = Field(default=None, max_length=20, pattern=PHONE_PATTERN)


class DeputyCreate(DeputyBase):
    @field_validator("full_name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("full_name must not be empty")
        return v.strip()


class DeputyUpdate(BaseModel):
    full_name: str | None = None
    party: str | None = None
    district: str | None = None
    elected_on: date | None = None
    is_active: bool | None = None
    email: str | None = Field(default=None, max_length=254, pattern=EMAIL_PATTERN)
    phone: str | None = Field(default=None, max_length=20, pattern=PHONE_PATTERN)


class DeputyOut(DeputyBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


# ─── Commission ───────────────────────────────────────────────────────────────


class CommissionBase(BaseModel):
    name: str
    description: str | None = None
    chair_id: int | None = None


class CommissionCreate(CommissionBase):
    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be empty")
        return v.strip()


class CommissionUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    chair_id: int | None = None


class CommissionOut(CommissionBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


# ─── CommissionMember ─────────────────────────────────────────────────────────


class CommissionMemberCreate(BaseModel):
    deputy_id: int
    joined_on: date | None = None


class CommissionMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    commission_id: int
    deputy_id: int
    joined_on: date | None


# ─── Session ─────────────────────────────────────────────────────────────────


class SessionBase(BaseModel):
    commission_id: int
    held_on: date
    topic: str
    status: SessionStatus = SessionStatus.planned
    notes: str | None = None


class SessionCreate(SessionBase):
    @field_validator("topic")
    @classmethod
    def topic_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("topic must not be empty")
        return v.strip()


class SessionUpdate(BaseModel):
    held_on: date | None = None
    topic: str | None = None
    status: SessionStatus | None = None
    notes: str | None = None


class SessionOut(SessionBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


# ─── Attendance ───────────────────────────────────────────────────────────────


class AttendanceCreate(BaseModel):
    session_id: int
    deputy_id: int
    status: AttendanceStatus = AttendanceStatus.present
    note: str | None = None


class AttendanceUpdate(BaseModel):
    status: AttendanceStatus | None = None
    note: str | None = None


class AttendanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    session_id: int
    deputy_id: int
    status: AttendanceStatus
    note: str | None


# ─── Health ───────────────────────────────────────────────────────────────────


class HealthOut(BaseModel):
    status: str
    database: str
    version: str
