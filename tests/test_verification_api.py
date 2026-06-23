"""Test API verification recording feature.

Bao phủ plan `verification_recording_feature.md`:
- POST /sessions: validate device mounted + org isolation
- POST /sessions/{id}/data: lưu file SisFall .txt, đếm sample, tính duration
- GET /sessions: list scoped theo org + filter subject/activity
- GET /sessions/{id}/download: trả file .txt
- GET /export: ZIP toàn bộ file của org

Harness dùng SQLite in-memory + JWT thật (xem conftest.py). File .txt được ghi
vào thư mục tạm (monkeypatch VERIFICATION_DATASET_DIR) để không bẩn workspace.
"""
import io
import uuid
import zipfile
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select

import app.api.api_v1.endpoints.verification as verification_ep
from app.models.domain import Device, VerificationSession

API = "/api/v1/data-collection"

# 6 mẫu IMU giả (ax, ay, az, gx, gy, gz) — đơn vị g / deg/s
SAMPLES = [
    [0.10, 0.20, 0.98, 1.5, -2.5, 0.0],
    [0.11, 0.21, 0.97, 1.6, -2.4, 0.1],
    [0.12, 0.22, 0.96, 1.7, -2.3, 0.2],
]


@pytest_asyncio.fixture(autouse=True)
def _tmp_dataset_dir(monkeypatch, tmp_path):
    """Ghi file .txt vào thư mục tạm thay vì ./verification_dataset của workspace."""
    monkeypatch.setattr(verification_ep, "VERIFICATION_DATASET_DIR", tmp_path / "verification_dataset")
    return tmp_path


@pytest_asyncio.fixture
async def unmounted_device_a(db_session, seed):
    """Thiết bị thuộc org A nhưng CHƯA gán wearer (current_wearer_id IS NULL)."""
    dev = Device(device_id="dev_a_unmounted", is_active=True, org_id=seed.org_a)
    db_session.add(dev)
    await db_session.commit()
    return "dev_a_unmounted"


def _create_body(seed, activity="D01", trial="R01", subject="SV01", device=None):
    return {
        "device_id": device or seed.device_a,
        "subject_code": subject,
        "activity_code": activity,
        "trial_no": trial,
    }


# ===========================================================================
# POST /sessions — tạo session
# ===========================================================================

@pytest.mark.asyncio
async def test_create_session_mounted_device_ok(client_a, seed):
    res = await client_a.post(f"{API}/sessions", json=_create_body(seed))
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["device_id"] == seed.device_a
    assert body["subject_code"] == "SV01"
    assert body["activity_code"] == "D01"
    assert body["trial_no"] == "R01"
    # Chưa submit data → metadata còn rỗng
    assert body["sample_count"] is None
    assert body["file_path"] is None
    assert "id" in body and "created_at" in body


@pytest.mark.asyncio
async def test_create_session_unmounted_device_400(client_a, seed, unmounted_device_a):
    res = await client_a.post(
        f"{API}/sessions", json=_create_body(seed, device=unmounted_device_a)
    )
    assert res.status_code == 400
    assert "gán" in res.json()["detail"]


@pytest.mark.asyncio
async def test_create_session_cross_org_404(client_a, seed):
    """Device thuộc org B → user A không thấy → 404 (không leak sang 400)."""
    res = await client_a.post(f"{API}/sessions", json=_create_body(seed, device=seed.device_b))
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_create_session_unknown_device_404(client_a, seed):
    res = await client_a.post(f"{API}/sessions", json=_create_body(seed, device="does_not_exist"))
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_create_session_requires_auth(client_anon, seed):
    res = await client_anon.post(f"{API}/sessions", json=_create_body(seed))
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_create_session_snapshots_wearer(client_a, db_session, seed):
    res = await client_a.post(f"{API}/sessions", json=_create_body(seed))
    sid = res.json()["id"]
    row = (await db_session.execute(
        select(VerificationSession).where(VerificationSession.id == uuid.UUID(sid))
    )).scalar_one()
    assert row.wearer_id == seed.wearer_a
    assert row.org_id == seed.org_a


# ===========================================================================
# POST /sessions/{id}/data — submit samples
# ===========================================================================

