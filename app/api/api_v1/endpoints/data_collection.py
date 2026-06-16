from fastapi import APIRouter, status, Depends, HTTPException
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.schemas.data_collection import DataCollectionSessionCreate
from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.domain import Device, User
from app.db.influx_client import influx_manager
from influxdb_client import Point
from app.core.config import settings

router = APIRouter()

@router.post("/sessions", status_code=status.HTTP_201_CREATED)
async def save_data_collection_session(
    session: DataCollectionSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Nhận dữ liệu thu thập từ Frontend và lưu vào InfluxDB measurement 'imu_raw'.
    Định dạng dữ liệu được tối ưu để huấn luyện TinyML sau này.
    """
    # Chỉ cho ghi dữ liệu cho thiết bị thuộc tổ chức của user (chống ghi giả mạo).
    device = await db.execute(
        select(Device).where(Device.device_id == session.device_id, Device.org_id == current_user.org_id)
    )
    if not device.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Device not found")

    import numpy as np
    from scipy.signal import find_peaks

    samples = session.samples
    n_samples = len(samples)
    if n_samples < 200:
        raise HTTPException(status_code=400, detail="Not enough samples (minimum 200 required)")

    # 1. Preprocess and calculate SVM
    processed_samples = []
    for s in samples:
        processed_samples.append({
            "ax": max(-8.0, min(8.0, s.ax)) / 8.0,
            "ay": max(-8.0, min(8.0, s.ay)) / 8.0,
            "az": max(-8.0, min(8.0, s.az)) / 8.0,
            "gx": s.gx / 2000.0,
            "gy": s.gy / 2000.0,
            "gz": s.gz / 2000.0,
            "timestamp": s.timestamp,
            "svm": (s.ax**2 + s.ay**2 + s.az**2) ** 0.5
        })

    def get_window(center, size=200):
        start = center - size // 2
        end = center + size // 2
        if start < 0:
            start, end = 0, size
        if end > n_samples:
            end = n_samples
            start = max(0, n_samples - size)
        return processed_samples[start:end]

    windows = []
    svm_array = np.array([s["svm"] for s in processed_samples])

    if session.label == "fall":
        peak_idx = int(np.argmax(svm_array))
        for shift in [-60, -30, 0, 30, 60]:
            win = get_window(peak_idx + shift)
            if len(win) == 200:
                windows.append((win, "fall"))
                
    elif session.label in ["transition_stand_sit", "transition_sit_lie"]:
        peaks, props = find_peaks(svm_array, height=1.0, distance=200)
        if len(peaks) > 0:
            if len(peaks) >= 2:
                selected_peaks = np.sort(peaks[np.argsort(props['peak_heights'])[-2:]])
            else:
                selected_peaks = peaks
            
            for peak in selected_peaks:
                win = get_window(peak)
                if len(win) == 200:
                    windows.append((win, session.label))
                    
                    # Data Augmentation: Scale 0.9 và 1.1
                    win_09 = [{**s, "ax": s["ax"]*0.9, "ay": s["ay"]*0.9, "az": s["az"]*0.9, 
                               "gx": s["gx"]*0.9, "gy": s["gy"]*0.9, "gz": s["gz"]*0.9} for s in win]
                    windows.append((win_09, session.label))
                    
                    win_11 = [{**s, "ax": s["ax"]*1.1, "ay": s["ay"]*1.1, "az": s["az"]*1.1, 
                               "gx": s["gx"]*1.1, "gy": s["gy"]*1.1, "gz": s["gz"]*1.1} for s in win]
                    windows.append((win_11, session.label))
                    
    elif session.label in ["walk", "run"]:
        for start_idx in range(0, n_samples - 200 + 1, 100):
            win = processed_samples[start_idx : start_idx + 200]
            if len(win) == 200:
                windows.append((win, session.label))

    # 2. Write windows to InfluxDB
    session_id = str(uuid4())
    points = []
    
    for w_idx, (win_data, win_label) in enumerate(windows):
        window_id = f"{session_id}_W{w_idx:03d}"
        for s in win_data:
            point = Point("imu_windowed") \
                .tag("device_id", session.device_id) \
                .tag("label", win_label) \
                .tag("session_id", session_id) \
                .tag("window_id", window_id) \
                .field("ax", s["ax"]) \
                .field("ay", s["ay"]) \
                .field("az", s["az"]) \
                .field("gx", s["gx"]) \
                .field("gy", s["gy"]) \
                .field("gz", s["gz"]) \
                .time(s["timestamp"], write_precision='ms')
            points.append(point)

    if points:
        try:
            influx_manager.write_api.write(bucket=settings.INFLUXDB_BUCKET, record=points)
        except Exception as e:
            print(f"Error writing to InfluxDB: {e}")

    return {
        "status": "success",
        "message": f"Processed {len(windows)} windows from session",
        "session_id": session_id,
        "window_count": len(windows),
        "sample_count": len(points),
        "device_id": session.device_id,
        "label": session.label
    }
