"""Проверка готовности контейнера (Docker HEALTHCHECK, ЛР4).

Код 0 — приложение отвечает и БД доступна, иначе 1. Без curl/wget в образе:
используется только стандартная библиотека Python.

    python -m scripts.healthcheck [URL]
"""

from __future__ import annotations

import json
import sys
import urllib.request

DEFAULT_URL = "http://127.0.0.1:8000/health"


def check(url: str = DEFAULT_URL, timeout: float = 3.0) -> tuple[bool, str]:
    if not url.startswith(("http://", "https://")):
        return False, f"unsupported url: {url}"
    try:
        # Обоснование: схема URL проверена выше (только http/https), адрес — локальный /health.
        resp = urllib.request.urlopen(url, timeout=timeout)  # noqa: S310  # nosec B310
        with resp:
            data = json.loads(resp.read().decode())
    except Exception as exc:  # любая ошибка сети/формата = нездоров
        return False, f"unreachable: {exc}"
    if data.get("database") != "ok":
        return False, f"database: {data.get('database')}"
    return True, f"ok version={data.get('version')} instance={data.get('instance')}"


def main(argv: list[str]) -> int:
    ok, message = check(argv[1] if len(argv) > 1 else DEFAULT_URL)
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
