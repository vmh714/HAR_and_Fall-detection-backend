import pytest
from httpx import AsyncClient
from app.services.mqtt_service import mqtt_service
from tests.conftest import TEST_DEVICE_ID

@pytest.mark.asyncio
async def test_get_dashboard_telemetry(async_client: AsyncClient, db_session):
    # First, simulate a status update
    status_data = {
        "device_id": TEST_DEVICE_ID,
        "status": "online",
        "battery_pct": 90,
        "walk_steps": 100,
        "run_steps": 0,
        "timestamp": 1713800000
    }
    await mqtt_service.process_status(db_session, TEST_DEVICE_ID, status_data)
    await db_session.commit()

    # Call API
    response = await async_client.get("/api/v1/dashboard/telemetry")
    assert response.status_code == 200
    data = response.json()
    
    # Assert
    assert isinstance(data, list)
    device_data = next((d for d in data if d["device_id"] == TEST_DEVICE_ID), None)
    assert device_data is not None
    assert device_data["battery_pct"] == 90
    assert device_data["is_active"] is True

@pytest.mark.asyncio
async def test_get_timeline_merges_events_and_alerts(async_client: AsyncClient, db_session):
    # 1. Insert an Event
    event_data = {
        "timestamp": 1713800000,
        "device_id": TEST_DEVICE_ID,
        "event_type": "ACTIVITY_WALKING", 
        "description": "Patient started walking"
    }
    await mqtt_service.process_event(db_session, TEST_DEVICE_ID, event_data)
    
    # 2. Insert an Alert
    alert_data = {
        "device_id": TEST_DEVICE_ID,
        "user_name": "Test Wearer",
        "timestamp": 1713800005,
        "confidence": 0.99,
        "message": "Fall detected!"
    }
    await mqtt_service.process_alert(db_session, TEST_DEVICE_ID, alert_data)
    await db_session.commit()

    # 3. Call API
    response = await async_client.get(f"/api/v1/history/{TEST_DEVICE_ID}/timeline")
    assert response.status_code == 200
    data = response.json()
    
    # Assert both types are present
    assert len(data) >= 2
    types = [item["type"] for item in data]
    assert "EVENT" in types
    assert "ALERT" in types
    
    # Verify mapping
    alert_item = next(item for item in data if item["type"] == "ALERT")
    assert alert_item["title"] == "FALL_DETECTED"
    
    event_item = next(item for item in data if item["type"] == "EVENT")
    assert event_item["title"] == "ACTIVITY_WALKING"
