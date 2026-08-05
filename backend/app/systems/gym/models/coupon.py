"""优惠券模型。"""

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
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class DiscountType(str, Enum):
    FIXED = "fixed"
    PERCENT = "percent"


class ApplicableTo(str, Enum):
    RETAIL = "retail"
    MEMBERSHIP = "membership"
    BOTH = "both"


class MemberCouponStatus(str, Enum):
    UNUSED = "unused"
    USED = "used"
    EXPIRED = "expired"
    VOID = "void"


class CouponTemplate(Base):
    __tablename__ = "coupon_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    discount_type: Mapped[str] = mapped_column(String(32), nullable=False)
    threshold_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    fixed_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    percent_off: Mapped[int | None] = mapped_column(Integer)
    applicable_to: Mapped[str] = mapped_column(String(32), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_limit: Mapped[int | None] = mapped_column(Integer)
    issued_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    claimable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    per_member_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MemberCoupon(Base):
    __tablename__ = "member_coupons"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("coupon_templates.id"), nullable=False, index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=MemberCouponStatus.UNUSED.value)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OrderCouponLink(Base):
    __tablename__ = "order_coupon_links"
    __table_args__ = (UniqueConstraint("order_id", name="uq_order_coupon_link_order"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    member_coupon_id: Mapped[int] = mapped_column(ForeignKey("member_coupons.id"), nullable=False, index=True)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
