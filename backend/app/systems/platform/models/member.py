"""场地级会员主档。"""

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class FaceStatus(str, Enum):
    NOT_ENROLLED = "not_enrolled"
    ENROLLED = "enrolled"


class AcquisitionSource(str, Enum):
    MERCHANT = "merchant"
    PLATFORM = "platform"


class Member(Base):
    __tablename__ = "members"
    __table_args__ = (UniqueConstraint("site_id", "phone", name="uq_members_site_phone"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    face_status: Mapped[str] = mapped_column(String(32), default=FaceStatus.NOT_ENROLLED.value, nullable=False)
    acquisition_source: Mapped[str] = mapped_column(
        String(32), default=AcquisitionSource.PLATFORM.value, nullable=False
    )
    first_merchant_id: Mapped[int | None] = mapped_column(ForeignKey("merchants.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MerchantMember(Base):
    __tablename__ = "merchant_members"
    __table_args__ = (UniqueConstraint("merchant_id", "member_id", name="uq_merchant_member"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
