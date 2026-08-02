"""健身房器材台账与报修（非门禁设备）。"""

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class EquipmentStatus(str, Enum):
    IN_USE = "in_use"
    REPAIR = "repair"
    DISABLED = "disabled"
    SCRAPPED = "scrapped"


class RepairTicketStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CLOSED = "closed"


class EquipmentAsset(Base):
    __tablename__ = "equipment_assets"
    __table_args__ = (UniqueConstraint("merchant_id", "asset_code", name="uq_equipment_merchant_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="other")
    brand_model: Mapped[str | None] = mapped_column(String(128))
    asset_code: Mapped[str] = mapped_column(String(64), nullable=False)
    area: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=EquipmentStatus.IN_USE.value)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EquipmentRepairTicket(Base):
    __tablename__ = "equipment_repair_tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("equipment_assets.id"), nullable=False, index=True)
    reporter_staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=RepairTicketStatus.OPEN.value)
    resolution: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
