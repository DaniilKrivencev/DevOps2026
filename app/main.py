"""Main FastAPI application entry point."""

import os

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text

from app.database import get_db, engine
from app.routers import deputies, commissions, sessions, attendance

APP_VERSION = "0.1.0"

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

# ─── Templates ────────────────────────────────────────────────────────────────
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


# ─── Health check ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
async def health():
    """Service health check — проверяет соединение с БД."""
    db_status = "ok"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"error: {exc}"
    return {"status": "ok", "database": db_status, "version": APP_VERSION}


# ─── Web UI routes ────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/ui/deputies", response_class=HTMLResponse)
async def ui_deputies(request: Request):
    return templates.TemplateResponse("deputies.html", {"request": request})


@app.get("/ui/commissions", response_class=HTMLResponse)
async def ui_commissions(request: Request):
    return templates.TemplateResponse("commissions.html", {"request": request})


@app.get("/ui/sessions", response_class=HTMLResponse)
async def ui_sessions(request: Request):
    return templates.TemplateResponse("sessions.html", {"request": request})


@app.get("/ui/attendance", response_class=HTMLResponse)
async def ui_attendance(request: Request):
    return templates.TemplateResponse("attendance.html", {"request": request})
