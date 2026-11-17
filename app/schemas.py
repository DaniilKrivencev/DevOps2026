"""Pydantic schemas for request/response validation."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import AgendaDecision, AttendanceStatus, SessionStatus
from app.services import normalize_full_name

# Простая проверка формата e-mail без внешних зависимостей
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
PHONE_PATTERN = r"^\+?[0-9\-\s()]{5,20}$"


# ─── Deputy ──────────────────────────────────────────────────────────────────


class DeputyBase(BaseModel):
    full_name: str = Field(max_length=200)
    party: str | None = Field(default=None, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    elected_on: date | None = None
    is_active: bool = True
    email: str | None = Field(default=None, max_length=254, pattern=EMAIL_PATTERN)
    phone: str | None = Field(default=None, max_length=20, pattern=PHONE_PATTERN)


class DeputyCreate(DeputyBase):
    @field_validator("full_name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        return normalize_full_name(v)


class DeputyUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=200)
    party: str | None = Field(default=None, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    elected_on: date | None = None
    is_active: bool | None = None
    email: str | None = Field(default=None, max_length=254, pattern=EMAIL_PATTERN)
    phone: str | None = Field(default=None, max_length=20, pattern=PHONE_PATTERN)

    @field_validator("full_name")
    @classmethod
    def name_not_empty(cls, v: str | None) -> str | None:
        return None if v is None else normalize_full_name(v)


class DeputyOut(DeputyBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime | None = None


# ─── Commission ───────────────────────────────────────────────────────────────


class CommissionBase(BaseModel):
    name: str = Field(max_length=200)
    description: str | None = None
    chair_id: int | None = None
    is_active: bool = True


class CommissionCreate(CommissionBase):
    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be empty")
        return v.strip()


class CommissionUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    description: str | None = None
    chair_id: int | None = None
    is_active: bool | None = None


class CommissionOut(CommissionBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime | None = None


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
    topic: str = Field(max_length=500)
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
    topic: str | None = Field(default=None, max_length=500)
    status: SessionStatus | None = None
    notes: str | None = None


class SessionOut(SessionBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime | None = None


# ─── Attendance ───────────────────────────────────────────────────────────────


class AttendanceCreate(BaseModel):
    session_id: int
    deputy_id: int
    status: AttendanceStatus = AttendanceStatus.present
    note: str | None = Field(default=None, max_length=300)


class AttendanceUpdate(BaseModel):
    status: AttendanceStatus | None = None
    note: str | None = Field(default=None, max_length=300)


class AttendanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    session_id: int
    deputy_id: int
    status: AttendanceStatus
    note: str | None


# ─── AgendaItem (ЛР3) ─────────────────────────────────────────────────────────


class AgendaItemCreate(BaseModel):
    position: int = Field(ge=1, le=999)
    title: str = Field(min_length=1, max_length=300)

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title must not be empty")
        return v.strip()


class AgendaItemUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    decision: AgendaDecision | None = None


class AgendaItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    session_id: int
    position: int
    title: str
    decision: AgendaDecision


# ─── Health ───────────────────────────────────────────────────────────────────


class HealthOut(BaseModel):
    status: str
    database: str
    version: str
