"""Main FastAPI application entry point."""

import os
import socket
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import User, current_user
from app.database import engine, get_db
from app.logging_setup import install as install_logging
from app.logging_setup import logger, setup_logging
from app.routers import agenda, attendance, commissions, deputies, sessions

APP_VERSION = "0.3.0"

# Идентификатор экземпляра: при нескольких копиях за балансировщиком (ЛР4)
# видно, какой экземпляр обработал запрос. В контейнере hostname = id контейнера.
INSTANCE_ID = os.getenv("INSTANCE_ID") or socket.gethostname()

setup_logging()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("City Duma started: version=%s instance=%s", APP_VERSION, INSTANCE_ID)
    yield
    # корректное завершение по SIGTERM: uvicorn перестаёт принимать запросы,
    # дожидается текущих, затем закрываются соединения с БД
    logger.info("Graceful shutdown: closing database connections (instance=%s)", INSTANCE_ID)
    await engine.dispose()


app = FastAPI(
    title="Городская Дума",
    description="Система учёта депутатов, комиссий, заседаний и посещаемости",
    version=APP_VERSION,
    lifespan=lifespan,
)
install_logging(app)


@app.middleware("http")
async def add_instance_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Instance-ID"] = INSTANCE_ID
    return response


# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(deputies.router, prefix="/api/v1")
app.include_router(commissions.router, prefix="/api/v1")
app.include_router(sessions.router, prefix="/api/v1")
app.include_router(attendance.router, prefix="/api/v1")
app.include_router(agenda.router, prefix="/api/v1")

# ─── Templates ────────────────────────────────────────────────────────────────
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


# ─── Health check ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
async def health(db: AsyncSession = Depends(get_db)):
    """Service health check — проверяет соединение с БД."""
    db_status = "ok"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:  # health должен отвечать даже при недоступной БД
        logger.error("health: database unavailable: %s", exc)
        db_status = f"error: {exc}"
    return {
        "status": "ok",
        "database": db_status,
        "version": APP_VERSION,
        "instance": INSTANCE_ID,
    }


# ─── Авторизация ──────────────────────────────────────────────────────────────
@app.get("/api/v1/auth/me", tags=["auth"])
async def who_am_i(user: User = Depends(current_user)):
    """Проверка учётных данных: возвращает логин и роль текущего пользователя."""
    return {"username": user.username, "role": user.role}


# ─── Web UI routes ────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/ui/deputies", response_class=HTMLResponse)
async def ui_deputies(request: Request):
    return templates.TemplateResponse(request=request, name="deputies.html")


@app.get("/ui/commissions", response_class=HTMLResponse)
async def ui_commissions(request: Request):
    return templates.TemplateResponse(request=request, name="commissions.html")


@app.get("/ui/sessions", response_class=HTMLResponse)
async def ui_sessions(request: Request):
    return templates.TemplateResponse(request=request, name="sessions.html")


@app.get("/ui/attendance", response_class=HTMLResponse)
async def ui_attendance(request: Request):
    return templates.TemplateResponse(request=request, name="attendance.html")
