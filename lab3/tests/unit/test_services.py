"""Unit-тесты чистой бизнес-логики (app/services.py).

Включают граничные случаи, «убивающие» типичные мутанты:
  > / >=, * 2 / / 2, total == 0, off-by-one в пороге кворума.
"""

import pytest

from app.models import AgendaDecision, AttendanceStatus, SessionStatus
from app.services import (
    MAX_FULL_NAME_LENGTH,
    attendance_rate,
    chair_allowed,
    decision_allowed,
    has_quorum,
    normalize_full_name,
    quorum_threshold,
)

pytestmark = pytest.mark.unit


# ─── Кворум (Ф3.3) ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("present", "total", "expected"),
    [
        (0, 0, False),  # нет членов — кворума нет никогда
        (0, 1, False),
        (1, 1, True),
        (1, 2, False),  # ровно 50% — НЕ кворум (нужно строго больше)
        (2, 2, True),
        (1, 3, False),
        (2, 3, True),  # 66% — кворум
        (2, 4, False),  # граница 50%
        (3, 4, True),
        (5, 10, False),
        (6, 10, True),
        (50, 101, False),
        (51, 101, True),
    ],
)
def test_has_quorum_boundaries(present, total, expected):
    assert has_quorum(present, total) is expected


@pytest.mark.parametrize(
    ("present", "total", "message"),
    [
        (-1, 5, "^counts must be non-negative$"),
        (1, -1, "^counts must be non-negative$"),
        (6, 5, "^present cannot exceed total members$"),
    ],
)
def test_has_quorum_rejects_invalid_counts(present, total, message):
    with pytest.raises(ValueError, match=message):
        has_quorum(present, total)


@pytest.mark.parametrize(
    ("total", "threshold"), [(0, 1), (1, 1), (2, 2), (3, 2), (4, 3), (10, 6), (11, 6)]
)
def test_quorum_threshold(total, threshold):
    assert quorum_threshold(total) == threshold


def test_quorum_threshold_is_consistent_with_has_quorum():
    for total in range(1, 30):
        t = quorum_threshold(total)
        assert has_quorum(t, total)
        assert not has_quorum(t - 1, total)


def test_quorum_threshold_negative():
    with pytest.raises(ValueError, match="^total_members must be non-negative$"):
        quorum_threshold(-1)


# ─── Председатель — член комиссии (Ф2.4) ──────────────────────────────────────


def test_chair_allowed_when_member():
    assert chair_allowed(5, [1, 5, 7]) is True


def test_chair_not_allowed_when_not_member():
    assert chair_allowed(2, [1, 5, 7]) is False


def test_chair_not_allowed_for_empty_commission():
    assert chair_allowed(1, []) is False


def test_no_chair_is_always_allowed():
    assert chair_allowed(None, []) is True


# ─── ФИО ──────────────────────────────────────────────────────────────────────


def test_normalize_full_name_collapses_spaces():
    assert normalize_full_name("  Иванов   Иван\tИванович ") == "Иванов Иван Иванович"


@pytest.mark.parametrize("value", ["", "   ", "\t\n"])
def test_normalize_full_name_empty(value):
    with pytest.raises(ValueError, match="^full_name must not be empty$"):
        normalize_full_name(value)


def test_max_full_name_length_matches_db_column():
    assert MAX_FULL_NAME_LENGTH == 200  # deputies.full_name VARCHAR(200)


def test_normalize_full_name_max_length_boundary():
    exact = "Я" * MAX_FULL_NAME_LENGTH
    assert normalize_full_name(exact) == exact
    with pytest.raises(ValueError, match="^full_name must be at most 200 characters$"):
        normalize_full_name(exact + "Я")


# ─── Процент посещаемости ─────────────────────────────────────────────────────


def test_attendance_rate_empty():
    assert attendance_rate([]) == 0.0


def test_attendance_rate_mixed():
    statuses = [
        AttendanceStatus.present,
        AttendanceStatus.absent,
        AttendanceStatus.excused,
        AttendanceStatus.present,
    ]
    assert attendance_rate(statuses) == 50.0


def test_attendance_rate_rounding():
    statuses = [AttendanceStatus.present, AttendanceStatus.absent, AttendanceStatus.absent]
    assert attendance_rate(statuses) == 33.33


def test_attendance_rate_all_present():
    assert attendance_rate([AttendanceStatus.present] * 3) == 100.0


# ─── Решения по повестке ──────────────────────────────────────────────────────


@pytest.mark.parametrize("status", list(SessionStatus))
def test_pending_decision_always_allowed(status):
    assert decision_allowed(status, AgendaDecision.pending) is True


@pytest.mark.parametrize("decision", [AgendaDecision.adopted, AgendaDecision.rejected])
def test_final_decision_only_for_held_session(decision):
    assert decision_allowed(SessionStatus.held, decision) is True
    assert decision_allowed(SessionStatus.planned, decision) is False
    assert decision_allowed(SessionStatus.cancelled, decision) is False
