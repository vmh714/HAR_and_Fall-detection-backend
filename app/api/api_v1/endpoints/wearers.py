from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from uuid import UUID

from app.db.session import get_db
from app.models.domain import Wearer
from app.schemas.domain import WearerCreate, WearerUpdate, WearerResponse

router = APIRouter()

@router.get("/", response_model=List[WearerResponse])
async def read_wearers(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    """Lấy danh sách người bệnh."""
    result = await db.execute(select(Wearer).offset(skip).limit(limit))
    wearers = result.scalars().all()
    return wearers

@router.post("/", response_model=WearerResponse, status_code=status.HTTP_201_CREATED)
async def create_wearer(wearer_in: WearerCreate, db: AsyncSession = Depends(get_db)):
    """Thêm mới người bệnh."""
    # Note: In a real app, verify org_id exists and user has permission
    db_wearer = Wearer(**wearer_in.model_dump())
    db.add(db_wearer)
    await db.commit()
    await db.refresh(db_wearer)
    return db_wearer

@router.get("/{wearer_id}", response_model=WearerResponse)
async def read_wearer(wearer_id: UUID, db: AsyncSession = Depends(get_db)):
    """Lấy thông tin chi tiết một người bệnh."""
    result = await db.execute(select(Wearer).where(Wearer.id == wearer_id))
    wearer = result.scalar_one_or_none()
    if not wearer:
        raise HTTPException(status_code=404, detail="Wearer not found")
    return wearer

@router.put("/{wearer_id}", response_model=WearerResponse)
async def update_wearer(wearer_id: UUID, wearer_in: WearerUpdate, db: AsyncSession = Depends(get_db)):
    """Cập nhật thông tin người bệnh."""
    result = await db.execute(select(Wearer).where(Wearer.id == wearer_id))
    wearer = result.scalar_one_or_none()
    if not wearer:
        raise HTTPException(status_code=404, detail="Wearer not found")
    
    update_data = wearer_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(wearer, field, value)
        
    await db.commit()
    await db.refresh(wearer)
    return wearer

@router.delete("/{wearer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_wearer(wearer_id: UUID, db: AsyncSession = Depends(get_db)):
    """Xóa hồ sơ người bệnh."""
    result = await db.execute(select(Wearer).where(Wearer.id == wearer_id))
    wearer = result.scalar_one_or_none()
    if not wearer:
        raise HTTPException(status_code=404, detail="Wearer not found")
        
    await db.delete(wearer)
    await db.commit()
