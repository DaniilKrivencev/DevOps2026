"""Application database connection and session management."""

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_database_url

DATABASE_URL: str = get_database_url()


def make_engine(url: str):
    """Создаёт async-engine; для PostgreSQL включает проверку соединений."""
    kwargs = {"echo": False}
    if not url.startswith("sqlite"):
        kwargs["pool_pre_ping"] = True
    return create_async_engine(url, **kwargs)


@event.listens_for(Engine, "connect")
def _sqlite_foreign_keys(dbapi_connection, connection_record):
    """SQLite по умолчанию не проверяет внешние ключи — включаем (ON DELETE CASCADE)."""
    module = type(dbapi_connection).__module__
    if "sqlite" in module:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


engine = make_engine(DATABASE_URL)

AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    """FastAPI dependency — yields an async DB session."""
    async with AsyncSessionLocal() as session:
        yield session
