"""Deputies router — CRUD for Deputy entity."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Deputy
from app.schemas import DeputyCreate, DeputyOut, DeputyUpdate

router = APIRouter(prefix="/deputies", tags=["deputies"])


@router.get("/", response_model=List[DeputyOut])
async def list_deputies(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Deputy).order_by(Deputy.id))
    return result.scalars().all()


@router.post("/", response_model=DeputyOut, status_code=status.HTTP_201_CREATED)
async def create_deputy(data: DeputyCreate, db: AsyncSession = Depends(get_db)):
    deputy = Deputy(**data.model_dump())
    db.add(deputy)
    await db.commit()
    await db.refresh(deputy)
    return deputy


@router.get("/{deputy_id}", response_model=DeputyOut)
async def get_deputy(deputy_id: int, db: AsyncSession = Depends(get_db)):
    deputy = await db.get(Deputy, deputy_id)
    if not deputy:
        raise HTTPException(status_code=404, detail="Deputy not found")
    return deputy


@router.patch("/{deputy_id}", response_model=DeputyOut)
async def update_deputy(
    deputy_id: int, data: DeputyUpdate, db: AsyncSession = Depends(get_db)
):
    deputy = await db.get(Deputy, deputy_id)
    if not deputy:
        raise HTTPException(status_code=404, detail="Deputy not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(deputy, field, value)
    await db.commit()
    await db.refresh(deputy)
    return deputy


@router.delete("/{deputy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deputy(deputy_id: int, db: AsyncSession = Depends(get_db)):
    deputy = await db.get(Deputy, deputy_id)
    if not deputy:
        raise HTTPException(status_code=404, detail="Deputy not found")
    await db.delete(deputy)
    await db.commit()
