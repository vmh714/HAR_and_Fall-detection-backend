import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.main import app
from app.db.session import AsyncSessionLocal, engine
from app.models.base import Organization
from app.models.domain import Wearer, Device, User, Alert, DeviceEvent
import uuid

TEST_DEVICE_ID = "test_dev_999"

@pytest_asyncio.fixture(scope="function")
async def test_app():
    yield app

@pytest_asyncio.fixture(scope="function")
async def async_client(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        yield client

@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Provides an isolated database session for a test."""
    async with AsyncSessionLocal() as session:
        yield session

@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_test_data(db_session: AsyncSession):
    """Sets up and tears down mock data for each test."""
    # 1. Setup Mock Data
    org_id = uuid.uuid4()
    org = Organization(id=org_id, name="Test Organization")
    db_session.add(org)
    
    wearer_id = uuid.uuid4()
    wearer = Wearer(id=wearer_id, full_name="Test Wearer", height_cm=170, org_id=org_id)
    db_session.add(wearer)
    
    device = Device(device_id=TEST_DEVICE_ID, current_wearer_id=wearer_id, is_active=True)
    db_session.add(device)
    
    await db_session.commit()
    
    yield  # Run the test
    
    # 2. Teardown Mock Data
    # Cleanup in reverse order of dependencies
    await db_session.execute(text(f"DELETE FROM device_events WHERE device_id = '{TEST_DEVICE_ID}'"))
    await db_session.execute(text(f"DELETE FROM alerts WHERE device_id = '{TEST_DEVICE_ID}'"))
    await db_session.execute(text(f"DELETE FROM devices WHERE device_id = '{TEST_DEVICE_ID}'"))
    await db_session.execute(text(f"DELETE FROM wearers WHERE id = '{wearer_id}'"))
    await db_session.execute(text(f"DELETE FROM organizations WHERE id = '{org_id}'"))
    await db_session.commit()
