"""
Test harness CÔ LẬP cho backend.

- DB: SQLite in-memory (StaticPool → 1 connection dùng chung cho mọi session),
  override `get_db` → KHÔNG đụng Postgres/Supabase thật.
- InfluxDB: mock toàn bộ (write_point / write_api.write / query_api.query).
- Auth: tạo 2 org + 2 user thật, ký JWT thật → test cả luồng get_current_user và
  việc filter theo org_id.

Hai file test thủ công cũ cần server/DB thật được bỏ qua khi collect.
"""
import uuid
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import Depends, HTTPException, status
from httpx import AsyncClient, ASGITransport
from jose import jwt, JWTError
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.config import settings
from app.models.base import Base, Organization
from app.models.domain import Wearer, Device, User, UserRole
from app.db.session import get_db
from app.api.deps import get_current_user, oauth2_scheme
from app.core.security import create_access_token, get_password_hash

# Bỏ qua các script thủ công (cần server localhost / Postgres thật)
collect_ignore = ["test_db_conn.py", "test_devices_manual.py"]

TEST_DEVICE_ID = "test_dev_999"     # device thuộc org A (giữ tên cũ cho test cũ)
DEVICE_B_ID = "test_dev_orgB"        # device thuộc org B
PASSWORD_A = "secret-a-123"

# ---- Engine SQLite dùng chung cho cả phiên test ---------------------------
test_engine = create_async_engine(
    "sqlite+aiosqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)


async def _override_get_db():
    async with TestSessionLocal() as session:
        yield session


async def _override_get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Bản sao dialect-safe của get_current_user: vẫn decode JWT thật (giữ 401 cho
    token thiếu/hỏng/hết hạn), chỉ ép `sub` (str) → UUID vì cột UUID của SQLite
    không tự coerce string như Postgres. Org-filter ở endpoint vẫn được test thật."""
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        uid = payload.get("sub")
        if uid is None:
            raise exc
    except JWTError:
        raise exc
    result = await db.execute(select(User).where(User.id == uuid.UUID(uid)))
    user = result.scalar_one_or_none()
    if user is None:
        raise exc
    return user


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _setup_schema():
    """Tạo toàn bộ bảng 1 lần + cài override get_db cho cả phiên."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user
    yield
    app.dependency_overrides.clear()
    await test_engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def mock_influx(monkeypatch):
    """Vô hiệu hoá mọi I/O InfluxDB; query trả [] mặc định."""
    from app.db import influx_client
    from unittest.mock import MagicMock

    monkeypatch.setattr(influx_client.influx_manager, "write_point", MagicMock(), raising=True)
    monkeypatch.setattr(influx_client.influx_manager.write_api, "write", MagicMock(), raising=True)
    monkeypatch.setattr(influx_client.influx_manager.query_api, "query", MagicMock(return_value=[]), raising=True)
    return influx_client.influx_manager


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def seed(_setup_schema):
    """Xoá sạch + seed dữ liệu mới cho MỖI test. Trả về namespace id/token."""
    async with TestSessionLocal() as s:
        # Xoá theo thứ tự FK
        for tbl in ["device_events", "alerts", "devices", "wearers", "users", "organizations"]:
            await s.execute(text(f"DELETE FROM {tbl}"))
        await s.commit()

        org_a, org_b = uuid.uuid4(), uuid.uuid4()
        s.add_all([
            Organization(id=org_a, name="Org A"),
            Organization(id=org_b, name="Org B"),
        ])

        user_a, user_b = uuid.uuid4(), uuid.uuid4()
        s.add_all([
            User(id=user_a, username="alice", password_hash=get_password_hash(PASSWORD_A),
                 role=UserRole.MANAGER, org_id=org_a),
            User(id=user_b, username="bob", password_hash=get_password_hash("secret-b-123"),
                 role=UserRole.MANAGER, org_id=org_b),
        ])

        wearer_a = uuid.uuid4()
        s.add(Wearer(id=wearer_a, full_name="Wearer A", height_cm=170, org_id=org_a))

        s.add_all([
            Device(device_id=TEST_DEVICE_ID, current_wearer_id=wearer_a, is_active=True, org_id=org_a, battery_pct=100),
            Device(device_id=DEVICE_B_ID, is_active=True, org_id=org_b, battery_pct=50),
        ])
        await s.commit()

    return SimpleNamespace(
        org_a=org_a, org_b=org_b,
        user_a=user_a, user_b=user_b,
        wearer_a=wearer_a,
        device_a=TEST_DEVICE_ID, device_b=DEVICE_B_ID,
        token_a=create_access_token({"sub": str(user_a)}),
        token_b=create_access_token({"sub": str(user_b)}),
    )


def _client(token: str | None = None) -> AsyncClient:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=headers)


@pytest_asyncio.fixture
async def async_client(seed):
    """Client xác thực như user A (org A) — giữ tên cũ cho test hiện có."""
    async with _client(seed.token_a) as c:
        yield c


@pytest_asyncio.fixture
async def client_a(seed):
    async with _client(seed.token_a) as c:
        yield c


@pytest_asyncio.fixture
async def client_b(seed):
    async with _client(seed.token_b) as c:
        yield c


@pytest_asyncio.fixture
async def client_anon(seed):
    """Client KHÔNG có token."""
    async with _client(None) as c:
        yield c
