"""Agenda router — пункты повестки заседания (ЛР3, новая функция, миграция 0004).

Бизнес-правила:
  - номер пункта уникален в пределах заседания;
  - решение (принято/отклонено) можно зафиксировать только на проведённом заседании.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AgendaItem, Session
from app.schemas import AgendaItemCreate, AgendaItemOut, AgendaItemUpdate
from app.services import decision_allowed

router = APIRouter(tags=["agenda"])


@router.get("/sessions/{session_id}/agenda", response_model=list[AgendaItemOut])
async def list_agenda(session_id: int, db: AsyncSession = Depends(get_db)):
    if not await db.get(Session, session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    result = await db.execute(
        select(AgendaItem).where(AgendaItem.session_id == session_id).order_by(AgendaItem.position)
    )
    return result.scalars().all()


@router.post(
    "/sessions/{session_id}/agenda",
    response_model=AgendaItemOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_agenda_item(
    session_id: int, data: AgendaItemCreate, db: AsyncSession = Depends(get_db)
):
    if not await db.get(Session, session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    stmt = select(AgendaItem).where(
        AgendaItem.session_id == session_id, AgendaItem.position == data.position
    )
    if (await db.execute(stmt)).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Agenda position already taken")
    item = AgendaItem(session_id=session_id, **data.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.patch("/agenda/{item_id}", response_model=AgendaItemOut)
async def update_agenda_item(
    item_id: int, data: AgendaItemUpdate, db: AsyncSession = Depends(get_db)
):
    item = await db.get(AgendaItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Agenda item not found")
    update_data = data.model_dump(exclude_unset=True)
    if "decision" in update_data:
        session = await db.get(Session, item.session_id)
        if not decision_allowed(session.status, update_data["decision"]):
            raise HTTPException(
                status_code=422,
                detail="Business rule violation: decision requires a held session",
            )
    for field, value in update_data.items():
        setattr(item, field, value)
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/agenda/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agenda_item(item_id: int, db: AsyncSession = Depends(get_db)):
    item = await db.get(AgendaItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Agenda item not found")
    await db.delete(item)
    await db.commit()
