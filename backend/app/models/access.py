"""门禁点、设备、授权与通行事件。"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AccessPoint(Base):
    __tablename__ = "access_points"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    merchant_id: Mapped[int | None] = mapped_column(ForeignKey("merchants.id"), index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_public_area: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AccessDevice(Base):
    __tablename__ = "access_devices"
    __table_args__ = (UniqueConstraint("device_code", name="uq_access_devices_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    access_point_id: Mapped[int] = mapped_column(ForeignKey("access_points.id"), nullable=False, index=True)
    device_code: Mapped[str] = mapped_column(String(64), nullable=False)
    api_key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_online: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AccessGrant(Base):
    __tablename__ = "access_grants"

    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False, index=True)
    access_point_id: Mapped[int] = mapped_column(ForeignKey("access_points.id"), nullable=False, index=True)
    merchant_id: Mapped[int | None] = mapped_column(ForeignKey("merchants.id"), index=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AccessEvent(Base):
    __tablename__ = "access_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("access_devices.id"), nullable=False, index=True)
    access_point_id: Mapped[int] = mapped_column(ForeignKey("access_points.id"), nullable=False, index=True)
    member_id: Mapped[int | None] = mapped_column(ForeignKey("members.id"), index=True)
    allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(128))
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
