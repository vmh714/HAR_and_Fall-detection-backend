# Tài liệu Kiến trúc & Chức năng Backend (FastAPI IoT Server)
Tài liệu này cung cấp thông tin chi tiết về kiến trúc, luồng xử lý dữ liệu và thiết kế cơ sở dữ liệu của Backend, được chuẩn hóa để làm tài liệu đầu vào cho việc viết Báo cáo Đồ án (Chương 3, 4 và 5).

## 1. Công nghệ cốt lõi & Kiến trúc (Phục vụ viết Mục 3.6 và 4.6)
- **Framework nền tảng:** FastAPI (Python), tận dụng ASGI để xử lý bất đồng bộ (Asynchronous) hoàn toàn, giúp hệ thống chịu tải cao khi hàng trăm thiết bị cùng lúc đẩy dữ liệu lên.
- **RESTful APIs:** Cung cấp các endpoints cho Web Frontend, phân chia theo module (`auth`, `wearers`, `devices`, `history`). Validate đầu vào tự động bằng Pydantic.
- **Giao tiếp IoT thời gian thực:** Chạy ngầm một luồng `aiomqtt` (MQTT Bridge) để liên tục lắng nghe dữ liệu đo đạc (telemetry) và cảnh báo từ các thiết bị ESP32.

## 2. Thiết kế Cơ sở dữ liệu kép (Phục vụ viết Mục 3.5 và 4.2)
Hệ thống giải quyết bài toán lưu trữ đa dạng bằng cấu trúc Dual-Database:
- **PostgreSQL (Cơ sở dữ liệu quan hệ):** 
  - Lưu trữ thông tin Metadata có tính liên kết chặt chẽ và yêu cầu tính ACID cao: Người dùng (Y tá/Quản trị viên), Người bệnh (Wearers), Thiết bị (Hardware MAC), và Lịch sử cảnh báo.
  - Hỗ trợ Multi-tenancy (Đa hệ thống): Mỗi bảng đều có `org_id` để cách ly dữ liệu giữa các viện dưỡng lão khác nhau.
- **InfluxDB (Cơ sở dữ liệu chuỗi thời gian):**
  - Tối ưu cho việc ghi dữ liệu liên tục với số lượng cực lớn. 
  - Lưu trữ dữ liệu gia tốc thô (Raw IMU) phục vụ huấn luyện AI (Giai đoạn 1) và dữ liệu đếm bước chân (Telemetry) theo chu kỳ thời gian thực (Giai đoạn 2).

## 3. Giải pháp kỹ thuật nổi bật (Phục vụ viết Chương 5 - Đóng góp)
### 3.1. Thuật toán ước lượng quãng đường di chuyển nội suy từ chiều cao
- **Vấn đề:** Thiết bị đeo chỉ đếm được số bước chân thông qua gia tốc kế, không sử dụng GPS (để tiết kiệm pin), do đó không biết được quãng đường bệnh nhân đã đi.
- **Giải pháp đóng góp:** Xây dựng logic tự động nội suy tại Backend (File `mqtt_service.py`).
  - Khi thiết bị IoT gửi dữ liệu `steps` lên qua MQTT, Backend lập tức truy vấn PostgreSQL để lấy thông tin `chiều cao` của bệnh nhân (Wearer) đang đeo thiết bị đó.
  - Áp dụng công thức sinh trắc học cơ bản: `Độ dài bước đi ≈ Chiều cao × 0.413` và `Độ dài bước chạy ≈ Chiều cao × 0.65`.
  - Backend nhân độ dài bước với số bước chân nhận được, tính ra tổng quãng đường (Distance) rồi ghi bản ghi cuối cùng vào InfluxDB để Frontend lấy ra vẽ biểu đồ.

### 3.2. Kiến trúc bảo mật & Quản lý thiết bị
- Áp dụng cơ chế **Unique Device Assignment**: Logic Backend kiểm tra nghiêm ngặt, đảm bảo một bệnh nhân chỉ được gán với duy nhất một thiết bị đang hoạt động, và một thiết bị không thể bị gán cho 2 người.
- Xác thực bằng JWT (JSON Web Token), kết hợp phân quyền quản trị hệ thống đa tổ chức.
