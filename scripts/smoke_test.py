"""Проверка основного пользовательского сценария работающего релиза (ЛР6).

Запускается после развёртывания (внутри контейнера приложения, только
стандартная библиотека) против адреса за nginx:

  1. веб-интерфейс открывается;
  2. администратор создаёт двух депутатов и комиссию, включает обоих в состав
     и назначает председателя (правило: председатель — член комиссии);
  3. секретарь-роль не нужна: администратор планирует заседание, отмечает явку
     и переводит заседание в «Проведено» (правило кворума);
  4. данные читаются обратно;
  5. созданные записи удаляются — проверка не оставляет следов.

    SMOKE_USER=admin SMOKE_PASSWORD=... python -m scripts.smoke_test http://nginx:8080
Код 0 — сценарий работает, 1 — нет (развёртывание считается неуспешным).
"""

from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request
import uuid


class SmokeError(Exception):
    pass


class Client:
    def __init__(self, base_url: str, user: str, password: str, timeout: float = 10.0):
        if not base_url.startswith(("http://", "https://")):
            raise SmokeError(f"unsupported url: {base_url}")
        self.base = base_url.rstrip("/")
        token = base64.b64encode(f"{user}:{password}".encode()).decode()
        self.headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json"}
        self.timeout = timeout

    def call(self, method: str, path: str, body: dict | None = None, expect: int = 200):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(  # noqa: S310 — схема проверена в __init__
            self.base + path, data=data, method=method, headers=self.headers
        )
        try:
            # Обоснование: схема URL проверена в __init__ (только http/https).
            resp = urllib.request.urlopen(req, timeout=self.timeout)  # noqa: S310  # nosec B310
            status, raw = resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            status, raw = exc.code, exc.read()
        except OSError as exc:
            raise SmokeError(f"{method} {path}: сервис недоступен: {exc}") from exc
        if status != expect:
            raise SmokeError(f"{method} {path}: ожидался {expect}, получен {status}: {raw[:300]!r}")
        return json.loads(raw) if raw and raw[:1] in (b"{", b"[") else raw.decode(errors="replace")


def run(client: Client) -> list[str]:
    """Выполняет сценарий, возвращает журнал шагов. Ошибка шага — SmokeError."""
    steps: list[str] = []
    mark = uuid.uuid4().hex[:8]
    created: dict[str, list[int]] = {"deputies": [], "commissions": []}
    try:
        page = client.call("GET", "/")
        if "Дума" not in page:
            raise SmokeError("главная страница не содержит название системы")
        steps.append("веб-интерфейс открывается")

        deputies = []
        for name in ("Проверочный Первый Релизович", "Проверочная Вторая Релизовна"):
            d = client.call("POST", "/api/v1/deputies/", {"full_name": name}, expect=201)
            created["deputies"].append(d["id"])
            deputies.append(d)
        commission = client.call(
            "POST", "/api/v1/commissions/", {"name": f"Проверка релиза {mark}"}, expect=201
        )
        created["commissions"].append(commission["id"])
        cid = commission["id"]
        for d in deputies:
            client.call(
                "POST", f"/api/v1/commissions/{cid}/members", {"deputy_id": d["id"]}, expect=201
            )
        client.call("PATCH", f"/api/v1/commissions/{cid}", {"chair_id": deputies[0]["id"]})
        steps.append("депутаты, комиссия, состав и председатель")

        session = client.call(
            "POST",
            "/api/v1/sessions/",
            {"commission_id": cid, "held_on": "2026-11-17", "topic": f"Проверка {mark}"},
            expect=201,
        )
        for d in deputies:
            client.call(
                "POST",
                "/api/v1/attendance/",
                {"session_id": session["id"], "deputy_id": d["id"], "status": "present"},
                expect=201,
            )
        held = client.call("PATCH", f"/api/v1/sessions/{session['id']}", {"status": "held"})
        if held.get("status") != "held":
            raise SmokeError(f"заседание не переведено в held: {held}")
        steps.append("заседание, явка и кворум")

        attendance = client.call("GET", f"/api/v1/attendance/?session_id={session['id']}")
        if len(attendance) != len(deputies):
            raise SmokeError(f"посещаемость: ожидалось {len(deputies)}, получено {len(attendance)}")
        steps.append("данные читаются обратно")
    finally:
        cleanup(client, created)
    steps.append("тестовые данные удалены")
    return steps


def cleanup(client: Client, created: dict[str, list[int]]) -> None:
    """Удаляет созданное; ошибка очистки не скрывает исходную ошибку сценария."""
    for kind in ("commissions", "deputies"):
        for obj_id in created[kind]:
            try:
                client.call("DELETE", f"/api/v1/{kind}/{obj_id}", expect=204)
            except SmokeError as exc:
                print(f"  ! не удалось удалить {kind}/{obj_id}: {exc}")


def main(argv: list[str]) -> int:
    url = argv[1] if len(argv) > 1 else "http://127.0.0.1:8000"
    user = os.getenv("SMOKE_USER", "")
    password = os.getenv("SMOKE_PASSWORD", "")
    if not user or not password:
        print("✗ smoke: задайте SMOKE_USER и SMOKE_PASSWORD")
        return 1
    try:
        for step in run(Client(url, user, password)):
            print(f"  ✔ {step}")
    except SmokeError as exc:
        print(f"✗ smoke: основной сценарий не работает: {exc}")
        return 1
    print("✔ smoke: основной пользовательский сценарий работает")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
