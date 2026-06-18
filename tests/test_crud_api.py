"""Smoke CRUD cho wearers, devices và data-collection (mọi API còn lại)."""
import pytest


# ==================== WEARERS ====================
@pytest.mark.asyncio
async def test_wearer_crud(client_a, seed):
    # CREATE
    res = await client_a.post("/api/v1/wearers/", json={"full_name": "Nguyễn Văn B", "height_cm": 165})
    assert res.status_code == 201
    w = res.json()
    assert w["full_name"] == "Nguyễn Văn B"
    assert w["org_id"] == str(seed.org_a)  # tự gán org theo user
    wid = w["id"]

    # READ list (gồm wearer mới + wearer seed)
    lst = (await client_a.get("/api/v1/wearers/")).json()
    assert wid in {x["id"] for x in lst}

    # READ one
    assert (await client_a.get(f"/api/v1/wearers/{wid}")).status_code == 200

    # UPDATE
    upd = await client_a.put(f"/api/v1/wearers/{wid}", json={"full_name": "Tên Mới"})
    assert upd.status_code == 200
    assert upd.json()["full_name"] == "Tên Mới"

    # DELETE
    assert (await client_a.delete(f"/api/v1/wearers/{wid}")).status_code == 204
    assert (await client_a.get(f"/api/v1/wearers/{wid}")).status_code == 404


# ==================== DEVICES ====================
@pytest.mark.asyncio
async def test_device_create_and_duplicate(client_a, seed):
    payload = {"device_id": "new_dev_1", "firmware_version": "1.0.0", "is_active": True}
    res = await client_a.post("/api/v1/devices/", json=payload)
    assert res.status_code == 201
    assert res.json()["org_id"] == str(seed.org_a)

    # Trùng device_id → 400
    dup = await client_a.post("/api/v1/devices/", json=payload)
    assert dup.status_code == 400


@pytest.mark.asyncio
async def test_device_update_assign_unassign_delete(client_a, seed):
    await client_a.post("/api/v1/devices/", json={"device_id": "dev_x", "firmware_version": "1.0.0", "is_active": True})

    # UPDATE
    upd = await client_a.put("/api/v1/devices/dev_x", json={"firmware_version": "2.0.0", "is_active": False})
    assert upd.status_code == 200
    assert upd.json()["firmware_version"] == "2.0.0"
    assert upd.json()["is_active"] is False

    # Tạo wearer mới rồi ASSIGN (wearer seed đã gắn device khác — cột unique)
    wid = (await client_a.post("/api/v1/wearers/", json={"full_name": "W2", "height_cm": 160})).json()["id"]
    asg = await client_a.post("/api/v1/devices/dev_x/assign", json={"wearer_id": wid})
    assert asg.status_code == 200
    assert asg.json()["current_wearer_id"] == wid

    # UNASSIGN
    un = await client_a.post("/api/v1/devices/dev_x/unassign")
    assert un.status_code == 200
    assert un.json()["current_wearer_id"] is None

    # DELETE
    assert (await client_a.delete("/api/v1/devices/dev_x")).status_code == 204


@pytest.mark.asyncio
async def test_device_update_not_found(client_a):
    res = await client_a.put("/api/v1/devices/khong-ton-tai", json={"is_active": False})
    assert res.status_code == 404


# ==================== DATA COLLECTION ====================
@pytest.mark.asyncio
async def test_data_collection_session(client_a, mock_influx, seed):
    # Endpoint hiện tại làm WINDOWING: cần >=200 mẫu, label hợp lệ (walk/run/fall/
    # transition_*); với 'walk' nó cắt cửa sổ 200 mẫu trượt 100. Gửi 250 mẫu → 1 window.
    samples = [
        {"timestamp": 1713800000000 + i * 10, "ax": 0.1, "ay": 0.0, "az": 1.0, "gx": 1, "gy": 2, "gz": 3}
        for i in range(250)
    ]
    payload = {
        "device_id": seed.device_a,
        "label": "walk",
        "start_timestamp": samples[0]["timestamp"],
        "end_timestamp": samples[-1]["timestamp"],
        "sample_count": len(samples),
        "samples": samples,
    }
    res = await client_a.post("/api/v1/data-collection/sessions", json=payload)
    assert res.status_code == 201
    body = res.json()
    assert body["window_count"] >= 1               # đã cắt được ít nhất 1 cửa sổ
    assert body["sample_count"] == body["window_count"] * 200  # mỗi window 200 điểm Influx
    assert body["session_id"]
    assert body["device_id"] == seed.device_a
    mock_influx.write_api.write.assert_called_once()  # đã ghi InfluxDB (mock)


@pytest.mark.asyncio
async def test_data_collection_rejects_too_few_samples(client_a, seed):
    # Guard: < 200 mẫu → 400 (không đủ cho 1 cửa sổ).
    payload = {
        "device_id": seed.device_a, "label": "walk",
        "start_timestamp": 0, "end_timestamp": 10, "sample_count": 2,
        "samples": [
            {"timestamp": 0, "ax": 0.1, "ay": 0.0, "az": 1.0, "gx": 1, "gy": 2, "gz": 3},
            {"timestamp": 10, "ax": 0.2, "ay": 0.1, "az": 1.0, "gx": 4, "gy": 5, "gz": 6},
        ],
    }
    res = await client_a.post("/api/v1/data-collection/sessions", json=payload)
    assert res.status_code == 400
