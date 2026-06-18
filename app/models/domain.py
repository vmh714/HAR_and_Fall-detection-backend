from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, UUID, ForeignKey, Float, Boolean, Enum as SQLEnum, Integer, DateTime
import uuid
import enum
import datetime
from typing import Optional
from app.models.base import Base

class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole), default=UserRole.MANAGER)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="users")

class Wearer(Base):
    __tablename__ = "wearers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    height_cm: Mapped[float] = mapped_column(Float, nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="wearers")
    device: Mapped[Optional["Device"]] = relationship(back_populates="wearer")

class Device(Base):
    __tablename__ = "devices"

    device_id: Mapped[str] = mapped_column(String(100), primary_key=True)  # MQTT Client ID
    firmware_version: Mapped[Optional[str]] = mapped_column(String(50))
    current_wearer_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("wearers.id"), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    telemetry_interval: Mapped[int] = mapped_column(Integer, default=5)
    fall_threshold: Mapped[float] = mapped_column(Float, default=0.6)  # ngưỡng xác suất chốt ngã (0.15–0.95)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    battery_pct: Mapped[Optional[int]] = mapped_column(Integer, default=100)
    last_online: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    wearer: Mapped[Optional["Wearer"]] = relationship(back_populates="device")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="device", cascade="all, delete-orphan")
    events: Mapped[list["DeviceEvent"]] = relationship(back_populates="device", cascade="all, delete-orphan")

class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.device_id"), nullable=False)
    wearer_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("wearers.id"))
    alert_type: Mapped[str] = mapped_column(String(50), default="FALL_DETECTED")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    device: Mapped["Device"] = relationship(back_populates="alerts")

class DeviceEvent(Base):
    __tablename__ = "device_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.device_id"), nullable=False)
    wearer_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("wearers.id"))
    event_type: Mapped[str] = mapped_column(String(50)) # e.g., ACTIVITY_WALKING, DEVICE_STARTED
    description: Mapped[Optional[str]] = mapped_column(String(255))

    # Relationships
    device: Mapped["Device"] = relationship(back_populates="events")
