"""Sessions router — CRUD for Session entity.

Business rule:
  A session can only be marked as 'held' if quorum is present
  (more than 50% of commission members have 'present' attendance).
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Attendance, AttendanceStatus, CommissionMember, Session, SessionStatus
from app.schemas import SessionCreate, SessionOut, SessionUpdate

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("/", response_model=List[SessionOut])
async def list_sessions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Session).order_by(Session.held_on.desc()))
    return result.scalars().all()


@router.post("/", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def create_session(data: SessionCreate, db: AsyncSession = Depends(get_db)):
    session = Session(**data.model_dump())
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.get("/{session_id}", response_model=SessionOut)
async def get_session(session_id: int, db: AsyncSession = Depends(get_db)):
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.patch("/{session_id}", response_model=SessionOut)
async def update_session(
    session_id: int, data: SessionUpdate, db: AsyncSession = Depends(get_db)
):
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    update_data = data.model_dump(exclude_unset=True)

    # Business rule: quorum check when marking session as 'held'
    if update_data.get("status") == SessionStatus.held:
        total_result = await db.execute(
            select(func.count()).where(
                CommissionMember.commission_id == session.commission_id
            )
        )
        total_members = total_result.scalar() or 0

        present_result = await db.execute(
            select(func.count()).where(
                Attendance.session_id == session_id,
                Attendance.status == AttendanceStatus.present,
            )
        )
        present_count = present_result.scalar() or 0

        if total_members == 0 or present_count <= total_members / 2:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Quorum not met: {present_count}/{total_members} present, "
                    f"need more than {total_members // 2}"
                ),
            )

    for field, value in update_data.items():
        setattr(session, field, value)
    await db.commit()
    await db.refresh(session)
    return session


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: int, db: AsyncSession = Depends(get_db)):
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.delete(session)
    await db.commit()
