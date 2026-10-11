"""Unit-тесты валидации входных данных (Pydantic-схемы): ошибочные данные и границы."""

import pytest
from pydantic import ValidationError

from app.schemas import (
    AttendanceCreate,
    CommissionCreate,
    DeputyCreate,
    DeputyUpdate,
    SessionCreate,
)

pytestmark = pytest.mark.unit


def test_deputy_name_is_normalized():
    assert DeputyCreate(full_name="  Петров  Пётр ").full_name == "Петров Пётр"


@pytest.mark.parametrize("name", ["", "   "])
def test_deputy_empty_name_rejected(name):
    with pytest.raises(ValidationError):
        DeputyCreate(full_name=name)


def test_deputy_name_length_boundary():
    DeputyCreate(full_name="А" * 200)
    with pytest.raises(ValidationError):
        DeputyCreate(full_name="А" * 201)


def test_deputy_update_blank_name_rejected():
    with pytest.raises(ValidationError):
        DeputyUpdate(full_name="  ")


def test_deputy_update_partial_is_allowed():
    assert DeputyUpdate(party="КПРФ").model_dump(exclude_unset=True) == {"party": "КПРФ"}


def test_commission_blank_name_rejected():
    with pytest.raises(ValidationError):
        CommissionCreate(name="   ")


def test_session_requires_valid_date_and_topic():
    with pytest.raises(ValidationError):
        SessionCreate(commission_id=1, held_on="2026-13-40", topic="Тема")
    with pytest.raises(ValidationError):
        SessionCreate(commission_id=1, held_on="2026-10-01", topic="  ")


def test_session_unknown_status_rejected():
    with pytest.raises(ValidationError):
        SessionCreate(commission_id=1, held_on="2026-10-01", topic="Тема", status="done")


def test_attendance_unknown_status_rejected():
    with pytest.raises(ValidationError):
        AttendanceCreate(session_id=1, deputy_id=1, status="late")


def test_attendance_note_length_boundary():
    AttendanceCreate(session_id=1, deputy_id=1, note="x" * 300)
    with pytest.raises(ValidationError):
        AttendanceCreate(session_id=1, deputy_id=1, note="x" * 301)
