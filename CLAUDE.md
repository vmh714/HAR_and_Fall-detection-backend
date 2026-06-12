# Backend — HAR & Fall Detection API

## Tech Stack
- **Framework**: FastAPI + Uvicorn (async)
- **DB quan hệ**: PostgreSQL — qua SQLAlchemy 2.x async + asyncpg
- **DB chuỗi thời gian**: InfluxDB — qua `influxdb-client`
- **Migration**: Alembic (`alembic/versions/`)
- **Auth**: JWT — python-jose + passlib/bcrypt
- **MQTT**: aiomqtt (async) — nhận telemetry từ firmware ESP32
- **Validation**: Pydantic v2
- **Test**: pytest (`tests/`)

## Cấu trúc thư mục

```
app/
├── main.py                   # Entry point: khởi tạo FastAPI app, mount router, lifespan (MQTT)
├── patch_loop.py             # Patch asyncio event loop cho Windows dev
├── api/
│   ├── deps.py               # Dependency injection: get_db, get_current_user, get_influx
│   └── api_v1/
│       ├── api.py            # Router tổng hợp tất cả endpoints
│       └── endpoints/
│           ├── auth.py       # POST /login, POST /refresh
│           ├── devices.py    # CRUD thiết bị ESP32, assign/unassign wearer
│           ├── wearers.py    # CRUD hồ sơ bệnh nhân (wearer)
│           ├── dashboard.py  # GET trạng thái realtime + alerts
│           ├── data_collection.py  # POST nhận telemetry từ firmware (HTTP fallback)
│           └── history.py    # GET lịch sử vận động từ InfluxDB
├── core/
│   ├── config.py             # Settings từ env (DATABASE_URL, INFLUX_*, MQTT_*, SECRET_KEY)
│   └── security.py           # Tạo/verify JWT, hash password
├── db/
│   ├── session.py            # Async SQLAlchemy engine + SessionLocal
│   └── influx_client.py      # InfluxDB write/query client
├── models/
│   ├── base.py               # DeclarativeBase
│   └── domain.py             # SQLAlchemy models: User, Device, Wearer, Alert, Organization
├── schemas/
│   ├── domain.py             # Pydantic schemas cho Device, Wearer, Alert, Organization
│   ├── user.py               # Pydantic schemas cho User, Token
│   ├── mqtt.py               # Schema parse gói tin MQTT từ firmware
│   ├── data_collection.py    # Schema cho telemetry HTTP ingestion
│   └── history.py            # Schema cho response lịch sử InfluxDB
└── services/
    └── mqtt_service.py       # Subscribe MQTT broker, parse payload, ghi Influx + trigger alert
```

## Luồng dữ liệu chính

```
ESP32 firmware
  │── MQTT publish ──► mqtt_service.py ──► InfluxDB (telemetry)
  │                                    └── PostgreSQL (alert khi phát hiện ngã)
  └── HTTP POST ──────► data_collection.py (fallback)

Frontend Dashboard
  └── REST API ──► endpoints/* ──► PostgreSQL / InfluxDB
```

## API Contract
Xem `openapi.json` ở thư mục **frontend** (`../frontend/Fall-Detection-dashboard/openapi.json`) — đây là source of truth cho tất cả request/response schema.

## Quy ước
- Tất cả DB operation dùng **async** (`async with SessionLocal() as db`)
- Dependency injection qua `app/api/deps.py` — không gọi session trực tiếp trong endpoint
- Multi-tenancy: mọi query lọc theo `organization_id` lấy từ JWT
- Alert chỉ được tạo bởi `mqtt_service`, không qua HTTP endpoint
