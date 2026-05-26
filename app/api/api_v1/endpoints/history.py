from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, union_all, literal_column, desc
from app.db.session import get_db
from app.models.domain import Alert, DeviceEvent
from app.schemas.history import TimelineEntry, AlertHistory, StepHistoryResponse
from app.db.influx_client import influx_manager
from app.core.config import settings
from typing import List

router = APIRouter()

@router.get("/alerts", response_model=List[AlertHistory])
async def get_alert_history(
    device_id: str = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """Query fall history from PostgreSQL"""
    query = select(Alert)
    if device_id:
        query = query.where(Alert.device_id == device_id)
    
    query = query.order_by(desc(Alert.created_at)).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

@router.patch("/alerts/{alert_id}/resolve", response_model=AlertHistory)
async def resolve_alert(
    alert_id: str,
    device_id: str = None,
    db: AsyncSession = Depends(get_db)
):
    """Mark a fall alert as resolved"""
    alert = None

    # 1. Try to find by UUID first if alert_id is a valid UUID
    try:
        uuid_id = UUID(alert_id)
        result = await db.execute(select(Alert).where(Alert.id == uuid_id))
        alert = result.scalar_one_or_none()
    except ValueError:
        pass

    # 2. Fallback: Find the latest unresolved alert (optionally filtered by device_id)
    if not alert:
        query = select(Alert).where(Alert.is_resolved == False)
        if device_id:
            query = query.where(Alert.device_id == device_id)
        query = query.order_by(desc(Alert.created_at)).limit(1)

        result = await db.execute(query)
        alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.is_resolved = True
    await db.commit()
    await db.refresh(alert)

    return alert

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

@router.get("/steps", response_model=List[StepHistoryResponse])
async def get_steps_history(days: int = 7):
    """Query daily step counts from InfluxDB"""
    # Note: Using aggregateWindow with 'max' because device sends cumulative steps per day.
    # We take the max value seen each day as the daily total.
    query = f'''
        from(bucket: "{settings.INFLUXDB_BUCKET}")
          |> range(start: -{days}d)
          |> filter(fn: (r) => r["_measurement"] == "telemetry")
          |> filter(fn: (r) => r["_field"] == "walk_steps" or r["_field"] == "run_steps" or r["_field"] == "distance_m")
          |> aggregateWindow(every: 1d, fn: max, createEmpty: false)
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
          |> sort(columns: ["_time"], desc: true)
    '''
    
    results = []
    try:
        tables = influx_manager.query_api.query(query, org=settings.INFLUXDB_ORG)
        for table in tables:
            for record in table.records:
                dt = record.get_time()
                results.append(StepHistoryResponse(
                    date=dt.strftime("%Y-%m-%d"),
                    walk_steps=int(record.values.get("walk_steps") or 0),
                    run_steps=int(record.values.get("run_steps") or 0),
                    distance_km=round((record.values.get("distance_m") or 0) / 1000, 2)
                ))
    except Exception as e:
        print(f"Error querying InfluxDB for steps: {e}")
        return []
        
    return results
