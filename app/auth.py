"""Базовая авторизация (HTTP Basic) и роли пользователей.

Учётные записи задаются переменной окружения AUTH_USERS:

    AUTH_USERS="admin:<пароль>:admin,secretary:<пароль>:secretary"

Роли:
  admin     — все изменяющие операции;
  secretary — ведение заседаний, повестки и посещаемости.
Чтение (GET) доступно без входа.

В production переменная AUTH_USERS обязательна; в development/test при её
отсутствии используются демонстрационные учётные записи (см. DEV_USERS).
"""

from __future__ import annotations

import hmac
import logging
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.config import get_app_env, get_auth_users_raw

logger = logging.getLogger("cityduma.auth")

ROLES = ("admin", "secretary")
# Только для локальной разработки и тестов, в production не используются.
DEV_USERS = "admin:admin:admin,secretary:secretary:secretary"

security = HTTPBasic(auto_error=False, realm="City Duma")


@dataclass(frozen=True)
class User:
    username: str
    role: str


def parse_users(raw: str) -> dict[str, tuple[str, str]]:
    """Разбирает строку AUTH_USERS → {логин: (пароль, роль)}."""
    users: dict[str, tuple[str, str]] = {}
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = chunk.split(":")
        if len(parts) != 3 or not all(parts):
            raise ValueError(f"AUTH_USERS: неверный формат записи '{parts[0]}:...'")
        username, password, role = parts
        if role not in ROLES:
            raise ValueError(f"AUTH_USERS: неизвестная роль '{role}' у '{username}'")
        users[username] = (password, role)
    if not users:
        raise ValueError("AUTH_USERS: не задано ни одной учётной записи")
    return users


def load_users() -> dict[str, tuple[str, str]]:
    raw = get_auth_users_raw()
    if not raw:
        if get_app_env() == "production":
            raise RuntimeError("AUTH_USERS must be set in production")
        raw = DEV_USERS
    return parse_users(raw)


def authenticate(username: str, password: str) -> User | None:
    """Проверка пароля за постоянное время (hmac.compare_digest)."""
    users = load_users()
    expected_password, role = users.get(username, ("", ""))
    ok = hmac.compare_digest(password.encode(), expected_password.encode())
    if not ok or not role:
        return None
    return User(username=username, role=role)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": 'Basic realm="City Duma"'},
    )


async def current_user(
    credentials: Annotated[HTTPBasicCredentials | None, Depends(security)],
) -> User:
    if credentials is None:
        raise _unauthorized("Authentication required")
    user = authenticate(credentials.username, credentials.password)
    if user is None:
        logger.warning("auth failed for user=%s", credentials.username)
        raise _unauthorized("Invalid username or password")
    return user


def require_roles(*roles: str):
    """Зависимость FastAPI: пускает только пользователей с одной из ролей."""

    async def checker(user: Annotated[User, Depends(current_user)]) -> User:
        if user.role not in roles:
            logger.warning("forbidden: user=%s role=%s needs=%s", user.username, user.role, roles)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough rights")
        return user

    return checker


require_admin = require_roles("admin")
require_secretary = require_roles("admin", "secretary")
