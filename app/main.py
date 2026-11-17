"""Main FastAPI application entry point."""

import os

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.routers import agenda, attendance, commissions, deputies, sessions

APP_VERSION = "0.3.0"

app = FastAPI(
    title="Городская Дума",
    description="Система учёта депутатов, комиссий, заседаний и посещаемости",
    version=APP_VERSION,
)

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
        db_status = f"error: {exc}"
    return {"status": "ok", "database": db_status, "version": APP_VERSION}


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
