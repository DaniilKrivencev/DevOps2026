"""Commissions router — CRUD + membership management.

Business rule enforced here:
  - The chairperson of a commission must be a member of that commission.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Commission, CommissionMember, Deputy
from app.schemas import (
    CommissionCreate,
    CommissionMemberCreate,
    CommissionMemberOut,
    CommissionOut,
    CommissionUpdate,
)

router = APIRouter(prefix="/commissions", tags=["commissions"])


# ─── Commission CRUD ──────────────────────────────────────────────────────────


@router.get("/", response_model=List[CommissionOut])
async def list_commissions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Commission).order_by(Commission.id))
    return result.scalars().all()


@router.post("/", response_model=CommissionOut, status_code=status.HTTP_201_CREATED)
async def create_commission(data: CommissionCreate, db: AsyncSession = Depends(get_db)):
    if data.chair_id is not None:
        chair = await db.get(Deputy, data.chair_id)
        if not chair:
            raise HTTPException(status_code=404, detail="Chair deputy not found")
    commission = Commission(**data.model_dump())
    db.add(commission)
    await db.commit()
    await db.refresh(commission)
    return commission


@router.get("/{commission_id}", response_model=CommissionOut)
async def get_commission(commission_id: int, db: AsyncSession = Depends(get_db)):
    commission = await db.get(Commission, commission_id)
    if not commission:
        raise HTTPException(status_code=404, detail="Commission not found")
    return commission


@router.patch("/{commission_id}", response_model=CommissionOut)
async def update_commission(
    commission_id: int, data: CommissionUpdate, db: AsyncSession = Depends(get_db)
):
    commission = await db.get(Commission, commission_id)
    if not commission:
        raise HTTPException(status_code=404, detail="Commission not found")

    update_data = data.model_dump(exclude_unset=True)

    # Business rule: new chair must be a member
    if "chair_id" in update_data and update_data["chair_id"] is not None:
        new_chair_id = update_data["chair_id"]
        chair = await db.get(Deputy, new_chair_id)
        if not chair:
            raise HTTPException(status_code=404, detail="Chair deputy not found")
        # Check membership
        stmt = select(CommissionMember).where(
            CommissionMember.commission_id == commission_id,
            CommissionMember.deputy_id == new_chair_id,
        )
        member = (await db.execute(stmt)).scalar_one_or_none()
        if not member:
            raise HTTPException(
                status_code=422,
                detail="Business rule violation: chair must be a member of the commission",
            )

    for field, value in update_data.items():
        setattr(commission, field, value)
    await db.commit()
    await db.refresh(commission)
    return commission


@router.delete("/{commission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_commission(commission_id: int, db: AsyncSession = Depends(get_db)):
    commission = await db.get(Commission, commission_id)
    if not commission:
        raise HTTPException(status_code=404, detail="Commission not found")
    await db.delete(commission)
    await db.commit()


# ─── Membership ───────────────────────────────────────────────────────────────


@router.get("/{commission_id}/members", response_model=List[CommissionMemberOut])
async def list_members(commission_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CommissionMember).where(
            CommissionMember.commission_id == commission_id
        )
    )
    return result.scalars().all()


@router.post(
    "/{commission_id}/members",
    response_model=CommissionMemberOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    commission_id: int,
    data: CommissionMemberCreate,
    db: AsyncSession = Depends(get_db),
):
    commission = await db.get(Commission, commission_id)
    if not commission:
        raise HTTPException(status_code=404, detail="Commission not found")
    deputy = await db.get(Deputy, data.deputy_id)
    if not deputy:
        raise HTTPException(status_code=404, detail="Deputy not found")

    # Check duplicate
    stmt = select(CommissionMember).where(
        CommissionMember.commission_id == commission_id,
        CommissionMember.deputy_id == data.deputy_id,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Deputy is already a member")

    member = CommissionMember(
        commission_id=commission_id,
        deputy_id=data.deputy_id,
        joined_on=data.joined_on,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return member


@router.delete(
    "/{commission_id}/members/{deputy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member(
    commission_id: int, deputy_id: int, db: AsyncSession = Depends(get_db)
):
    stmt = select(CommissionMember).where(
        CommissionMember.commission_id == commission_id,
        CommissionMember.deputy_id == deputy_id,
    )
    member = (await db.execute(stmt)).scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Membership not found")

    # Cannot remove the chair
    commission = await db.get(Commission, commission_id)
    if commission and commission.chair_id == deputy_id:
        raise HTTPException(
            status_code=422,
            detail="Cannot remove the chairperson from commission members",
        )
    await db.delete(member)
    await db.commit()
