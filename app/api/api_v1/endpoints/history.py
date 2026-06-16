from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, union_all, literal_column, desc
from app.db.session import get_db
from app.models.domain import Alert, DeviceEvent, Device, User
from app.api.deps import get_current_user
from app.schemas.history import TimelineEntry, AlertHistory, StepHistoryResponse
from app.db.influx_client import influx_manager
from app.core.config import settings
from typing import List

router = APIRouter()

@router.get("/alerts", response_model=List[AlertHistory])
async def get_alert_history(
    device_id: str = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Query fall history from PostgreSQL"""
    org_devices = await db.execute(
        select(Device.device_id).where(Device.org_id == current_user.org_id)
    )
    org_device_ids = [r[0] for r in org_devices.all()]

    query = select(Alert).where(Alert.device_id.in_(org_device_ids))
    if device_id:
        query = query.where(Alert.device_id == device_id)

    query = query.order_by(desc(Alert.created_at)).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

@router.patch("/alerts/{alert_id}/resolve", response_model=AlertHistory)
async def resolve_alert(
    alert_id: str,
    device_id: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mark a fall alert as resolved"""
    org_devices = await db.execute(
        select(Device.device_id).where(Device.org_id == current_user.org_id)
    )
    org_device_ids = [r[0] for r in org_devices.all()]

    alert = None

    # 1. Try to find by UUID first if alert_id is a valid UUID
    try:
        uuid_id = UUID(alert_id)
        result = await db.execute(
            select(Alert).where(Alert.id == uuid_id, Alert.device_id.in_(org_device_ids))
        )
        alert = result.scalar_one_or_none()
    except ValueError:
        pass

    # 2. Fallback: Find the latest unresolved alert (optionally filtered by device_id)
    if not alert:
        query = select(Alert).where(
            Alert.is_resolved == False,
            Alert.device_id.in_(org_device_ids)
        )
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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get activity timeline by merging Alerts and DeviceEvents.
    """
    # Verify device belongs to current user's org
    device_check = await db.execute(
        select(Device).where(
            Device.device_id == device_id,
            Device.org_id == current_user.org_id
        )
    )
    if not device_check.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Device not found")

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
async def get_steps_history(
    days: int = 7,
    device_id: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Query daily step counts from InfluxDB, scoped to current user's org"""
    org_devices = await db.execute(
        select(Device.device_id).where(Device.org_id == current_user.org_id)
    )
    org_device_ids = [r[0] for r in org_devices.all()]

    if not org_device_ids:
        return []

    if device_id:
        if device_id not in org_device_ids:
            return []
        org_device_ids = [device_id]

    device_set = "[" + ", ".join([f'"{d}"' for d in org_device_ids]) + "]"

    # Note: Using aggregateWindow with 'max' because device sends cumulative steps per day.
    # We take the max value seen each day as the daily total.
    query = f'''
        from(bucket: "{settings.INFLUXDB_BUCKET}")
          |> range(start: -{days}d)
          |> filter(fn: (r) => r["_measurement"] == "telemetry")
          |> filter(fn: (r) => contains(value: r["device_id"], set: {device_set}))
          |> filter(fn: (r) => r["_field"] == "steps" or r["_field"] == "distance_m")
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
                    steps=int(record.values.get("steps") or 0),
                    distance_km=round((record.values.get("distance_m") or 0) / 1000, 2)
                ))
    except Exception as e:
        print(f"Error querying InfluxDB for steps: {e}")
        return []

    return results

from app.schemas.history import TelemetryHistoryResponse

@router.get("/{device_id}/telemetry", response_model=List[TelemetryHistoryResponse])
async def get_device_telemetry(
    device_id: str,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get raw telemetry logs for a specific device from InfluxDB"""
    device_check = await db.execute(
        select(Device).where(
            Device.device_id == device_id,
            Device.org_id == current_user.org_id
        )
    )
    if not device_check.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Device not found")

    query = f'''
        from(bucket: "{settings.INFLUXDB_BUCKET}")
          |> range(start: -30d)
          |> filter(fn: (r) => r["_measurement"] == "telemetry")
          |> filter(fn: (r) => r["device_id"] == "{device_id}")
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
          |> sort(columns: ["_time"], desc: true)
          |> limit(n: {limit})
    '''

    results = []
    try:
        tables = influx_manager.query_api.query(query, org=settings.INFLUXDB_ORG)
        for table in tables:
            for record in table.records:
                dt = record.get_time()
                raw_rssi = record.values.get("rssi")
                rssi_val = int(raw_rssi) if raw_rssi is not None else None
                results.append(TelemetryHistoryResponse(
                    timestamp=dt,
                    battery_pct=record.values.get("battery_pct"),
                    steps=record.values.get("steps"),
                    distance_m=record.values.get("distance_m"),
                    state=record.values.get("state"),
                    ai_pred=record.values.get("ai_pred"),
                    ai_conf=record.values.get("ai_conf"),
                    rssi=rssi_val
                ))
    except Exception as e:
        print(f"Error querying InfluxDB for telemetry: {e}")
        return []

    return results
