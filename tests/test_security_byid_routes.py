"""Bảo mật các route THEO-ID vừa được vá (devices/wearers/data-collection):
chống truy cập chéo tổ chức + chống tự chỉ định org_id khi tạo + bắt buộc auth."""
import uuid

import pytest
from app.models.domain import Wearer


# ---------------- devices theo-ID: chéo org → 404 ----------------
@pytest.mark.asyncio
async def test_device_update_cross_org_404(client_a, seed):
    res = await client_a.put(f"/api/v1/devices/{seed.device_b}", json={"is_active": False})
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_device_delete_cross_org_404(client_a, seed):
    res = await client_a.delete(f"/api/v1/devices/{seed.device_b}")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_device_assign_cross_org_device_404(client_a, seed):
    res = await client_a.post(f"/api/v1/devices/{seed.device_b}/assign", json={"wearer_id": str(seed.wearer_a)})
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_device_assign_cross_org_wearer_404(client_a, db_session, seed):
    # device thuộc org A, nhưng gán wearer thuộc org B → phải bị chặn
    wb = Wearer(id=uuid.uuid4(), full_name="Wearer B", height_cm=150, org_id=seed.org_b)
    db_session.add(wb)
    await db_session.commit()
    res = await client_a.post(f"/api/v1/devices/{seed.device_a}/unassign")  # đảm bảo device A trống
    assert res.status_code == 200
    res = await client_a.post(f"/api/v1/devices/{seed.device_a}/assign", json={"wearer_id": str(wb.id)})
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_device_unassign_cross_org_404(client_a, seed):
    res = await client_a.post(f"/api/v1/devices/{seed.device_b}/unassign")
    assert res.status_code == 404


# ---------------- wearers theo-ID: chéo org → 404 ----------------
@pytest.mark.asyncio
async def test_wearer_get_update_delete_cross_org_404(client_a, db_session, seed):
    wb = Wearer(id=uuid.uuid4(), full_name="Wearer B", height_cm=150, org_id=seed.org_b)
    db_session.add(wb)
    await db_session.commit()

    assert (await client_a.get(f"/api/v1/wearers/{wb.id}")).status_code == 404
    assert (await client_a.put(f"/api/v1/wearers/{wb.id}", json={"full_name": "hack"})).status_code == 404
    assert (await client_a.delete(f"/api/v1/wearers/{wb.id}")).status_code == 404


# ---------------- create: KHÔNG cho tự chỉ định org_id ----------------
@pytest.mark.asyncio
async def test_create_device_ignores_client_org_id(client_a, seed):
    res = await client_a.post("/api/v1/devices/", json={
        "device_id": "dev_inject", "firmware_version": "1.0", "is_active": True,
        "org_id": str(seed.org_b),   # cố tình nhét org khác
    })
    assert res.status_code == 201
    assert res.json()["org_id"] == str(seed.org_a)  # bị ép về org của user


@pytest.mark.asyncio
async def test_create_wearer_ignores_client_org_id(client_a, seed):
    res = await client_a.post("/api/v1/wearers/", json={
        "full_name": "Inject", "height_cm": 170, "org_id": str(seed.org_b),
    })
    assert res.status_code == 201
    assert res.json()["org_id"] == str(seed.org_a)


# ---------------- data-collection: auth + verify device org ----------------
@pytest.mark.asyncio
async def test_data_collection_requires_auth(client_anon, seed):
    res = await client_anon.post("/api/v1/data-collection/sessions", json={
        "device_id": seed.device_a, "label": "walking",
        "start_timestamp": 1, "end_timestamp": 2, "sample_count": 0, "samples": [],
    })
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_data_collection_cross_org_device_404(client_a, mock_influx, seed):
    res = await client_a.post("/api/v1/data-collection/sessions", json={
        "device_id": seed.device_b, "label": "walking",   # device org B
        "start_timestamp": 1, "end_timestamp": 2, "sample_count": 1,
        "samples": [{"timestamp": 1, "ax": 0, "ay": 0, "az": 1, "gx": 0, "gy": 0, "gz": 0}],
    })
    assert res.status_code == 404
    mock_influx.write_api.write.assert_not_called()  # không được ghi gì


# ---------------- no-token cho route vừa được bảo vệ ----------------
@pytest.mark.asyncio
async def test_patched_routes_require_token(client_anon, seed):
    assert (await client_anon.put(f"/api/v1/devices/{seed.device_a}", json={"is_active": False})).status_code == 401
    assert (await client_anon.delete(f"/api/v1/devices/{seed.device_a}")).status_code == 401
    assert (await client_anon.get(f"/api/v1/wearers/{seed.wearer_a}")).status_code == 401
