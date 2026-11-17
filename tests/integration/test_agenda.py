"""Интеграционные тесты новой функции ЛР3: повестка заседания (миграция 0004)."""

import pytest

pytestmark = pytest.mark.integration


async def test_add_and_list_agenda_sorted(client, make_session):
    session = await make_session()
    url = f"/api/v1/sessions/{session['id']}/agenda"
    assert (await client.post(url, json={"position": 2, "title": "Разное"})).status_code == 201
    r = await client.post(url, json={"position": 1, "title": "Бюджет"})
    assert r.status_code == 201
    assert r.json()["decision"] == "pending"
    items = (await client.get(url)).json()
    assert [i["title"] for i in items] == ["Бюджет", "Разное"]


async def test_agenda_position_unique(client, make_session):
    session = await make_session()
    url = f"/api/v1/sessions/{session['id']}/agenda"
    await client.post(url, json={"position": 1, "title": "Первый"})
    r = await client.post(url, json={"position": 1, "title": "Дубль"})
    assert r.status_code == 409


async def test_same_position_in_different_sessions(client, make_session):
    s1, s2 = await make_session(), await make_session()
    for s in (s1, s2):
        r = await client.post(
            f"/api/v1/sessions/{s['id']}/agenda", json={"position": 1, "title": "Пункт"}
        )
        assert r.status_code == 201


async def test_agenda_unknown_session(client):
    assert (await client.get("/api/v1/sessions/999/agenda")).status_code == 404
    r = await client.post("/api/v1/sessions/999/agenda", json={"position": 1, "title": "X"})
    assert r.status_code == 404


async def test_decision_requires_held_session(client, make_session):
    session = await make_session()
    item = (
        await client.post(
            f"/api/v1/sessions/{session['id']}/agenda", json={"position": 1, "title": "Пункт"}
        )
    ).json()
    r = await client.patch(f"/api/v1/agenda/{item['id']}", json={"decision": "adopted"})
    assert r.status_code == 422
    r = await client.patch(f"/api/v1/agenda/{item['id']}", json={"title": "Новый"})
    assert r.status_code == 200
    assert r.json()["title"] == "Новый"


async def test_decision_on_held_session(client, make_deputy, make_session):
    deputy = await make_deputy()
    session = await make_session()
    await client.post(
        f"/api/v1/commissions/{session['commission_id']}/members",
        json={"deputy_id": deputy["id"]},
    )
    await client.post(
        "/api/v1/attendance/", json={"session_id": session["id"], "deputy_id": deputy["id"]}
    )
    assert (
        await client.patch(f"/api/v1/sessions/{session['id']}", json={"status": "held"})
    ).status_code == 200
    item = (
        await client.post(
            f"/api/v1/sessions/{session['id']}/agenda", json={"position": 1, "title": "Пункт"}
        )
    ).json()
    r = await client.patch(f"/api/v1/agenda/{item['id']}", json={"decision": "rejected"})
    assert r.status_code == 200
    assert r.json()["decision"] == "rejected"


async def test_delete_agenda_item(client, make_session):
    session = await make_session()
    item = (
        await client.post(
            f"/api/v1/sessions/{session['id']}/agenda", json={"position": 1, "title": "Пункт"}
        )
    ).json()
    assert (await client.delete(f"/api/v1/agenda/{item['id']}")).status_code == 204
    assert (await client.delete(f"/api/v1/agenda/{item['id']}")).status_code == 404
    assert (await client.patch(f"/api/v1/agenda/{item['id']}", json={})).status_code == 404


async def test_delete_session_removes_agenda(client, db_session, make_session):
    from sqlalchemy import func, select

    from app.models import AgendaItem

    session = await make_session()
    await client.post(
        f"/api/v1/sessions/{session['id']}/agenda", json={"position": 1, "title": "Пункт"}
    )
    await client.delete(f"/api/v1/sessions/{session['id']}")
    count = (await db_session.execute(select(func.count()).select_from(AgendaItem))).scalar()
    assert count == 0
