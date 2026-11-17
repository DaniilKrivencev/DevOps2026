# =============================================================================
# Образ приложения «Городская Дума» (ЛР4).
# Воспроизводимость: базовый образ с точной версией (не latest), зависимости
# с зафиксированными версиями (requirements.txt), контекст ограничен .dockerignore.
# Безопасность: процесс работает от непривилегированного пользователя app (uid 10001),
# секретов в образе нет — все настройки передаются переменными окружения при запуске.
# =============================================================================
ARG PYTHON_IMAGE=python:3.12.8-slim-bookworm

# ─── Сборка зависимостей в отдельном слое ────────────────────────────────────
FROM ${PYTHON_IMAGE} AS builder
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
COPY requirements.txt /tmp/requirements.txt
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-compile -r /tmp/requirements.txt

# ─── Итоговый образ ──────────────────────────────────────────────────────────
FROM ${PYTHON_IMAGE} AS runtime

ARG APP_VERSION=0.0.0-dev
ARG GIT_SHA=unknown
LABEL org.opencontainers.image.title="cityduma" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.source="https://github.com/DaniilKrivencev/DevOps2026"

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    APP_PORT=8000

RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --home-dir /nonexistent \
            --shell /usr/sbin/nologin app

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
# код принадлежит root и доступен приложению только для чтения
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts

USER 10001:10001
EXPOSE 8000

# docker stop шлёт SIGTERM; uvicorn (PID 1, exec-форма CMD) завершает текущие
# запросы за --timeout-graceful-shutdown и закрывает соединения с БД
STOPSIGNAL SIGTERM
HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-m", "scripts.healthcheck"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*", \
     "--timeout-graceful-shutdown", "15", "--no-access-log"]
