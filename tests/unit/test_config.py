"""Unit-тесты конфигурации: тестовое окружение изолировано от рабочей БД."""

import pytest

from app.config import DEFAULT_DATABASE_URL, DEFAULT_TEST_DATABASE_URL, get_database_url

pytestmark = pytest.mark.unit


def test_test_env_ignores_production_database_url(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://prod/prod")
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    assert get_database_url() == DEFAULT_TEST_DATABASE_URL


def test_test_env_uses_test_database_url(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("TEST_DATABASE_URL", "sqlite+aiosqlite:///tmp/x.db")
    assert get_database_url() == "sqlite+aiosqlite:///tmp/x.db"


def test_development_default(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert get_database_url() == DEFAULT_DATABASE_URL


def test_development_uses_database_url(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    assert get_database_url() == "postgresql+asyncpg://u:p@h/db"


def test_production_requires_database_url(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError):
        get_database_url()
