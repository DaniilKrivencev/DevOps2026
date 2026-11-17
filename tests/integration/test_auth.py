"""Авторизация: чтение без входа, изменения — только с ролью (ЛР1, п. 6)."""

import pytest

from tests.conftest import SECRETARY

pytestmark = pytest.mark.integration

DEPUTY = {"full_name": "Иванов Иван Иванович"}


async def test_read_is_public(make_client, make_deputy):
    await make_deputy()
    anon = make_client(None)
    r = await anon.get("/api/v1/deputies/")
    assert r.status_code == 200
    assert len(r.json()) == 1


async def test_write_without_credentials_is_401(make_client):
    anon = make_client(None)
    r = await anon.post("/api/v1/deputies/", json=DEPUTY)
    assert r.status_code == 401
    assert r.headers["www-authenticate"].startswith("Basic")


async def test_wrong_password_is_401(make_client):
    bad = make_client(("admin", "wrong"))
    r = await bad.post("/api/v1/deputies/", json=DEPUTY)
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid username or password"


async def test_unknown_user_is_401(make_client):
    r = await make_client(("ghost", "admin")).delete("/api/v1/deputies/1")
    assert r.status_code == 401


async def test_secretary_cannot_manage_deputies(make_client):
    sec = make_client(SECRETARY)
    r = await sec.post("/api/v1/deputies/", json=DEPUTY)
    assert r.status_code == 403
    assert r.json()["detail"] == "Not enough rights"


async def test_secretary_manages_sessions_and_attendance(make_client, make_commission, make_deputy):
    commission = await make_commission()
    deputy = await make_deputy()
    sec = make_client(SECRETARY)
    r = await sec.post(
        "/api/v1/sessions/",
        json={"commission_id": commission["id"], "held_on": "2026-11-01", "topic": "Бюджет"},
    )
    assert r.status_code == 201, r.text
    session_id = r.json()["id"]
    r = await sec.post(
        "/api/v1/attendance/",
        json={"deputy_id": deputy["id"], "session_id": session_id},
    )
    assert r.status_code == 201, r.text
    # удаление заседания — только администратор
    r = await sec.delete(f"/api/v1/sessions/{session_id}")
    assert r.status_code == 403


async def test_admin_can_delete(client, make_deputy):
    deputy = await make_deputy()
    r = await client.delete(f"/api/v1/deputies/{deputy['id']}")
    assert r.status_code == 204


@pytest.mark.parametrize(
    ("auth", "role"), [(("admin", "admin"), "admin"), (SECRETARY, "secretary")]
)
async def test_who_am_i(make_client, auth, role):
    r = await make_client(auth).get("/api/v1/auth/me")
    assert r.status_code == 200
    assert r.json() == {"username": auth[0], "role": role}


async def test_who_am_i_requires_auth(make_client):
    r = await make_client(None).get("/api/v1/auth/me")
    assert r.status_code == 401
