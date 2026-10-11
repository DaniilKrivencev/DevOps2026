"""Конфигурация приложения через переменные окружения.

Окружения:
  development — локальная работа (по умолчанию SQLite-файл cityduma.db)
  production  — PostgreSQL, DATABASE_URL обязателен
  test        — отдельная тестовая БД (TEST_DATABASE_URL), никогда не рабочая
"""

import os

from dotenv import load_dotenv

# .env не переопределяет уже заданные переменные окружения
load_dotenv()

DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./cityduma.db"
DEFAULT_TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"


def get_app_env() -> str:
    return os.getenv("APP_ENV", "development")


def get_database_url() -> str:
    """Возвращает DSN БД с учётом окружения.

    В тестовом окружении рабочий DATABASE_URL игнорируется, чтобы тесты
    не могли случайно изменить рабочие данные.
    """
    if get_app_env() == "test":
        return os.getenv("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
    url = os.getenv("DATABASE_URL")
    if not url:
        if get_app_env() == "production":
            raise RuntimeError("DATABASE_URL must be set in production")
        return DEFAULT_DATABASE_URL
    return url
