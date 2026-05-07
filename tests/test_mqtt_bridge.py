import pytest
from sqlalchemy import select
from app.services.mqtt_service import mqtt_service
from app.models.domain import Device, Alert, DeviceEvent
from tests.conftest import TEST_DEVICE_ID

@pytest.mark.asyncio
async def test_process_status(db_session):
    data = {
        "device_id": TEST_DEVICE_ID,
        "status": "online",
        "battery_pct": 80,
        "rssi": -65,
        "walk_steps": 100,
        "run_steps": 0,
        "timestamp": 1713800000
    }
    
    await mqtt_service.process_status(db_session, TEST_DEVICE_ID, data)
    await db_session.commit()
    
    # Verify DB update
    result = await db_session.execute(select(Device).where(Device.device_id == TEST_DEVICE_ID))
    device = result.scalar_one()
    
    assert device.battery_pct == 80
    assert device.last_online is not None

@pytest.mark.asyncio
async def test_process_alert(db_session):
    data = {
        "device_id": TEST_DEVICE_ID,
        "user_name": "Test Wearer",
        "timestamp": 1713800000,
        "confidence": 0.95,
        "message": "Fall detected!"
    }
    
    await mqtt_service.process_alert(db_session, TEST_DEVICE_ID, data)
    await db_session.commit()
    
    # Verify DB insertion
    result = await db_session.execute(select(Alert).where(Alert.device_id == TEST_DEVICE_ID))
    alert = result.scalar_one()
    
    assert alert.alert_type == "FALL_DETECTED"
    assert alert.confidence == 0.95
    assert alert.is_resolved is False
    assert alert.wearer_id is not None

@pytest.mark.asyncio
async def test_process_event(db_session):
    data = {
        "timestamp": 1713800000,
        "device_id": TEST_DEVICE_ID,
        "event_type": "ACTIVITY_WALKING", 
        "description": "Patient started walking"
    }
    
    await mqtt_service.process_event(db_session, TEST_DEVICE_ID, data)
    await db_session.commit()
    
    # Verify DB insertion
    result = await db_session.execute(select(DeviceEvent).where(DeviceEvent.device_id == TEST_DEVICE_ID))
    event = result.scalar_one()
    
    assert event.event_type == "ACTIVITY_WALKING"
    assert event.description == "Patient started walking"
    assert event.wearer_id is not None