@pytest.mark.asyncio
async def test_submit_data_saves_file(client_a, seed, _tmp_dataset_dir):
    sid = (await client_a.post(f"{API}/sessions", json=_create_body(seed))).json()["id"]

    res = await client_a.post(
        f"{API}/sessions/{sid}/data",
        json={"session_id": sid, "samples": SAMPLES},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["sample_count"] == 3
    assert body["duration_s"] == pytest.approx(0.03)  # 3 / 100Hz
    assert body["file_path"] is not None

    # File tồn tại, đúng tên SisFall, đúng format 6 cột x 6 chữ số thập phân
    fpath = Path(body["file_path"])
    assert fpath.name == "D01_SV01_R01.txt"
    lines = fpath.read_text().strip().splitlines()
    assert len(lines) == 3
    first = lines[0].split(",")
    assert len(first) == 6
    assert first[0] == "0.100000"  # định dạng %.6f


@pytest.mark.asyncio
async def test_submit_empty_samples(client_a, seed):
    sid = (await client_a.post(f"{API}/sessions", json=_create_body(seed))).json()["id"]
    res = await client_a.post(
        f"{API}/sessions/{sid}/data",
        json={"session_id": sid, "samples": []},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["sample_count"] == 0
    assert body["duration_s"] == 0.0
    assert body["file_path"] is None  # không tạo file rỗng


@pytest.mark.asyncio
async def test_submit_data_unknown_session_404(client_a, seed):
    fake = "00000000-0000-0000-0000-000000000000"
    res = await client_a.post(
        f"{API}/sessions/{fake}/data",
        json={"session_id": fake, "samples": SAMPLES},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_submit_data_cross_org_404(client_a, client_b, seed):
    """Session do user A tạo, user B không submit được."""
    sid = (await client_a.post(f"{API}/sessions", json=_create_body(seed))).json()["id"]
    res = await client_b.post(
        f"{API}/sessions/{sid}/data",
        json={"session_id": sid, "samples": SAMPLES},
    )
    assert res.status_code == 404


# ===========================================================================
# GET /sessions — list + filter + org scoping
# ===========================================================================

@pytest.mark.asyncio
async def test_list_sessions_scoped_to_org(client_a, client_b, seed):
    await client_a.post(f"{API}/sessions", json=_create_body(seed, activity="D01"))
    await client_a.post(f"{API}/sessions", json=_create_body(seed, activity="D03", trial="R02"))

    a = (await client_a.get(f"{API}/sessions")).json()
    b = (await client_b.get(f"{API}/sessions")).json()
    assert len(a) == 2
    assert b == []  # org B chưa thu gì


@pytest.mark.asyncio
async def test_list_sessions_filter_subject_activity(client_a, seed):
    await client_a.post(f"{API}/sessions", json=_create_body(seed, subject="SV01", activity="D01"))
    await client_a.post(f"{API}/sessions", json=_create_body(seed, subject="SV02", activity="D01"))
    await client_a.post(f"{API}/sessions", json=_create_body(seed, subject="SV01", activity="F06"))

    by_subject = (await client_a.get(f"{API}/sessions?subject_code=SV01")).json()
    assert len(by_subject) == 2
    assert all(s["subject_code"] == "SV01" for s in by_subject)

    by_activity = (await client_a.get(f"{API}/sessions?activity_code=D01")).json()
    assert len(by_activity) == 2
    assert all(s["activity_code"] == "D01" for s in by_activity)

    both = (await client_a.get(f"{API}/sessions?subject_code=SV01&activity_code=F06")).json()
    assert len(both) == 1


@pytest.mark.asyncio
async def test_list_sessions_requires_auth(client_anon):
    res = await client_anon.get(f"{API}/sessions")
    assert res.status_code == 401


# ===========================================================================
# GET /sessions/{id}/download
# ===========================================================================

@pytest.mark.asyncio
async def test_download_file_ok(client_a, seed):
    sid = (await client_a.post(f"{API}/sessions", json=_create_body(seed))).json()["id"]
    await client_a.post(f"{API}/sessions/{sid}/data", json={"session_id": sid, "samples": SAMPLES})

    res = await client_a.get(f"{API}/sessions/{sid}/download")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/plain")
    assert "D01_SV01_R01.txt" in res.headers.get("content-disposition", "")
    assert len(res.text.strip().splitlines()) == 3


@pytest.mark.asyncio
async def test_download_no_file_404(client_a, seed):
    """Session đã tạo nhưng chưa submit data → chưa có file → 404."""
    sid = (await client_a.post(f"{API}/sessions", json=_create_body(seed))).json()["id"]
    res = await client_a.get(f"{API}/sessions/{sid}/download")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_download_cross_org_404(client_a, client_b, seed):
    sid = (await client_a.post(f"{API}/sessions", json=_create_body(seed))).json()["id"]
    await client_a.post(f"{API}/sessions/{sid}/data", json={"session_id": sid, "samples": SAMPLES})
    res = await client_b.get(f"{API}/sessions/{sid}/download")
    assert res.status_code == 404


# ===========================================================================
# GET /export — ZIP
# ===========================================================================

@pytest.mark.asyncio
async def test_export_zip_contains_org_files(client_a, seed):
    s1 = (await client_a.post(f"{API}/sessions", json=_create_body(seed, activity="D01", trial="R01"))).json()["id"]
    await client_a.post(f"{API}/sessions/{s1}/data", json={"session_id": s1, "samples": SAMPLES})
    s2 = (await client_a.post(f"{API}/sessions", json=_create_body(seed, subject="SV02", activity="F06", trial="R01"))).json()["id"]
    await client_a.post(f"{API}/sessions/{s2}/data", json={"session_id": s2, "samples": SAMPLES})

    res = await client_a.get(f"{API}/export")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"

    zf = zipfile.ZipFile(io.BytesIO(res.content))
    names = set(zf.namelist())
    assert "SV01/D01_SV01_R01.txt" in names
    assert "SV02/F06_SV02_R01.txt" in names


@pytest.mark.asyncio
async def test_export_excludes_other_org(client_a, client_b, seed):
    """File của org A không lọt vào export của org B."""
    sid = (await client_a.post(f"{API}/sessions", json=_create_body(seed))).json()["id"]
    await client_a.post(f"{API}/sessions/{sid}/data", json={"session_id": sid, "samples": SAMPLES})

    res = await client_b.get(f"{API}/export")
    assert res.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(res.content))
    assert zf.namelist() == []
