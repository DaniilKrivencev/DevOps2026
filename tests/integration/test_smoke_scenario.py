"""Проверка основного сценария после развёртывания (ЛР6): scripts/smoke_test.py
против настоящего HTTP-сервера uvicorn."""

import socket
import threading
import time

import pytest
import uvicorn
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.models  # noqa: F401 — регистрирует модели в Base.metadata
from app.database import Base, get_db, make_engine
from app.main import app as fastapi_app
from scripts import smoke_test

pytestmark = pytest.mark.integration


@pytest.fixture
def live_server(tmp_path):
    db_file = tmp_path / "smoke.db"
    sync_engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(sync_engine)
    sync_engine.dispose()
    state = {}

    async def override_get_db():
        # движок создаётся в цикле событий сервера (отдельный поток)
        if "maker" not in state:
            engine = make_engine(f"sqlite+aiosqlite:///{db_file}")
            state["maker"] = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with state["maker"]() as session:
            yield session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(
            fastapi_app, host="127.0.0.1", port=port, log_level="warning", lifespan="off"
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)
    fastapi_app.dependency_overrides.clear()


def test_smoke_scenario_passes(live_server, monkeypatch, capsys):
    monkeypatch.setenv("SMOKE_USER", "admin")
    monkeypatch.setenv("SMOKE_PASSWORD", "admin")
    assert smoke_test.main(["smoke", live_server]) == 0
    out = capsys.readouterr().out
    assert "заседание, явка и кворум" in out
    assert "тестовые данные удалены" in out
    # после проверки следов не остаётся
    client = smoke_test.Client(live_server, "admin", "admin")
    assert client.call("GET", "/api/v1/deputies/") == []
    assert client.call("GET", "/api/v1/commissions/") == []


def test_smoke_fails_with_wrong_credentials(live_server, monkeypatch, capsys):
    monkeypatch.setenv("SMOKE_USER", "admin")
    monkeypatch.setenv("SMOKE_PASSWORD", "wrong")
    assert smoke_test.main(["smoke", live_server]) == 1
    assert "основной сценарий не работает" in capsys.readouterr().out


def test_smoke_requires_credentials(monkeypatch, capsys):
    monkeypatch.delenv("SMOKE_USER", raising=False)
    monkeypatch.delenv("SMOKE_PASSWORD", raising=False)
    assert smoke_test.main(["smoke", "http://127.0.0.1:1"]) == 1
    assert "SMOKE_USER" in capsys.readouterr().out


def test_smoke_unreachable_service(monkeypatch, capsys):
    monkeypatch.setenv("SMOKE_USER", "admin")
    monkeypatch.setenv("SMOKE_PASSWORD", "admin")
    assert smoke_test.main(["smoke", "http://127.0.0.1:1"]) == 1
    assert "недоступен" in capsys.readouterr().out


def test_smoke_rejects_non_http_url():
    with pytest.raises(smoke_test.SmokeError, match="unsupported"):
        smoke_test.Client("file:///etc/passwd", "a", "b")


def test_cleanup_reports_failures(capsys):
    client = smoke_test.Client("http://127.0.0.1:1", "a", "b", timeout=1)
    smoke_test.cleanup(client, {"commissions": [1], "deputies": []})
    assert "не удалось удалить commissions/1" in capsys.readouterr().out
