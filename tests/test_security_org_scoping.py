"""Bảo mật đa tổ chức: user chỉ thấy/đụng được dữ liệu thuộc org của mình.
Đây là phần security fix chính của BE (filter org_id ở dashboard/devices/wearers/history)."""
import pytest
from sqlalchemy import select
from app.models.domain import Alert


# ---------------- dashboard ----------------
@pytest.mark.asyncio
async def test_dashboard_only_own_org(client_a, client_b, seed):
    a = (await client_a.get("/api/v1/dashboard/telemetry")).json()
    b = (await client_b.get("/api/v1/dashboard/telemetry")).json()
    ids_a = {d["device_id"] for d in a}
    ids_b = {d["device_id"] for d in b}
    assert ids_a == {seed.device_a}
    assert ids_b == {seed.device_b}


# ---------------- devices ----------------
@pytest.mark.asyncio
async def test_devices_list_scoped(client_a, seed):
    devs = (await client_a.get("/api/v1/devices/")).json()
    ids = {d["device_id"] for d in devs}
    assert seed.device_a in ids
    assert seed.device_b not in ids


# ---------------- wearers ----------------
@pytest.mark.asyncio
async def test_wearers_list_scoped(client_a, client_b, seed):
    a = (await client_a.get("/api/v1/wearers/")).json()
    b = (await client_b.get("/api/v1/wearers/")).json()
    assert {w["id"] for w in a} == {str(seed.wearer_a)}
    assert b == []  # org B chưa có wearer nào


# ---------------- history / alerts ----------------
@pytest.mark.asyncio
async def test_alerts_list_scoped(client_a, db_session, seed):
    db_session.add_all([
        Alert(device_id=seed.device_a, alert_type="FALL_DETECTED", confidence=0.9, is_resolved=False),
        Alert(device_id=seed.device_b, alert_type="FALL_DETECTED", confidence=0.8, is_resolved=False),
    ])
    await db_session.commit()

    alerts = (await client_a.get("/api/v1/history/alerts")).json()
    assert len(alerts) == 1
    assert all(al["device_id"] == seed.device_a for al in alerts)


# ---------------- history / timeline (cross-org) ----------------
@pytest.mark.asyncio
async def test_timeline_cross_org_404(client_a, seed):
    res = await client_a.get(f"/api/v1/history/{seed.device_b}/timeline")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_timeline_own_device_ok(client_a, seed):
    res = await client_a.get(f"/api/v1/history/{seed.device_a}/timeline")
    assert res.status_code == 200


# ---------------- history / resolve (cross-org) ----------------
@pytest.mark.asyncio
async def test_resolve_cross_org_forbidden(client_a, client_b, db_session, seed):
    alert_b = Alert(device_id=seed.device_b, alert_type="FALL_DETECTED", confidence=0.7, is_resolved=False)
    db_session.add(alert_b)
    await db_session.commit()
    await db_session.refresh(alert_b)

    # User A KHÔNG được resolve alert của org B (không tìm thấy trong org A → 404)
    res_a = await client_a.patch(f"/api/v1/history/alerts/{alert_b.id}/resolve")
    assert res_a.status_code == 404

    # User B resolve được alert của chính org mình
    res_b = await client_b.patch(f"/api/v1/history/alerts/{alert_b.id}/resolve")
    assert res_b.status_code == 200
    assert res_b.json()["is_resolved"] is True


# ---------------- history / steps (Flux query bị giới hạn theo org) ----------------
@pytest.mark.asyncio
async def test_steps_query_scoped_to_org(client_a, mock_influx, seed):
    res = await client_a.get("/api/v1/history/steps")
    assert res.status_code == 200
    assert res.json() == []  # mock query trả []

    # Flux query phải chứa device của org A và KHÔNG chứa device org B
    flux = mock_influx.query_api.query.call_args.args[0]
    assert seed.device_a in flux
    assert seed.device_b not in flux
