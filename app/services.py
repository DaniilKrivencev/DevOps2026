"""Чистая бизнес-логика приложения (без БД и HTTP) — покрывается unit-тестами.

Правила из ТЗ:
  Ф2.4 — председатель комиссии обязан входить в её состав;
  Ф3.3 — заседание можно провести только при кворуме (> 50% членов присутствуют);
  Ф4.3 — одна запись посещаемости на пару «депутат + заседание».
"""

from __future__ import annotations

from collections.abc import Iterable

from app.models import AgendaDecision, AttendanceStatus, SessionStatus

MAX_FULL_NAME_LENGTH = 200


def has_quorum(present: int, total_members: int) -> bool:
    """Кворум есть, если присутствует строго больше половины членов комиссии."""
    if present < 0 or total_members < 0:
        raise ValueError("counts must be non-negative")
    if present > total_members:
        raise ValueError("present cannot exceed total members")
    # при total_members == 0 present тоже 0, и 0 > 0 — False: пустая комиссия без кворума
    return present * 2 > total_members


def quorum_threshold(total_members: int) -> int:
    """Минимальное число присутствующих для кворума."""
    if total_members < 0:
        raise ValueError("total_members must be non-negative")
    return total_members // 2 + 1


def chair_allowed(chair_id: int | None, member_ids: Iterable[int]) -> bool:
    """Председателем может быть только член комиссии (или председатель не задан)."""
    return chair_id is None or chair_id in set(member_ids)


def normalize_full_name(value: str) -> str:
    """Убирает лишние пробелы в ФИО и проверяет длину."""
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError("full_name must not be empty")
    if len(normalized) > MAX_FULL_NAME_LENGTH:
        raise ValueError(f"full_name must be at most {MAX_FULL_NAME_LENGTH} characters")
    return normalized


def attendance_rate(statuses: Iterable[AttendanceStatus]) -> float:
    """Доля посещённых заседаний в процентах (уважительная причина не считается явкой)."""
    items = list(statuses)
    if not items:
        return 0.0
    present = sum(1 for s in items if s == AttendanceStatus.present)
    return round(present * 100 / len(items), 2)


def decision_allowed(session_status: SessionStatus, decision: AgendaDecision) -> bool:
    """Решение по пункту повестки можно принять только на проведённом заседании."""
    if decision == AgendaDecision.pending:
        return True
    return session_status == SessionStatus.held
