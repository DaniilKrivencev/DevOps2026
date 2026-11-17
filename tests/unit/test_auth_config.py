"""Разбор AUTH_USERS и проверка паролей (unit)."""

import pytest

from app import auth

pytestmark = pytest.mark.unit


def test_parse_users_ok():
    users = auth.parse_users(" admin:p1:admin , sec:p2:secretary ,")
    assert users == {"admin": ("p1", "admin"), "sec": ("p2", "secretary")}


@pytest.mark.parametrize("raw", ["admin:p1", "admin::admin", ":p:admin", "a:b:c:d"])
def test_parse_users_bad_format(raw):
    with pytest.raises(ValueError, match="неверный формат"):
        auth.parse_users(raw)


def test_parse_users_unknown_role():
    with pytest.raises(ValueError, match="неизвестная роль"):
        auth.parse_users("u:p:root")


def test_parse_users_empty():
    with pytest.raises(ValueError, match="ни одной"):
        auth.parse_users(" , ")


def test_dev_users_used_outside_production(monkeypatch):
    monkeypatch.delenv("AUTH_USERS", raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    assert auth.load_users()["admin"] == ("admin", "admin")


def test_production_requires_auth_users(monkeypatch):
    monkeypatch.delenv("AUTH_USERS", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(RuntimeError, match="AUTH_USERS"):
        auth.load_users()


def test_env_users_override_dev(monkeypatch):
    monkeypatch.setenv("AUTH_USERS", "boss:s3cret:admin")
    assert auth.authenticate("boss", "s3cret") == auth.User("boss", "admin")
    assert auth.authenticate("admin", "admin") is None
    assert auth.authenticate("boss", "S3cret") is None
