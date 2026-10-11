"""Резервное копирование и восстановление БД «Городская Дума».

Использование:
  python -m scripts.db_backup backup [--output FILE]
  python -m scripts.db_backup restore FILE

Поддерживаются:
  - PostgreSQL — через pg_dump / psql (формат: plain SQL, с --clean);
  - SQLite     — через встроенный sqlite3 backup API (копия файла БД).
URL берётся из конфигурации приложения (DATABASE_URL / APP_ENV).
"""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3

# Обоснование nosec: вызываются только pg_dump/psql со списком аргументов, без shell
import subprocess  # nosec B404
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

from app.config import get_database_url

BACKUP_DIR = Path("backups")


def _sqlite_path(url: str) -> Path:
    # sqlite+aiosqlite:///./cityduma.db -> ./cityduma.db
    return Path(url.split(":///", 1)[1])


def _pg_params(url: str) -> tuple[list[str], dict[str, str]]:
    """Преобразует SQLAlchemy URL в аргументы libpq-утилит и окружение с паролем."""
    parsed = urlparse(url.replace("+asyncpg", "").replace("+psycopg2", ""))
    args = [
        "-h",
        parsed.hostname or "localhost",
        "-p",
        str(parsed.port or 5432),
        "-U",
        unquote(parsed.username or "postgres"),
        "-d",
        parsed.path.lstrip("/"),
    ]
    env = dict(os.environ)
    if parsed.password:
        env["PGPASSWORD"] = unquote(parsed.password)
    return args, env


def _require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"{name} not found in PATH")
    return path


def default_backup_name(url: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = "sqlite" if url.startswith("sqlite") else "sql"
    return BACKUP_DIR / f"dump_{stamp}.{ext}"


def backup(url: str, output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    if url.startswith("sqlite"):
        src = sqlite3.connect(_sqlite_path(url))
        dst = sqlite3.connect(output)
        with dst:
            src.backup(dst)
        src.close()
        dst.close()
    else:
        args, env = _pg_params(url)
        cmd = [_require_tool("pg_dump"), *args, "--clean", "--if-exists", "--no-owner"]
        with output.open("w", encoding="utf-8") as fh:
            # Обоснование noqa/nosec: фиксированная команда, список аргументов, без shell
            subprocess.run(cmd, stdout=fh, env=env, check=True)  # noqa: S603  # nosec B603
    return output


def restore(url: str, source: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(source)
    if url.startswith("sqlite"):
        src = sqlite3.connect(source)
        dst = sqlite3.connect(_sqlite_path(url))
        with dst:
            src.backup(dst)
        src.close()
        dst.close()
    else:
        args, env = _pg_params(url)
        cmd = [_require_tool("psql"), *args, "-v", "ON_ERROR_STOP=1", "-q", "-f", str(source)]
        # Обоснование noqa/nosec: фиксированная команда, список аргументов, без shell
        subprocess.run(cmd, env=env, check=True, stdout=subprocess.DEVNULL)  # noqa: S603  # nosec B603


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p_backup = sub.add_parser("backup", help="создать резервную копию")
    p_backup.add_argument("--output", type=Path, default=None)
    p_restore = sub.add_parser("restore", help="восстановить из резервной копии")
    p_restore.add_argument("file", type=Path)
    args = parser.parse_args(argv)

    url = get_database_url()
    if args.command == "backup":
        path = backup(url, args.output or default_backup_name(url))
        print(f"Backup created: {path}")
    else:
        restore(url, args.file)
        print(f"Restored from: {args.file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
