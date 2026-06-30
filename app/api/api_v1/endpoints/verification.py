import io
import logging
import os
import zipfile
from pathlib import Path
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.domain import Device, User, VerificationSession
from app.schemas.verification import (
    VerificationSessionCreate,
    VerificationSessionData,
    VerificationSessionResponse,
    VerificationSessionUpdate,
)

router = APIRouter()
logger = logging.getLogger(__name__)

VERIFICATION_DATASET_DIR = Path("verification_dataset")


def _save_sisfall_txt(subject_code: str, activity_code: str, trial_no: str, samples: List[List[float]]) -> str:
    """Lưu file .txt theo format SisFall: mỗi dòng 6 giá trị float cách nhau dấu phẩy."""
    folder = VERIFICATION_DATASET_DIR / subject_code
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{activity_code}_{subject_code}_{trial_no}.txt"
    path = folder / filename
    if path.exists():
        logger.warning("Overwriting existing verification file: %s", path)
    with open(path, "w") as f:
        for row in samples:
            f.write(",".join(f"{v:.6f}" for v in row) + "\n")
    return str(path)


# ---------------------------------------------------------------------------
# POST /sessions — tạo session mới (validate device mounted)
# ---------------------------------------------------------------------------

@router.post("/sessions", response_model=VerificationSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_verification_session(
    body: VerificationSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Tạo session verification. Device phải đã được gán cho người (current_wearer_id IS NOT NULL)."""
    result = await db.execute(
        select(Device).where(
            Device.device_id == body.device_id,
            Device.org_id == current_user.org_id,
        )
    )
    device = result.scalar_one_or_none()

    if device is None:
        raise HTTPException(status_code=404, detail="Device không tìm thấy hoặc không thuộc org của bạn.")
    if device.current_wearer_id is None:
        raise HTTPException(
            status_code=400,
            detail="Device chưa được gán cho người dùng. Assign device trước khi thu data verification.",
        )

    session = VerificationSession(
        device_id=body.device_id,
        wearer_id=device.current_wearer_id,
        subject_code=body.subject_code,
        activity_code=body.activity_code,
        trial_no=body.trial_no,
        org_id=current_user.org_id,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


# ---------------------------------------------------------------------------
# POST /sessions/{session_id}/data — nhận samples, lưu file .txt
# ---------------------------------------------------------------------------

@router.post("/sessions/{session_id}/data", response_model=VerificationSessionResponse)
async def submit_verification_data(
    session_id: UUID,
    body: VerificationSessionData,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Nhận samples IMU (g/deg/s), lưu file SisFall .txt, cập nhật metadata session."""
    result = await db.execute(
        select(VerificationSession).where(
            VerificationSession.id == session_id,
            VerificationSession.org_id == current_user.org_id,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Verification session không tìm thấy.")

    samples = body.samples
    sample_count = len(samples)
    duration_s = round(sample_count / 100.0, 3)  # 100Hz

    file_path: Optional[str] = None
    if sample_count > 0:
        try:
            file_path = _save_sisfall_txt(
                session.subject_code,
                session.activity_code,
                session.trial_no,
                samples,
            )
        except Exception as exc:
            logger.error("Error saving verification file: %s", exc)
            raise HTTPException(status_code=500, detail=f"Lỗi lưu file: {exc}")

    session.sample_count = sample_count
    session.duration_s = duration_s
    session.file_path = file_path
    await db.commit()
    await db.refresh(session)
    return session


# ---------------------------------------------------------------------------
# GET /sessions — list tất cả sessions của org
# ---------------------------------------------------------------------------

@router.get("/sessions", response_model=List[VerificationSessionResponse])
async def list_verification_sessions(
    subject_code: Optional[str] = Query(None, description="Lọc theo subject, ví dụ SV01"),
    activity_code: Optional[str] = Query(None, description="Lọc theo activity, ví dụ D01"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lấy danh sách tất cả sessions verification của org, mới nhất trước."""
    q = (
        select(VerificationSession)
        .where(VerificationSession.org_id == current_user.org_id)
        .order_by(VerificationSession.created_at.desc())
    )
    if subject_code:
        q = q.where(VerificationSession.subject_code == subject_code)
    if activity_code:
        q = q.where(VerificationSession.activity_code == activity_code)

    result = await db.execute(q)
    return result.scalars().all()


# ---------------------------------------------------------------------------
# GET /sessions/{session_id}/download — tải file .txt một session
# ---------------------------------------------------------------------------

@router.get("/sessions/{session_id}/download")
async def download_verification_file(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Tải xuống file .txt SisFall của một session cụ thể."""
    result = await db.execute(
        select(VerificationSession).where(
            VerificationSession.id == session_id,
            VerificationSession.org_id == current_user.org_id,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session không tìm thấy.")
    if not session.file_path or not os.path.exists(session.file_path):
        raise HTTPException(status_code=404, detail="File chưa được tạo hoặc không tồn tại trên server.")

    filename = f"{session.activity_code}_{session.subject_code}_{session.trial_no}.txt"
    return FileResponse(path=session.file_path, media_type="text/plain", filename=filename)


# ---------------------------------------------------------------------------
# PATCH /sessions/{session_id} — đổi trial_no (rename file kèm theo)
# ---------------------------------------------------------------------------

@router.patch("/sessions/{session_id}", response_model=VerificationSessionResponse)
async def update_verification_session(
    session_id: UUID,
    body: VerificationSessionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Đổi trial_no của session và rename file .txt tương ứng (cùng thư mục subject)."""
    new_trial = body.trial_no.strip().upper()
    if not new_trial:
        raise HTTPException(status_code=400, detail="trial_no không được rỗng.")

    result = await db.execute(
        select(VerificationSession).where(
            VerificationSession.id == session_id,
            VerificationSession.org_id == current_user.org_id,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session không tìm thấy.")

    if new_trial == session.trial_no:
        return session

    # Chống trùng: không cho 2 session cùng subject+activity+trial trong org
    dup = await db.execute(
        select(VerificationSession).where(
            VerificationSession.org_id == current_user.org_id,
            VerificationSession.subject_code == session.subject_code,
            VerificationSession.activity_code == session.activity_code,
            VerificationSession.trial_no == new_trial,
            VerificationSession.id != session.id,
        )
    )
    if dup.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Đã tồn tại trial {new_trial} cho {session.subject_code}/{session.activity_code}.",
        )

    # Rename file vật lý nếu đang có
    if session.file_path and os.path.exists(session.file_path):
        old_path = Path(session.file_path)
        new_name = f"{session.activity_code}_{session.subject_code}_{new_trial}.txt"
        new_path = old_path.with_name(new_name)
        try:
            os.replace(old_path, new_path)
            session.file_path = str(new_path)
        except OSError as exc:
            logger.error("Error renaming verification file: %s", exc)
            raise HTTPException(status_code=500, detail=f"Lỗi đổi tên file: {exc}")

    session.trial_no = new_trial
    await db.commit()
    await db.refresh(session)
    return session


# ---------------------------------------------------------------------------
# DELETE /sessions/{session_id} — xóa session + file trên đĩa
# ---------------------------------------------------------------------------

@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_verification_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Xóa session verification và file .txt tương ứng (nếu có)."""
    result = await db.execute(
        select(VerificationSession).where(
            VerificationSession.id == session_id,
            VerificationSession.org_id == current_user.org_id,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session không tìm thấy.")

    if session.file_path and os.path.exists(session.file_path):
        try:
            os.remove(session.file_path)
        except OSError as exc:
            logger.warning("Could not delete file %s: %s", session.file_path, exc)

    await db.delete(session)
    await db.commit()
    return None


# ---------------------------------------------------------------------------
# GET /export — xuất ZIP tất cả files của org
# ---------------------------------------------------------------------------

@router.get("/export")
async def export_all_verification(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Xuất toàn bộ file .txt của org thành một file ZIP (cấu trúc SV0X/ACT_SV0X_R0X.txt)."""
    result = await db.execute(
        select(VerificationSession).where(
            VerificationSession.org_id == current_user.org_id,
            VerificationSession.file_path.isnot(None),
        )
    )
    sessions = result.scalars().all()

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for s in sessions:
            if s.file_path and os.path.exists(s.file_path):
                arcname = f"{s.subject_code}/{s.activity_code}_{s.subject_code}_{s.trial_no}.txt"
                zf.write(s.file_path, arcname=arcname)

    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=verification_dataset.zip"},
    )
