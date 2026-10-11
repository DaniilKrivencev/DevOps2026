"""Интеграционные тесты миграций Alembic.

Проверяется (п. 8–9 задания):
  - создание чистой БД цепочкой миграций 0001 → head;
  - обновление БД, уже содержащей данные (данные сохраняются, новые
    столбцы получают значения по умолчанию);
  - откат downgrade до base и повторный upgrade;
  - схема после миграций совпадает с ORM-моделями (нет «дрейфа»).
"""

import asyncio
import os
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from app.database import Base

pytestmark = pytest.mark.integration

LAB3_DIR = Path(__file__).resolve().parents[2]
EXPECTED_REVISIONS = ["0001", "0002", "0003"]


def _alembic_config(url: str) -> Config:
    cfg = Config(str(LAB3_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(LAB3_DIR / "alembic"))
    cfg.attributes["database_url"] = url
    return cfg


@pytest.fixture
def sqlite_db(tmp_path):
    path = tmp_path / "migrations.db"
    return path, f"sqlite+aiosqlite:///{path}"


def _tables(path: Path) -> set[str]:
    with sqlite3.connect(path) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {r[0] for r in rows}


def _columns(path: Path, table: str) -> set[str]:
    with sqlite3.connect(path) as conn:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def test_revision_chain_is_linear():
    script = ScriptDirectory.from_config(_alembic_config("sqlite://"))
    revisions = [rev.revision for rev in reversed(list(script.walk_revisions()))]
    assert revisions == EXPECTED_REVISIONS
    assert len(script.get_heads()) == 1


def test_clean_database_upgrade(sqlite_db):
    path, url = sqlite_db
    command.upgrade(_alembic_config(url), "head")
    assert {
        "deputies",
        "commissions",
        "commission_members",
        "sessions",
        "attendances",
        "alembic_version",
    } <= _tables(path)
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0003"


def test_upgrade_database_with_existing_data(sqlite_db):
    path, url = sqlite_db
    cfg = _alembic_config(url)
    command.upgrade(cfg, "0001")
    assert "email" not in _columns(path, "deputies")

    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO deputies (id, full_name, is_active) VALUES (1, 'Иванов', 1)")
        conn.execute("INSERT INTO commissions (id, name, chair_id) VALUES (1, 'Бюджет', 1)")
        conn.execute("INSERT INTO commission_members (commission_id, deputy_id) VALUES (1, 1)")
        conn.execute(
            "INSERT INTO sessions (id, commission_id, held_on, topic, status) "
            "VALUES (1, 1, '2026-01-15', 'Тема', 'planned')"
        )

    command.upgrade(cfg, "head")

    assert {"email", "phone"} <= _columns(path, "deputies")
    assert "is_active" in _columns(path, "commissions")
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT full_name, email FROM deputies").fetchall() == [
            ("Иванов", None)
        ]
        assert conn.execute("SELECT name, chair_id, is_active FROM commissions").fetchall() == [
            ("Бюджет", 1, 1)
        ]
        assert conn.execute("SELECT count(*) FROM commission_members").fetchone()[0] == 1
        assert conn.execute("SELECT topic FROM sessions").fetchone()[0] == "Тема"


def test_unique_email_enforced_after_migration(sqlite_db):
    path, url = sqlite_db
    command.upgrade(_alembic_config(url), "head")
    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO deputies (full_name, is_active, email) VALUES ('A', 1, 'a@b.ru')")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO deputies (full_name, is_active, email) VALUES ('B', 1, 'a@b.ru')"
            )


def test_downgrade_to_base_and_upgrade_again(sqlite_db):
    path, url = sqlite_db
    cfg = _alembic_config(url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "0002")
    assert "is_active" not in _columns(path, "commissions")
    assert "email" in _columns(path, "deputies")
    command.downgrade(cfg, "base")
    assert _tables(path) <= {"alembic_version"}
    command.upgrade(cfg, "head")
    assert "is_active" in _columns(path, "commissions")


def test_migrations_match_models(sqlite_db):
    path, url = sqlite_db
    command.upgrade(_alembic_config(url), "head")
    engine = create_engine(f"sqlite:///{path}")
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    engine.dispose()
    assert diff == []


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL", "").startswith("postgresql"),
    reason="обоснование: PostgreSQL-вариант запускается через make test-pg",
)
def test_postgres_clean_upgrade_and_downgrade():
    url = os.environ["TEST_DATABASE_URL"]
    cfg = _alembic_config(url)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")

    async def _version():
        from sqlalchemy import text

        from app.database import make_engine

        engine = make_engine(url)
        async with engine.connect() as conn:
            value = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
        await engine.dispose()
        return value

    assert asyncio.run(_version()) == "0003"
    command.downgrade(cfg, "base")
