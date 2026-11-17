"""Журналирование приложения (ЛР1, п. 5).

- уровень задаётся LOG_LEVEL (по умолчанию INFO), формат — LOG_FORMAT=text|json;
- каждый HTTP-запрос журналируется: метод, путь, код ответа, длительность, request id;
- необработанные исключения журналируются с трассировкой, клиент получает 500
  и request id, по которому ошибку можно найти в журнале (journalctl / docker logs).
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("cityduma")
access_logger = logging.getLogger("cityduma.access")

TEXT_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


class JsonFormatter(logging.Formatter):
    """Одна строка JSON на событие — удобно для сбора журналов из контейнеров."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    handler = logging.StreamHandler(sys.stdout)
    if os.getenv("LOG_FORMAT", "text").lower() == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(TEXT_FORMAT))
    root = logging.getLogger("cityduma")
    root.handlers[:] = [handler]
    root.setLevel(level if level in logging.getLevelNamesMapping() else "INFO")
    root.propagate = True


def install(app: FastAPI) -> None:
    """Подключает журналирование запросов и обработчик необработанных ошибок."""

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration = (time.perf_counter() - started) * 1000
            logger.exception(
                "unhandled error rid=%s %s %s (%.1f ms)",
                request_id,
                request.method,
                request.url.path,
                duration,
            )
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error", "request_id": request_id},
                headers={"X-Request-ID": request_id},
            )
        duration = (time.perf_counter() - started) * 1000
        level = logging.WARNING if response.status_code >= 400 else logging.INFO
        access_logger.log(
            level,
            "rid=%s %s %s -> %s (%.1f ms)",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration,
        )
        response.headers["X-Request-ID"] = request_id
        return response
