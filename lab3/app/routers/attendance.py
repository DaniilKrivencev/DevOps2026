"""Attendance router — CRUD for Attendance entity."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Attendance, Deputy, Session
from app.schemas import AttendanceCreate, AttendanceOut, AttendanceUpdate

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.get("/", response_model=List[AttendanceOut])
async def list_attendance(
    session_id: int | None = None,
    deputy_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Attendance)
    if session_id:
        stmt = stmt.where(Attendance.session_id == session_id)
    if deputy_id:
        stmt = stmt.where(Attendance.deputy_id == deputy_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/", response_model=AttendanceOut, status_code=status.HTTP_201_CREATED)
async def create_attendance(
    data: AttendanceCreate, db: AsyncSession = Depends(get_db)
):
    session = await db.get(Session, data.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    deputy = await db.get(Deputy, data.deputy_id)
    if not deputy:
        raise HTTPException(status_code=404, detail="Deputy not found")

    # Check for duplicate
    stmt = select(Attendance).where(
        Attendance.session_id == data.session_id,
        Attendance.deputy_id == data.deputy_id,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=409, detail="Attendance record already exists for this deputy/session"
        )

    attendance = Attendance(**data.model_dump())
    db.add(attendance)
    await db.commit()
    await db.refresh(attendance)
    return attendance


@router.get("/{attendance_id}", response_model=AttendanceOut)
async def get_attendance(attendance_id: int, db: AsyncSession = Depends(get_db)):
    attendance = await db.get(Attendance, attendance_id)
    if not attendance:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    return attendance


@router.patch("/{attendance_id}", response_model=AttendanceOut)
async def update_attendance(
    attendance_id: int, data: AttendanceUpdate, db: AsyncSession = Depends(get_db)
):
    attendance = await db.get(Attendance, attendance_id)
    if not attendance:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(attendance, field, value)
    await db.commit()
    await db.refresh(attendance)
    return attendance


@router.delete("/{attendance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attendance(attendance_id: int, db: AsyncSession = Depends(get_db)):
    attendance = await db.get(Attendance, attendance_id)
    if not attendance:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    await db.delete(attendance)
    await db.commit()
