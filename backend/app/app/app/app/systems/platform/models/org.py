"""场地与商户组织模型。"""

from datetime import date, datetime
from enum import Enum

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.systems.platform.models.identity import JSONType


class MerchantStatus(str, Enum):
    PREPARING = "preparing"
    ACTIVE = "active"
    DISABLED = "disabled"


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255))
    tagline: Mapped[str | None] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text)
    service_phone: Mapped[str | None] = mapped_column(String(32))
    business_hours: Mapped[str | None] = mapped_column(String(128))
    cover_image_url: Mapped[str | None] = mapped_column(String(255))
    banner_image_urls: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
    gallery_image_urls: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
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
    legal_name: Mapped[str | None] = mapped_column(String(128))
    credit_code: Mapped[str | None] = mapped_column(String(32))
    license_no: Mapped[str | None] = mapped_column(String(64))
    license_image_url: Mapped[str | None] = mapped_column(String(512))
    legal_person: Mapped[str | None] = mapped_column(String(64))
    registered_address: Mapped[str | None] = mapped_column(String(255))
    business_address: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(32))
    contact_email: Mapped[str | None] = mapped_column(String(128))
    business_hours: Mapped[str | None] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text)
    tagline: Mapped[str | None] = mapped_column(String(64))
    cover_image_url: Mapped[str | None] = mapped_column(String(255))
    gallery_image_urls: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
    lease_starts_on: Mapped[date | None] = mapped_column(Date)
    lease_ends_on: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    site: Mapped[Site] = relationship(back_populates="merchants")
    merchant_type: Mapped[MerchantType] = relationship(back_populates="merchants")
    subsystems: Mapped[list["MerchantSubsystem"]] = relationship(back_populates="merchant")
    contacts: Mapped[list["MerchantContact"]] = relationship(
        back_populates="merchant", cascade="all, delete-orphan"
    )


class MerchantSubsystem(Base):
    """商户关联的业态子系统（可多选，数据仍按 merchant_id 隔离）。"""

    __tablename__ = "merchant_subsystems"
    __table_args__ = (UniqueConstraint("merchant_id", "system_code", name="uq_merchant_subsystem"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    system_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    merchant: Mapped[Merchant] = relationship(back_populates="subsystems")


class MerchantContactKind(str, Enum):
    PRIMARY = "primary"
    EMERGENCY = "emergency"
    OTHER = "other"


class MerchantContact(Base):
    """商户联系人，支持多名紧急联系人。"""

    __tablename__ = "merchant_contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str | None] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(16), default=MerchantContactKind.OTHER.value, nullable=False)
    remark: Mapped[str | None] = mapped_column(String(255))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    merchant: Mapped[Merchant] = relationship(back_populates="contacts")
