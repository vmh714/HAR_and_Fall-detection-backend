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

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        env_file_encoding='utf-8',
        extra='ignore'
    )

settings = Settings()
