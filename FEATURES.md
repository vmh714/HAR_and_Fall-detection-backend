# Tài liệu Chức năng Backend (FastAPI IoT Server)

Tài liệu này mô tả chi tiết các chức năng đã được xây dựng tại Backend nhằm đóng vai trò trung tâm xử lý dữ liệu IoT, bảo mật và lưu trữ.

## 1. Cấu trúc Dự án (Project Structure)
- `app/api/`: Định nghĩa các Endpoints (Controllers).
- `app/core/`: Chứa cấu hình (`config.py`) và logic bảo mật, tạo JWT (`security.py`).
- `app/db/`: Quản lý Session của PostgreSQL và InfluxDB Client.
- `app/models/`: Định nghĩa Schema cho Database (SQLAlchemy ORM).
- `app/schemas/`: Định nghĩa Pydantic Models để validate Input/Output API.
- `app/services/`: Logic xử lý nền (Background Tasks, MQTT Bridge).

## 2. Hệ thống Xác thực & Multi-tenancy (`app/api/deps.py`)
- Mọi API (trừ đăng nhập) đều yêu cầu JWT Token.
- Dữ liệu được cách ly theo tổ chức (Multi-tenancy): Model `User` và `Device`, `Wearer` đều có khóa ngoại `org_id`. Các truy vấn API tự động filter dữ liệu dựa trên `org_id` của user đang request để đảm bảo một Viện dưỡng lão không xem được dữ liệu của Viện khác.

## 3. Quản lý RESTful APIs (`app/api/api_v1/endpoints/`)

### 3.1. Auth API (`auth.py`)
- Endpoint: `POST /api/v1/auth/login`.
- Xử lý xác thực tài khoản và cấp phát JWT token có thời hạn.

### 3.2. Wearers API (`wearers.py`)
- Quản lý người đeo thiết bị. 
- Quan trọng: Xử lý lưu trữ chiều cao (`height_cm`) để dùng cho thuật toán tính toán độ dài bước chân.
- Hỗ trợ CRUD đầy đủ.

### 3.3. Devices API (`devices.py`)
- Đăng ký thiết bị vào tổ chức.
- **Tính năng Assign/Unassign**: Gắn kết (hoặc gỡ bỏ) logic giữa Thiết bị (Hardware MAC) và Người đeo (Wearer UUID). Hệ thống sẽ chặn nếu một người dùng được gán nhiều thiết bị cùng lúc.

### 3.4. History & Analytics API (`history.py`)
- Endpoint: `GET /api/v1/history/alerts`: Truy xuất danh sách cảnh báo té ngã (từ Postgres).
- Endpoint: `GET /api/v1/history/steps`: Truy vấn InfluxDB bằng Flux Query, dùng `aggregateWindow` để tổng hợp số lượng bước đi, chạy và quãng đường theo ngày.

### 3.5. Data Collection API (`data_collection.py`)
- Phục vụ cho Giai đoạn 1 (Thu thập mẫu).
- Nhận mảng dữ liệu Raw IMU (Gia tốc & Góc quay) kèm nhãn (Label) và stream trực tiếp vào InfluxDB (measurement: `imu_raw`).

## 4. Dịch vụ MQTT Bridge (`app/services/mqtt_service.py`)
Đây là trái tim của hệ thống IoT thời gian thực, chạy ngầm bằng `asyncio` loop:
- Lắng nghe Topic: `eldercare/+/status`, `eldercare/+/alert/fall`, `eldercare/+/event`.
- **Xử lý Cảnh báo (Alert)**: Khi nhận MQTT payload báo va chạm, tạo ngay bản ghi `FALL_DETECTED` vào Postgres.
- **Tính toán Quãng đường (Distance Calculation)**: Đọc luồng trạng thái (`status`), tự động lookup chiều cao bệnh nhân từ Postgres. Tính toán quãng đường dựa trên công thức nhân hệ số bước chạy/đi, sau đó Write vào InfluxDB.

## 5. Cơ sở Dữ liệu (Databases)
- **PostgreSQL**: Dùng cho cấu trúc quan hệ. Đã setup hệ thống di chuyển cấu trúc (Migrations) bằng **Alembic** (`alembic/versions/`).
- **InfluxDB**: Dùng lưu dữ liệu Time-Series có tần số cao. Quản lý kết nối tại `app/db/influx_client.py`.
