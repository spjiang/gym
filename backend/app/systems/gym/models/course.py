"""私教课包与团课相关模型。"""

from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.systems.platform.models.identity import JSONType


class PtPackageStatus(str, Enum):
    ACTIVE = "active"
    EXHAUSTED = "exhausted"
    EXPIRED = "expired"
    VOID = "void"


class GroupSessionStatus(str, Enum):
    OPEN = "open"
    CANCELLED = "cancelled"


class GroupBookingStatus(str, Enum):
    BOOKED = "booked"
    CANCELLED = "cancelled"
    ATTENDED = "attended"
    NO_SHOW = "no_show"


class Coach(Base):
    __tablename__ = "coaches"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    # 可选：仅用于登录后台看佣金；主身份挂会员
    staff_user_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"), nullable=True, index=True)
    # 必填（创建时）：推广码、课时收益统一走会员机制
    member_id: Mapped[int | None] = mapped_column(ForeignKey("members.id"), nullable=True, index=True)
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str | None] = mapped_column(String(64))
    gender: Mapped[str | None] = mapped_column(String(16))
    phone: Mapped[str | None] = mapped_column(String(32))
    years_experience: Mapped[int | None] = mapped_column(Integer)
    hourly_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    # 教练个人私教课佣金比例；留空回落商户 pt_session 提成规则
    pt_commission_rate: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    specialties: Mapped[str | None] = mapped_column(String(255))
    certifications: Mapped[str | None] = mapped_column(Text)
    bio: Mapped[str | None] = mapped_column(Text)
    availability_note: Mapped[str | None] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(String(255))
    intro_image_urls: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PtPackageProduct(Base):
    __tablename__ = "pt_package_products"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    session_count: Mapped[int] = mapped_column(Integer, nullable=False)
    valid_days: Mapped[int] = mapped_column(Integer, nullable=False)
    # True 表示适用全部启用教练；False 时看关联表
    all_coaches: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    promo_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    promo_starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    promo_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PtPackageProductCoach(Base):
    __tablename__ = "pt_package_product_coaches"
    __table_args__ = (UniqueConstraint("product_id", "coach_id", name="uq_pt_product_coach"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("pt_package_products.id"), nullable=False, index=True)
    coach_id: Mapped[int] = mapped_column(ForeignKey("coaches.id"), nullable=False, index=True)


class PtPackage(Base):
    __tablename__ = "pt_packages"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("pt_package_products.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=PtPackageStatus.ACTIVE.value)
    remaining_sessions: Mapped[int] = mapped_column(Integer, nullable=False)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PtOrderLink(Base):
    __tablename__ = "pt_order_links"
    __table_args__ = (UniqueConstraint("order_id", name="uq_pt_order_link_order"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("pt_package_products.id"), nullable=False)
    fulfilled_package_id: Mapped[int | None] = mapped_column(ForeignKey("pt_packages.id"))
    fulfill_error: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GroupCourse(Base):
    __tablename__ = "group_courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    difficulty: Mapped[str | None] = mapped_column(String(32))
    default_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    default_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    book_ahead_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cancel_ahead_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GroupSession(Base):
    __tablename__ = "group_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("group_courses.id"), nullable=False, index=True)
    coach_id: Mapped[int] = mapped_column(ForeignKey("coaches.id"), nullable=False, index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    room: Mapped[str | None] = mapped_column(String(64))
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=GroupSessionStatus.OPEN.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GroupBooking(Base):
    __tablename__ = "group_bookings"
    __table_args__ = (UniqueConstraint("session_id", "member_id", name="uq_group_booking_session_member"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("group_sessions.id"), nullable=False, index=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=GroupBookingStatus.BOOKED.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
