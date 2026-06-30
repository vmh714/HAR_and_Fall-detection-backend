from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import os

class Settings(BaseSettings):
    # System
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "info"
    SECRET_KEY: str = "your_super_secret_jwt_key_here"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    API_V1_STR: str = "/api/v1"

    # PostgreSQL
    DATABASE_URL: str = Field(..., validation_alias="DATABASE_URL")

    # InfluxDB
    INFLUXDB_URL: str = "http://localhost:8086"
    INFLUXDB_TOKEN: str = "your_influxdb_admin_token"
    INFLUXDB_ORG: str = "your_org_name"
    INFLUXDB_BUCKET: str = "telemetry_bucket"

    # MQTT
    MQTT_USERNAME: str = "your_mqtt_username"
    MQTT_PASSWORD: str = "your_mqtt_password"
    MQTT_PROTOCOL: str = "mqtts"
    MQTT_HOST: str = "localhost"
    MQTT_PORT: int = 8883
    MQTT_WS_PATH: str = "/mqtt"

    # Device Status
    DEVICE_ONLINE_TIMEOUT_SECONDS: int = 60
    ALERT_AUTO_RESOLVE_HOURS: int = 24
    ALERT_AUTO_RESOLVE_INTERVAL_SECONDS: int = 3600

    # Device provisioning
    # Org nhận thiết bị auto-provision. None = dùng org duy nhất trong DB (1 org/deployment).
    ORG_ID: str | None = None
    # Tiền tố sinh device_id ngữ nghĩa khi auto-provision: esp32_eldercare_01, _02, ...
    DEVICE_ID_PREFIX: str = "esp32_eldercare_"
    # Migration: thiết bị cũ (đăng ký trước khi có cột mac) khi reflash + reconnect sẽ "nhận lại"
    # đúng bản ghi cũ NẾU trong org chỉ có đúng 1 device chưa gắn mac → giữ device_id + lịch sử.
    # Đặt False sau khi đã migrate xong để tránh nhận nhầm.
    ADOPT_SINGLE_LEGACY_DEVICE: bool = True

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        env_file_encoding='utf-8',
        extra='ignore'
    )

settings = Settings()
