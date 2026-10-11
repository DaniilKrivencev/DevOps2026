"""Интеграционные тесты веб-интерфейса (Ф5.2), документации (Ф5.3) и /health (Ф5.1)."""

import pytest

from app.database import get_db
from app.main import app as fastapi_app

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "path", ["/", "/ui/deputies", "/ui/commissions", "/ui/sessions", "/ui/attendance"]
)
async def test_ui_pages_render(client, path):
    r = await client.get(path)
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


async def test_openapi_docs_available(client):
    r = await client.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json()["paths"]
    assert "/api/v1/deputies/" in paths
    assert "/api/v1/sessions/{session_id}" in paths
    assert (await client.get("/docs")).status_code == 200


async def test_health_reports_database_error(client):
    class BrokenSession:
        async def execute(self, *_args, **_kwargs):
            raise ConnectionError("db is down")

    async def broken_db():
        yield BrokenSession()

    fastapi_app.dependency_overrides[get_db] = broken_db
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["database"].startswith("error: db is down")
