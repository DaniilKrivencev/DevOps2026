"""Интеграционные тесты: депутаты (Ф1.1–Ф1.3) через API и реальную БД."""

import pytest

pytestmark = pytest.mark.integration

API = "/api/v1/deputies/"


async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["database"] == "ok"


async def test_create_and_get_deputy(client):
    payload = {
        "full_name": "Иванов Иван Иванович",
        "party": "Партия",
        "district": "№1",
        "elected_on": "2025-09-14",
        "email": "ivanov@duma.ru",
        "phone": "+7 900 000-00-00",
    }
    r = await client.post(API, json=payload)
    assert r.status_code == 201
    created = r.json()
    for key, value in payload.items():
        assert created[key] == value
    assert created["is_active"] is True

    r = await client.get(f"{API}{created['id']}")
    assert r.status_code == 200
    assert r.json()["email"] == "ivanov@duma.ru"


async def test_create_deputy_empty_name(client):
    r = await client.post(API, json={"full_name": "  "})
    assert r.status_code == 422


async def test_create_deputy_missing_name(client):
    r = await client.post(API, json={"party": "Без имени"})
    assert r.status_code == 422


async def test_duplicate_email_conflict(client, make_deputy):
    await make_deputy(email="same@duma.ru")
    r = await client.post(API, json={"full_name": "Другой", "email": "same@duma.ru"})
    assert r.status_code == 409


async def test_update_to_duplicate_email_conflict(client, make_deputy):
    await make_deputy(email="first@duma.ru")
    second = await make_deputy(email="second@duma.ru")
    r = await client.patch(f"{API}{second['id']}", json={"email": "first@duma.ru"})
    assert r.status_code == 409


async def test_list_deputies_ordered(client, make_deputy):
    first = await make_deputy()
    second = await make_deputy()
    r = await client.get(API)
    assert [d["id"] for d in r.json()] == [first["id"], second["id"]]


async def test_list_is_empty_in_fresh_db(client):
    """Изоляция: каждый тест начинается с пустой БД."""
    r = await client.get(API)
    assert r.json() == []


async def test_get_deputy_not_found(client):
    r = await client.get(f"{API}99999")
    assert r.status_code == 404
    assert r.json()["detail"] == "Deputy not found"


async def test_update_deputy(client, make_deputy):
    deputy = await make_deputy()
    r = await client.patch(f"{API}{deputy['id']}", json={"party": "КПРФ", "is_active": False})
    assert r.status_code == 200
    assert r.json()["party"] == "КПРФ"
    assert r.json()["is_active"] is False
    assert r.json()["full_name"] == deputy["full_name"]


async def test_update_missing_deputy(client):
    r = await client.patch(f"{API}424242", json={"party": "X"})
    assert r.status_code == 404


async def test_delete_deputy(client, make_deputy):
    deputy = await make_deputy()
    assert (await client.delete(f"{API}{deputy['id']}")).status_code == 204
    assert (await client.get(f"{API}{deputy['id']}")).status_code == 404
    assert (await client.delete(f"{API}{deputy['id']}")).status_code == 404


async def test_delete_deputy_with_membership_and_attendance(client, make_deputy, make_session):
    """4.1: членства и посещаемость депутата удаляются каскадно."""
    deputy = await make_deputy()
    session = await make_session()
    await client.post(
        f"/api/v1/commissions/{session['commission_id']}/members",
        json={"deputy_id": deputy["id"]},
    )
    await client.post(
        "/api/v1/attendance/", json={"session_id": session["id"], "deputy_id": deputy["id"]}
    )
    assert (await client.delete(f"{API}{deputy['id']}")).status_code == 204
    members = await client.get(f"/api/v1/commissions/{session['commission_id']}/members")
    assert members.json() == []
    assert (await client.get("/api/v1/attendance/")).json() == []


async def test_filter_deputies_by_active_and_party(client, make_deputy):
    """Ф1.3: список депутатов с фильтрацией по статусу активности и партии."""
    a = await make_deputy(party="Партия А")
    b = await make_deputy(party="Партия Б")
    c = await make_deputy(party="Партия А", is_active=False)
    active = (await client.get(API, params={"is_active": True})).json()
    assert [d["id"] for d in active] == [a["id"], b["id"]]
    party = (await client.get(API, params={"party": "Партия А"})).json()
    assert [d["id"] for d in party] == [a["id"], c["id"]]
    both = (await client.get(API, params={"party": "Партия А", "is_active": False})).json()
    assert [d["id"] for d in both] == [c["id"]]
    assert (await client.get(API, params={"party": "Нет такой"})).json() == []


async def test_filter_deputies_invalid_is_active(client):
    r = await client.get(API, params={"is_active": "может быть"})
    assert r.status_code == 422
