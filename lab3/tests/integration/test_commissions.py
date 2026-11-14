"""Интеграционные тесты: комиссии и состав (Ф2.1–Ф2.4), ограничения БД (раздел 4.1 ТЗ)."""

import pytest

pytestmark = pytest.mark.integration

API = "/api/v1/commissions/"


async def test_create_commission(client):
    r = await client.post(API, json={"name": "Комиссия по бюджету", "description": "Бюджет"})
    assert r.status_code == 201
    assert r.json()["name"] == "Комиссия по бюджету"
    assert r.json()["chair_id"] is None
    assert r.json()["is_active"] is True


async def test_commission_name_unique(client, make_commission):
    await make_commission(name="Уникальная")
    r = await client.post(API, json={"name": "Уникальная"})
    assert r.status_code == 409


async def test_create_commission_with_chair_rejected(client, make_deputy):
    """Ф2.4: у новой комиссии нет членов, поэтому председатель сразу задан быть не может."""
    deputy = await make_deputy()
    r = await client.post(API, json={"name": "С председателем", "chair_id": deputy["id"]})
    assert r.status_code == 422


async def test_create_commission_with_unknown_chair(client):
    r = await client.post(API, json={"name": "Призрак", "chair_id": 999})
    assert r.status_code == 404


async def test_chair_must_be_member(client, make_deputy, make_commission):
    deputy = await make_deputy()
    commission = await make_commission()
    r = await client.patch(f"{API}{commission['id']}", json={"chair_id": deputy["id"]})
    assert r.status_code == 422
    assert "chair must be a member" in r.json()["detail"]


async def test_chair_as_member(client, make_deputy, make_commission):
    deputy = await make_deputy()
    commission = await make_commission()
    r = await client.post(f"{API}{commission['id']}/members", json={"deputy_id": deputy["id"]})
    assert r.status_code == 201
    r = await client.patch(f"{API}{commission['id']}", json={"chair_id": deputy["id"]})
    assert r.status_code == 200
    assert r.json()["chair_id"] == deputy["id"]


async def test_set_unknown_chair(client, make_commission):
    commission = await make_commission()
    r = await client.patch(f"{API}{commission['id']}", json={"chair_id": 777})
    assert r.status_code == 404


async def test_rename_to_existing_name_conflict(client, make_commission):
    await make_commission(name="Первая")
    second = await make_commission(name="Вторая")
    r = await client.patch(f"{API}{second['id']}", json={"name": "Первая"})
    assert r.status_code == 409


async def test_deactivate_commission(client, make_commission):
    commission = await make_commission()
    r = await client.patch(f"{API}{commission['id']}", json={"is_active": False})
    assert r.status_code == 200
    assert r.json()["is_active"] is False


async def test_member_duplicate(client, make_deputy, make_commission):
    deputy = await make_deputy()
    commission = await make_commission()
    url = f"{API}{commission['id']}/members"
    assert (await client.post(url, json={"deputy_id": deputy["id"]})).status_code == 201
    assert (await client.post(url, json={"deputy_id": deputy["id"]})).status_code == 409


async def test_member_unknown_entities(client, make_deputy, make_commission):
    deputy = await make_deputy()
    commission = await make_commission()
    r = await client.post(f"{API}999/members", json={"deputy_id": deputy["id"]})
    assert r.status_code == 404
    r = await client.post(f"{API}{commission['id']}/members", json={"deputy_id": 999})
    assert r.status_code == 404


async def test_list_and_remove_member(client, make_deputy, make_commission):
    deputy = await make_deputy()
    commission = await make_commission()
    url = f"{API}{commission['id']}/members"
    await client.post(url, json={"deputy_id": deputy["id"], "joined_on": "2026-01-10"})
    members = (await client.get(url)).json()
    assert [m["deputy_id"] for m in members] == [deputy["id"]]
    assert members[0]["joined_on"] == "2026-01-10"
    assert (await client.delete(f"{url}/{deputy['id']}")).status_code == 204
    assert (await client.get(url)).json() == []
    assert (await client.delete(f"{url}/{deputy['id']}")).status_code == 404


async def test_cannot_remove_chair_from_members(client, make_deputy, make_commission):
    deputy = await make_deputy()
    commission = await make_commission()
    url = f"{API}{commission['id']}/members"
    await client.post(url, json={"deputy_id": deputy["id"]})
    await client.patch(f"{API}{commission['id']}", json={"chair_id": deputy["id"]})
    r = await client.delete(f"{url}/{deputy['id']}")
    assert r.status_code == 422


async def test_delete_commission_cascades(client, make_deputy, make_commission, make_session):
    """4.1: при удалении комиссии удаляются её членства и заседания."""
    deputy = await make_deputy()
    commission = await make_commission()
    await client.post(f"{API}{commission['id']}/members", json={"deputy_id": deputy["id"]})
    session = await make_session(commission_id=commission["id"])
    assert (await client.delete(f"{API}{commission['id']}")).status_code == 204
    assert (await client.get(f"{API}{commission['id']}")).status_code == 404
    assert (await client.get(f"/api/v1/sessions/{session['id']}")).status_code == 404
    assert (await client.delete(f"{API}{commission['id']}")).status_code == 404


async def test_delete_chair_deputy_sets_null(client, make_deputy, make_commission):
    """4.1: при удалении депутата-председателя chair_id становится NULL."""
    deputy = await make_deputy()
    commission = await make_commission()
    await client.post(f"{API}{commission['id']}/members", json={"deputy_id": deputy["id"]})
    await client.patch(f"{API}{commission['id']}", json={"chair_id": deputy["id"]})
    assert (await client.delete(f"/api/v1/deputies/{deputy['id']}")).status_code == 204
    r = await client.get(f"{API}{commission['id']}")
    assert r.json()["chair_id"] is None


async def test_get_update_missing_commission(client):
    assert (await client.get(f"{API}999")).status_code == 404
    assert (await client.patch(f"{API}999", json={"name": "X"})).status_code == 404
