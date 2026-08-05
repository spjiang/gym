"""会籍卡种与会籍实例。"""

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


class ProductType(str, Enum):
    TERM = "term"
    COUNT = "count"
    VALUE = "value"


class MembershipStatus(str, Enum):
    ACTIVE = "active"
    FROZEN = "frozen"
    EXPIRED = "expired"
    VOID = "void"


class MembershipOrderAction(str, Enum):
    PURCHASE = "purchase"
    RENEW = "renew"


class MembershipProduct(Base):
    __tablename__ = "membership_products"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    product_type: Mapped[str] = mapped_column(String(32), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    duration_days: Mapped[int | None] = mapped_column(Integer)
    session_count: Mapped[int | None] = mapped_column(Integer)
    stored_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    is_trial: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    promo_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    promo_starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    promo_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MembershipProductAccessPoint(Base):
    __tablename__ = "membership_product_access_points"
    __table_args__ = (
        UniqueConstraint("product_id", "access_point_id", name="uq_product_access_point"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("membership_products.id"), nullable=False, index=True)
    access_point_id: Mapped[int] = mapped_column(ForeignKey("access_points.id"), nullable=False, index=True)


class Membership(Base):
    __tablename__ = "memberships"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("membership_products.id"), nullable=False, index=True)
    product_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=MembershipStatus.ACTIVE.value)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    remaining_sessions: Mapped[int | None] = mapped_column(Integer)
    balance: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MembershipOrderLink(Base):
    __tablename__ = "membership_order_links"
    __table_args__ = (UniqueConstraint("order_id", name="uq_membership_order_link_order"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("membership_products.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    target_membership_id: Mapped[int | None] = mapped_column(ForeignKey("memberships.id"))
    fulfilled_membership_id: Mapped[int | None] = mapped_column(ForeignKey("memberships.id"))
    fulfill_error: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
