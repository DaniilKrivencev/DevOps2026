"""Интеграционные тесты резервного копирования и восстановления (п. 11–12)."""

import sqlite3

import pytest

from alembic import command
from scripts import db_backup
from tests.integration.test_migrations import _alembic_config

pytestmark = pytest.mark.integration


@pytest.fixture
def populated_db(tmp_path):
    path = tmp_path / "prod.db"
    url = f"sqlite+aiosqlite:///{path}"
    command.upgrade(_alembic_config(url), "head")
    with sqlite3.connect(path) as conn:
        conn.executemany(
            "INSERT INTO deputies (full_name, is_active) VALUES (?, 1)",
            [("Иванов",), ("Петров",), ("Сидоров",)],
        )
    return path, url


def _names(path):
    with sqlite3.connect(path) as conn:
        return [r[0] for r in conn.execute("SELECT full_name FROM deputies ORDER BY id")]


def test_backup_creates_file(populated_db, tmp_path):
    _, url = populated_db
    out = db_backup.backup(url, tmp_path / "backups" / "dump.sqlite")
    assert out.exists() and out.stat().st_size > 0
    assert _names(out) == ["Иванов", "Петров", "Сидоров"]


def test_restore_after_intentional_delete(populated_db, tmp_path):
    path, url = populated_db
    dump = db_backup.backup(url, tmp_path / "dump.sqlite")

    with sqlite3.connect(path) as conn:  # намеренное удаление
        conn.execute("DELETE FROM deputies")
    assert _names(path) == []

    db_backup.restore(url, dump)
    assert _names(path) == ["Иванов", "Петров", "Сидоров"]


def test_restore_after_intentional_modification(populated_db, tmp_path):
    path, url = populated_db
    dump = db_backup.backup(url, tmp_path / "dump.sqlite")

    with sqlite3.connect(path) as conn:  # намеренное изменение
        conn.execute("UPDATE deputies SET full_name = 'ИСПОРЧЕНО'")
        conn.execute("INSERT INTO deputies (full_name, is_active) VALUES ('Лишний', 1)")

    db_backup.restore(url, dump)
    assert _names(path) == ["Иванов", "Петров", "Сидоров"]


def test_restore_missing_file(populated_db, tmp_path):
    _, url = populated_db
    with pytest.raises(FileNotFoundError):
        db_backup.restore(url, tmp_path / "nope.sqlite")


def test_default_backup_name():
    assert db_backup.default_backup_name("sqlite+aiosqlite:///x.db").suffix == ".sqlite"
    name = db_backup.default_backup_name("postgresql+asyncpg://u:p@h/db")
    assert name.suffix == ".sql" and name.parent.name == "backups"


def test_pg_params_parsing(monkeypatch):
    monkeypatch.delenv("PGPASSWORD", raising=False)
    args, env = db_backup._pg_params("postgresql+asyncpg://duma:p%40ss@db.local:6543/city")
    assert args == ["-h", "db.local", "-p", "6543", "-U", "duma", "-d", "city"]
    assert env["PGPASSWORD"] == "p@ss"


def test_cli_backup_and_restore(populated_db, tmp_path, monkeypatch, capsys):
    path, url = populated_db
    monkeypatch.setenv("TEST_DATABASE_URL", url)  # APP_ENV=test → используется этот URL
    dump = tmp_path / "cli.sqlite"
    assert db_backup.main(["backup", "--output", str(dump)]) == 0
    with sqlite3.connect(path) as conn:
        conn.execute("DELETE FROM deputies WHERE full_name = 'Петров'")
    assert db_backup.main(["restore", str(dump)]) == 0
    assert _names(path) == ["Иванов", "Петров", "Сидоров"]
    assert "Restored from" in capsys.readouterr().out


async def test_seed_is_idempotent(populated_db, monkeypatch, capsys):
    """scripts/seed.py: наполняет пустую БД и не дублирует данные повторно."""
    from scripts import seed as seed_module

    path, url = populated_db
    with sqlite3.connect(path) as conn:
        conn.execute("DELETE FROM deputies")

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.database import make_engine

    engine = make_engine(url)
    monkeypatch.setattr(seed_module, "engine", engine)
    monkeypatch.setattr(
        seed_module,
        "AsyncSessionLocal",
        async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False),
    )
    await seed_module.seed()
    assert len(_names(path)) == 3
    await seed_module.seed()
    assert len(_names(path)) == 3
    assert "пропуск" in capsys.readouterr().out
    await engine.dispose()
