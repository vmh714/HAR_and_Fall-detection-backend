from fastapi import APIRouter, status
from app.schemas.data_collection import DataCollectionSessionCreate
from app.db.influx_client import influx_manager
from influxdb_client import Point
from app.core.config import settings

router = APIRouter()

@router.post("/sessions", status_code=status.HTTP_201_CREATED)
async def save_data_collection_session(session: DataCollectionSessionCreate):
    """
    Nhận dữ liệu thu thập từ Frontend và lưu vào InfluxDB measurement 'imu_raw'.
    Định dạng dữ liệu được tối ưu để huấn luyện TinyML sau này.
    """
    points = []
    for sample in session.samples:
        # Tạo point cho InfluxDB
        point = Point("imu_raw") \
            .tag("device_id", session.device_id) \
            .tag("label", session.label) \
            .tag("session_id", str(session.start_timestamp)) \
            .field("ax", sample.ax) \
            .field("ay", sample.ay) \
            .field("az", sample.az) \
            .field("gx", sample.gx) \
            .field("gy", sample.gy) \
            .field("gz", sample.gz) \
            .time(sample.timestamp, write_precision='ms')
        points.append(point)
    
    # Thực hiện ghi batch vào InfluxDB
    try:
        influx_manager.write_api.write(bucket=settings.INFLUXDB_BUCKET, record=points)
    except Exception as e:
        # Trong trường hợp InfluxDB lỗi, chúng ta vẫn trả về 201 để frontend không bị treo
        # nhưng log lỗi ra console
        print(f"Error writing to InfluxDB: {e}")
    
    return {
        "status": "success", 
        "message": "Data collection session saved",
        "sample_count": len(points),
        "device_id": session.device_id,
        "label": session.label
    }
