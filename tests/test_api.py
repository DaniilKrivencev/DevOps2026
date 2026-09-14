"""API and integration tests for City Duma application.

Tests run against a real PostgreSQL database (via TEST_DATABASE_URL env var)
OR use an in-memory SQLite database for unit-level tests.

Run: make test
"""

import os
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Use SQLite for tests (no PostgreSQL required in CI by default)
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "sqlite+aiosqlite:///./test.db"
)

# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    # Create tables
    from app.database import Base
    import app.models  # noqa: F401 — register models
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(scope="session")
async def client(db_engine):
    from app.main import app
    from app.database import get_db

    TestSessionLocal = sessionmaker(
        bind=db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ─── Health ───────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "version" in data


# ─── Deputies ─────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_create_deputy(client):
    payload = {"full_name": "Иванов Иван Иванович", "party": "Единая Россия", "district": "№1"}
    r = await client.post("/api/v1/deputies/", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["full_name"] == "Иванов Иван Иванович"
    assert data["id"] > 0


@pytest.mark.anyio
async def test_create_deputy_empty_name(client):
    r = await client.post("/api/v1/deputies/", json={"full_name": "  "})
    assert r.status_code == 422


@pytest.mark.anyio
async def test_list_deputies(client):
    r = await client.get("/api/v1/deputies/")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert len(r.json()) >= 1


@pytest.mark.anyio
async def test_get_deputy_not_found(client):
    r = await client.get("/api/v1/deputies/99999")
    assert r.status_code == 404


@pytest.mark.anyio
async def test_update_deputy(client):
    # first create
    r = await client.post("/api/v1/deputies/", json={"full_name": "Петров Пётр Петрович"})
    deputy_id = r.json()["id"]
    r2 = await client.patch(f"/api/v1/deputies/{deputy_id}", json={"party": "КПРФ"})
    assert r2.status_code == 200
    assert r2.json()["party"] == "КПРФ"


@pytest.mark.anyio
async def test_delete_deputy(client):
    r = await client.post("/api/v1/deputies/", json={"full_name": "Сидоров Сидор"})
    deputy_id = r.json()["id"]
    r2 = await client.delete(f"/api/v1/deputies/{deputy_id}")
    assert r2.status_code == 204
    r3 = await client.get(f"/api/v1/deputies/{deputy_id}")
    assert r3.status_code == 404


# ─── Commissions ─────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_create_commission(client):
    r = await client.post("/api/v1/commissions/", json={"name": "Комиссия по бюджету"})
    assert r.status_code == 201
    assert r.json()["name"] == "Комиссия по бюджету"


@pytest.mark.anyio
async def test_commission_chair_must_be_member(client):
    """Business rule: setting a chair who is not a member must fail with 422."""
    # Create deputy
    dep_r = await client.post("/api/v1/deputies/", json={"full_name": "Новый Депутат"})
    dep_id = dep_r.json()["id"]
    # Create commission
    comm_r = await client.post("/api/v1/commissions/", json={"name": "Тестовая комиссия БПМ"})
    comm_id = comm_r.json()["id"]
    # Try to set chair without membership → must be 422
    r = await client.patch(f"/api/v1/commissions/{comm_id}", json={"chair_id": dep_id})
    assert r.status_code == 422


@pytest.mark.anyio
async def test_commission_chair_as_member(client):
    """After adding deputy as member, setting chair must succeed."""
    dep_r = await client.post("/api/v1/deputies/", json={"full_name": "Председатель Тест"})
    dep_id = dep_r.json()["id"]
    comm_r = await client.post("/api/v1/commissions/", json={"name": "Комиссия по ЖКХ"})
    comm_id = comm_r.json()["id"]
    # Add as member
    mr = await client.post(f"/api/v1/commissions/{comm_id}/members", json={"deputy_id": dep_id})
    assert mr.status_code == 201
    # Now set as chair
    ur = await client.patch(f"/api/v1/commissions/{comm_id}", json={"chair_id": dep_id})
    assert ur.status_code == 200
    assert ur.json()["chair_id"] == dep_id


# ─── Sessions ─────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_create_session(client):
    comm_r = await client.post("/api/v1/commissions/", json={"name": "Комиссия по спорту"})
    comm_id = comm_r.json()["id"]
    payload = {"commission_id": comm_id, "held_on": "2026-10-01", "topic": "Финансирование стадиона"}
    r = await client.post("/api/v1/sessions/", json=payload)
    assert r.status_code == 201
    assert r.json()["status"] == "planned"


@pytest.mark.anyio
async def test_session_quorum_check(client):
    """Marking session as 'held' without quorum must fail."""
    comm_r = await client.post("/api/v1/commissions/", json={"name": "Малая комиссия"})
    comm_id = comm_r.json()["id"]
    sess_r = await client.post("/api/v1/sessions/", json={
        "commission_id": comm_id, "held_on": "2026-11-01", "topic": "Тест кворума"
    })
    sess_id = sess_r.json()["id"]
    # Try to mark as held with 0 members → quorum fails
    r = await client.patch(f"/api/v1/sessions/{sess_id}", json={"status": "held"})
    assert r.status_code == 422


# ─── Attendance ───────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_create_attendance(client):
    dep_r = await client.post("/api/v1/deputies/", json={"full_name": "Явный Депутат"})
    dep_id = dep_r.json()["id"]
    comm_r = await client.post("/api/v1/commissions/", json={"name": "Комиссия по образованию"})
    comm_id = comm_r.json()["id"]
    sess_r = await client.post("/api/v1/sessions/", json={
        "commission_id": comm_id, "held_on": "2026-09-15", "topic": "Школьная реформа"
    })
    sess_id = sess_r.json()["id"]
    payload = {"session_id": sess_id, "deputy_id": dep_id, "status": "present"}
    r = await client.post("/api/v1/attendance/", json=payload)
    assert r.status_code == 201
    assert r.json()["status"] == "present"


@pytest.mark.anyio
async def test_attendance_duplicate(client):
    dep_r = await client.post("/api/v1/deputies/", json={"full_name": "Дубль Депутат"})
    dep_id = dep_r.json()["id"]
    comm_r = await client.post("/api/v1/commissions/", json={"name": "Ещё одна комиссия"})
    comm_id = comm_r.json()["id"]
    sess_r = await client.post("/api/v1/sessions/", json={
        "commission_id": comm_id, "held_on": "2026-09-20", "topic": "Дубль тест"
    })
    sess_id = sess_r.json()["id"]
    payload = {"session_id": sess_id, "deputy_id": dep_id, "status": "present"}
    await client.post("/api/v1/attendance/", json=payload)
    r2 = await client.post("/api/v1/attendance/", json=payload)
    assert r2.status_code == 409
