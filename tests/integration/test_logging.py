"""Журналирование запросов и ошибок (ЛР1, п. 5)."""

import json
import logging

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app import logging_setup

pytestmark = pytest.mark.integration


async def test_request_is_logged_with_request_id(client, caplog):
    caplog.set_level(logging.INFO, logger="cityduma")
    r = await client.get("/api/v1/deputies/", headers={"X-Request-ID": "abc123"})
    assert r.status_code == 200
    assert r.headers["X-Request-ID"] == "abc123"
    lines = [rec.getMessage() for rec in caplog.records if rec.name == "cityduma.access"]
    assert any("rid=abc123 GET /api/v1/deputies/ -> 200" in line for line in lines)


async def test_client_errors_logged_as_warning(client, caplog):
    caplog.set_level(logging.INFO, logger="cityduma")
    r = await client.get("/api/v1/deputies/999999")
    assert r.status_code == 404
    rec = next(rec for rec in caplog.records if rec.name == "cityduma.access")
    assert rec.levelno == logging.WARNING
    assert "-> 404" in rec.getMessage()
    assert len(r.headers["X-Request-ID"]) == 12


async def test_unhandled_error_logged_and_hidden_from_client(caplog):
    app = FastAPI()
    logging_setup.install(app)

    @app.get("/boom")
    async def boom():
        raise RuntimeError("secret internal detail")

    caplog.set_level(logging.INFO, logger="cityduma")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get("/boom")
    assert r.status_code == 500
    body = r.json()
    assert body["detail"] == "Internal server error"
    assert "secret" not in r.text
    err = next(rec for rec in caplog.records if rec.levelno == logging.ERROR)
    assert body["request_id"] in err.getMessage()
    assert err.exc_info is not None


def test_json_formatter():
    rec = logging.LogRecord("cityduma", logging.INFO, __file__, 1, "hello %s", ("мир",), None)
    data = json.loads(logging_setup.JsonFormatter().format(rec))
    assert data["msg"] == "hello мир"
    assert data["level"] == "INFO"
    assert data["logger"] == "cityduma"


def test_json_formatter_with_exception():
    try:
        raise ValueError("x")
    except ValueError:
        import sys

        rec = logging.LogRecord("cityduma", logging.ERROR, __file__, 1, "fail", (), sys.exc_info())
    data = json.loads(logging_setup.JsonFormatter().format(rec))
    assert "ValueError" in data["exc"]


@pytest.mark.parametrize(
    ("level", "fmt", "expected_level", "formatter"),
    [
        ("debug", "json", logging.DEBUG, logging_setup.JsonFormatter),
        ("nonsense", "text", logging.INFO, logging.Formatter),
    ],
)
def test_setup_logging(monkeypatch, level, fmt, expected_level, formatter):
    monkeypatch.setenv("LOG_LEVEL", level)
    monkeypatch.setenv("LOG_FORMAT", fmt)
    logging_setup.setup_logging()
    log = logging.getLogger("cityduma")
    assert log.level == expected_level
    assert len(log.handlers) == 1
    assert type(log.handlers[0].formatter) is formatter
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("LOG_FORMAT", "text")
    logging_setup.setup_logging()
