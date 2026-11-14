"""Интеграционные тесты: заседания, кворум (Ф3.x) и посещаемость (Ф4.x)."""

import pytest

pytestmark = pytest.mark.integration

SESSIONS = "/api/v1/sessions/"
ATTENDANCE = "/api/v1/attendance/"


async def _commission_with_members(client, make_deputy, make_commission, n):
    commission = await make_commission()
    deputies = []
    for _ in range(n):
        deputy = await make_deputy()
        await client.post(
            f"/api/v1/commissions/{commission['id']}/members", json={"deputy_id": deputy["id"]}
        )
        deputies.append(deputy)
    return commission, deputies


async def _mark(client, session_id, deputy_id, status):
    r = await client.post(
        ATTENDANCE, json={"session_id": session_id, "deputy_id": deputy_id, "status": status}
    )
    assert r.status_code == 201, r.text
    return r.json()


async def test_create_session_defaults(client, make_session):
    session = await make_session()
    assert session["status"] == "planned"
    assert session["topic"] == "Тестовая повестка"


async def test_create_session_unknown_commission(client):
    r = await client.post(
        SESSIONS, json={"commission_id": 999, "held_on": "2026-10-01", "topic": "Тема"}
    )
    assert r.status_code == 404


async def test_sessions_sorted_by_date_desc(client, make_commission, make_session):
    commission = await make_commission()
    await make_session(commission_id=commission["id"], held_on="2026-01-01")
    await make_session(commission_id=commission["id"], held_on="2026-03-01")
    dates = [s["held_on"] for s in (await client.get(SESSIONS)).json()]
    assert dates == ["2026-03-01", "2026-01-01"]


async def test_quorum_without_members(client, make_session):
    session = await make_session()
    r = await client.patch(f"{SESSIONS}{session['id']}", json={"status": "held"})
    assert r.status_code == 422
    assert "Quorum not met" in r.json()["detail"]


async def test_quorum_exactly_half_fails(client, make_deputy, make_commission, make_session):
    """Граничный случай: 2 из 4 (ровно 50%) — кворума нет."""
    commission, deputies = await _commission_with_members(client, make_deputy, make_commission, 4)
    session = await make_session(commission_id=commission["id"])
    await _mark(client, session["id"], deputies[0]["id"], "present")
    await _mark(client, session["id"], deputies[1]["id"], "present")
    await _mark(client, session["id"], deputies[2]["id"], "excused")
    r = await client.patch(f"{SESSIONS}{session['id']}", json={"status": "held"})
    assert r.status_code == 422
    assert "need at least 3" in r.json()["detail"]


async def test_quorum_more_than_half_succeeds(client, make_deputy, make_commission, make_session):
    commission, deputies = await _commission_with_members(client, make_deputy, make_commission, 4)
    session = await make_session(commission_id=commission["id"])
    for deputy in deputies[:3]:
        await _mark(client, session["id"], deputy["id"], "present")
    r = await client.patch(f"{SESSIONS}{session['id']}", json={"status": "held"})
    assert r.status_code == 200
    assert r.json()["status"] == "held"


async def test_cancel_session_without_quorum_allowed(client, make_session):
    session = await make_session()
    r = await client.patch(f"{SESSIONS}{session['id']}", json={"status": "cancelled"})
    assert r.status_code == 200


async def test_session_crud_not_found(client):
    assert (await client.get(f"{SESSIONS}999")).status_code == 404
    assert (await client.patch(f"{SESSIONS}999", json={"topic": "X"})).status_code == 404
    assert (await client.delete(f"{SESSIONS}999")).status_code == 404


async def test_delete_session_cascades_attendance(client, make_deputy, make_session):
    deputy = await make_deputy()
    session = await make_session()
    record = await _mark(client, session["id"], deputy["id"], "present")
    assert (await client.delete(f"{SESSIONS}{session['id']}")).status_code == 204
    assert (await client.get(f"{ATTENDANCE}{record['id']}")).status_code == 404


async def test_attendance_duplicate(client, make_deputy, make_session):
    """Ф4.3: одна запись на пару «депутат + заседание»."""
    deputy = await make_deputy()
    session = await make_session()
    await _mark(client, session["id"], deputy["id"], "present")
    r = await client.post(ATTENDANCE, json={"session_id": session["id"], "deputy_id": deputy["id"]})
    assert r.status_code == 409


async def test_attendance_unknown_refs(client, make_deputy, make_session):
    deputy = await make_deputy()
    session = await make_session()
    r = await client.post(ATTENDANCE, json={"session_id": 999, "deputy_id": deputy["id"]})
    assert r.status_code == 404
    r = await client.post(ATTENDANCE, json={"session_id": session["id"], "deputy_id": 999})
    assert r.status_code == 404


async def test_attendance_filters(client, make_deputy, make_session):
    """Ф4.4: фильтрация по заседанию и по депутату."""
    d1, d2 = await make_deputy(), await make_deputy()
    s1, s2 = await make_session(), await make_session()
    await _mark(client, s1["id"], d1["id"], "present")
    await _mark(client, s1["id"], d2["id"], "absent")
    await _mark(client, s2["id"], d1["id"], "excused")
    by_session = (await client.get(ATTENDANCE, params={"session_id": s1["id"]})).json()
    assert {a["deputy_id"] for a in by_session} == {d1["id"], d2["id"]}
    by_deputy = (await client.get(ATTENDANCE, params={"deputy_id": d1["id"]})).json()
    assert {a["session_id"] for a in by_deputy} == {s1["id"], s2["id"]}
    both = (
        await client.get(ATTENDANCE, params={"session_id": s2["id"], "deputy_id": d1["id"]})
    ).json()
    assert [a["status"] for a in both] == ["excused"]
    assert len((await client.get(ATTENDANCE)).json()) == 3


async def test_attendance_update_and_delete(client, make_deputy, make_session):
    deputy = await make_deputy()
    session = await make_session()
    record = await _mark(client, session["id"], deputy["id"], "absent")
    r = await client.patch(
        f"{ATTENDANCE}{record['id']}", json={"status": "excused", "note": "Болен"}
    )
    assert r.status_code == 200
    assert r.json()["status"] == "excused"
    assert r.json()["note"] == "Болен"
    assert (await client.delete(f"{ATTENDANCE}{record['id']}")).status_code == 204
    assert (await client.get(f"{ATTENDANCE}{record['id']}")).status_code == 404
    assert (await client.patch(f"{ATTENDANCE}{record['id']}", json={})).status_code == 404
    assert (await client.delete(f"{ATTENDANCE}{record['id']}")).status_code == 404


async def test_attendance_invalid_status(client, make_deputy, make_session):
    deputy = await make_deputy()
    session = await make_session()
    r = await client.post(
        ATTENDANCE,
        json={"session_id": session["id"], "deputy_id": deputy["id"], "status": "late"},
    )
    assert r.status_code == 422
