from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, UUID, DateTime
from sqlalchemy.sql import func
import uuid
import datetime
from typing import List

class Base(DeclarativeBase):
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=True)

    # Relationships
    users: Mapped[List["User"]] = relationship(back_populates="organization")
    wearers: Mapped[List["Wearer"]] = relationship(back_populates="organization")
