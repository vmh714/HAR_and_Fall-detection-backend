"""Auth + bảo vệ route: login, token thiếu/sai/hết hạn."""
from datetime import timedelta

import pytest
from app.core.security import create_access_token
from tests.conftest import PASSWORD_A

LOGIN = "/api/v1/auth/login"
PROTECTED = "/api/v1/dashboard/telemetry"


@pytest.mark.asyncio
async def test_login_success(client_anon):
    res = await client_anon.post(LOGIN, data={"username": "alice", "password": PASSWORD_A})
    assert res.status_code == 200
    body = res.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


@pytest.mark.asyncio
async def test_login_wrong_password(client_anon):
    res = await client_anon.post(LOGIN, data={"username": "alice", "password": "sai-mat-khau"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_user(client_anon):
    res = await client_anon.post(LOGIN, data={"username": "khong-ton-tai", "password": "x"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_protected_without_token(client_anon):
    res = await client_anon.get(PROTECTED)
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_protected_bad_token(seed):
    from tests.conftest import _client
    async with _client("token.rac.khong-hop-le") as c:
        res = await c.get(PROTECTED)
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_protected_expired_token(seed):
    from tests.conftest import _client
    expired = create_access_token({"sub": str(seed.user_a)}, expires_delta=timedelta(seconds=-10))
    async with _client(expired) as c:
        res = await c.get(PROTECTED)
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_protected_valid_token(client_a):
    res = await client_a.get(PROTECTED)
    assert res.status_code == 200
