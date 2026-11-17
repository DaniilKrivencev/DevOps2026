"""Тестовая конфигурация.

Изоляция тестовых данных:
  - APP_ENV=test выставляется ДО импорта приложения, поэтому рабочий
    DATABASE_URL никогда не используется тестами (см. app/config.py);
  - каждый тест получает собственную чистую БД: отдельный SQLite-файл
    во временном каталоге pytest (tmp_path), либо, если задан
    TEST_DATABASE_URL на PostgreSQL, схема пересоздаётся для каждого теста.
"""

import os

os.environ["APP_ENV"] = "test"

# Импорты ниже идут после выставления APP_ENV намеренно (E402 разрешён для
# этого файла в pyproject.toml с обоснованием).
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.models  # noqa: F401 — импорт регистрирует модели в Base.metadata
from app.database import Base, get_db, make_engine
from app.main import app as fastapi_app

PG_TEST_URL = os.getenv("TEST_DATABASE_URL", "")
USE_POSTGRES = PG_TEST_URL.startswith("postgresql")


@pytest.fixture
def db_url(tmp_path) -> str:
    if USE_POSTGRES:
        return PG_TEST_URL
    return f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"


@pytest.fixture
async def db_engine(db_url):
    engine = make_engine(db_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    maker = async_sessionmaker(bind=db_engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session


@pytest.fixture
async def client(db_engine):
    maker = async_sessionmaker(bind=db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with maker() as session:
            yield session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as ac:
        yield ac
    fastapi_app.dependency_overrides.clear()


# ─── Фабрики тестовых данных ──────────────────────────────────────────────────


@pytest.fixture
def make_deputy(client):
    counter = {"n": 0}

    async def _make(**fields):
        counter["n"] += 1
        payload = {"full_name": f"Депутат Тестовый {counter['n']}", **fields}
        r = await client.post("/api/v1/deputies/", json=payload)
        assert r.status_code == 201, r.text
        return r.json()

    return _make


@pytest.fixture
def make_commission(client):
    counter = {"n": 0}

    async def _make(**fields):
        counter["n"] += 1
        payload = {"name": f"Комиссия {counter['n']}", **fields}
        r = await client.post("/api/v1/commissions/", json=payload)
        assert r.status_code == 201, r.text
        return r.json()

    return _make


@pytest.fixture
def make_session(client, make_commission):
    async def _make(commission_id=None, **fields):
        if commission_id is None:
            commission_id = (await make_commission())["id"]
        payload = {
            "commission_id": commission_id,
            "held_on": "2026-10-01",
            "topic": "Тестовая повестка",
            **fields,
        }
        r = await client.post("/api/v1/sessions/", json=payload)
        assert r.status_code == 201, r.text
        return r.json()

    return _make
