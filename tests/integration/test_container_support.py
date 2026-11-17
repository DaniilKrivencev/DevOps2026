"""Поддержка контейнерного запуска (ЛР4): идентификатор экземпляра,
корректное завершение, healthcheck без внешних утилит."""

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app import main
from scripts import healthcheck

pytestmark = pytest.mark.integration


async def test_instance_id_in_header_and_health(client):
    r = await client.get("/health")
    assert r.headers["X-Instance-ID"] == main.INSTANCE_ID
    assert r.json()["instance"] == main.INSTANCE_ID
    r = await client.get("/api/v1/deputies/")
    assert r.headers["X-Instance-ID"] == main.INSTANCE_ID


async def test_graceful_shutdown_logs_and_disposes_engine(caplog, monkeypatch):
    disposed = []

    class FakeEngine:
        async def dispose(self):
            disposed.append(True)

    monkeypatch.setattr(main, "engine", FakeEngine())
    caplog.set_level(logging.INFO, logger="cityduma")
    async with main.lifespan(main.app):
        assert any("started" in r.getMessage() for r in caplog.records)
    assert disposed == [True]
    assert any("Graceful shutdown" in r.getMessage() for r in caplog.records)


def _serve(payload: dict | None, status: int = 200):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 — имя метода задаёт http.server
            body = b"not json" if payload is None else json.dumps(payload).encode()
            self.send_response(status)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}/health"


@pytest.mark.parametrize(
    ("payload", "status", "ok", "fragment"),
    [
        ({"database": "ok", "version": "1", "instance": "a"}, 200, True, "instance=a"),
        ({"database": "error: down"}, 200, False, "database: error"),
        (None, 200, False, "unreachable"),
        ({"database": "ok"}, 500, False, "unreachable"),
    ],
)
def test_healthcheck_script(payload, status, ok, fragment):
    server, url = _serve(payload, status)
    try:
        result, message = healthcheck.check(url, timeout=2)
    finally:
        server.shutdown()
    assert result is ok
    assert fragment in message


def test_healthcheck_rejects_non_http_url():
    assert healthcheck.check("file:///etc/passwd") == (False, "unsupported url: file:///etc/passwd")


def test_healthcheck_main_exit_code(capsys):
    assert healthcheck.main(["x", "http://127.0.0.1:1/health"]) == 1
    assert "unreachable" in capsys.readouterr().out


async def test_version_endpoint(client, monkeypatch):
    monkeypatch.setenv("APP_COMMIT", "0123456789abcdef")
    monkeypatch.setenv("APP_BUILD_TIME", "2026-11-17T20:00:00Z")
    r = await client.get("/version")
    assert r.status_code == 200
    assert r.json() == {
        "version": main.APP_VERSION,
        "commit": "0123456789abcdef",
        "build_time": "2026-11-17T20:00:00Z",
        "environment": "test",
        "instance": main.INSTANCE_ID,
    }


async def test_version_defaults(client, monkeypatch):
    monkeypatch.delenv("APP_COMMIT", raising=False)
    monkeypatch.delenv("APP_BUILD_TIME", raising=False)
    body = (await client.get("/version")).json()
    assert body["commit"] == "unknown"
    assert body["build_time"] == "unknown"
