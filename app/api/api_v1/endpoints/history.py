from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, union_all, literal_column, desc
from app.db.session import get_db
from app.models.domain import Alert, DeviceEvent
from app.schemas.history import TimelineEntry, AlertHistory
from typing import List

router = APIRouter()

@router.get("/alerts", response_model=List[AlertHistory])
async def get_alert_history(
    device_id: str = None, 
    db: AsyncSession = Depends(get_db)
):
    """Query fall history from PostgreSQL"""
    query = select(Alert)
    if device_id:
        query = query.where(Alert.device_id == device_id)
    
    query = query.order_by(desc(Alert.created_at))
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/{device_id}/timeline", response_model=List[TimelineEntry])
async def get_device_timeline(
    device_id: str, 
    limit: int = 20, 
    db: AsyncSession = Depends(get_db)
):
    """
    Get activity timeline by merging Alerts and DeviceEvents.
    """
    # Create subqueries for UNION ALL
    alerts_query = select(
        Alert.id,
        literal_column("'ALERT'").label("type"),
        Alert.alert_type.label("title"),
        literal_column("NULL").label("description"),
        Alert.created_at
    ).where(Alert.device_id == device_id)

    events_query = select(
        DeviceEvent.id,
        literal_column("'EVENT'").label("type"),
        DeviceEvent.event_type.label("title"),
        DeviceEvent.description,
        DeviceEvent.created_at
    ).where(DeviceEvent.device_id == device_id)

    # Combine using union_all
    union_query = union_all(alerts_query, events_query).alias("timeline")
    
    # Final query to sort and limit
    final_query = select(
        union_query.c.id,
        union_query.c.type,
        union_query.c.title,
        union_query.c.description,
        union_query.c.created_at
    ).order_by(desc(union_query.c.created_at)).limit(limit)

    result = await db.execute(final_query)
    
    # Map raw rows to Pydantic
    return [
        TimelineEntry(
            id=row.id,
            type=row.type,
            title=row.title,
            description=row.description,
            created_at=row.created_at
        )
        for row in result
    ]
