"""场地与商户组织模型。"""

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class MerchantStatus(str, Enum):
    PREPARING = "preparing"
    ACTIVE = "active"
    DISABLED = "disabled"


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    merchants: Mapped[list["Merchant"]] = relationship(back_populates="site")


class MerchantType(Base):
    __tablename__ = "merchant_types"
    __table_args__ = (UniqueConstraint("code", name="uq_merchant_types_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    merchants: Mapped[list["Merchant"]] = relationship(back_populates="merchant_type")


class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    merchant_type_id: Mapped[int] = mapped_column(ForeignKey("merchant_types.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=MerchantStatus.PREPARING.value, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    site: Mapped[Site] = relationship(back_populates="merchants")
    merchant_type: Mapped[MerchantType] = relationship(back_populates="merchants")
    subsystems: Mapped[list["MerchantSubsystem"]] = relationship(back_populates="merchant")


class MerchantSubsystem(Base):
    """商户关联的业态子系统（可多选，数据仍按 merchant_id 隔离）。"""

    __tablename__ = "merchant_subsystems"
    __table_args__ = (UniqueConstraint("merchant_id", "system_code", name="uq_merchant_subsystem"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    system_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    merchant: Mapped[Merchant] = relationship(back_populates="subsystems")
