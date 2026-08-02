"""场地级会员主档。"""

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class FaceStatus(str, Enum):
    NOT_ENROLLED = "not_enrolled"
    ENROLLED = "enrolled"


class Member(Base):
    __tablename__ = "members"
    __table_args__ = (UniqueConstraint("site_id", "phone", name="uq_members_site_phone"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    face_status: Mapped[str] = mapped_column(String(32), default=FaceStatus.NOT_ENROLLED.value, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MerchantMember(Base):
    __tablename__ = "merchant_members"
    __table_args__ = (UniqueConstraint("merchant_id", "member_id", name="uq_merchant_member"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
