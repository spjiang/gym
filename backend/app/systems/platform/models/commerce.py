"""订单与支付流水骨架。"""

from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class OrderStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class PaymentChannel(str, Enum):
    OFFLINE_CASH = "offline_cash"
    OFFLINE_TRANSFER = "offline_transfer"
    ONLINE = "online"


class PaymentKind(str, Enum):
    CHARGE = "charge"
    REFUND = "refund"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    member_id: Mapped[int | None] = mapped_column(ForeignKey("members.id"), index=True)
    # 可扩展：retail / membership / course_pack ...
    order_type: Mapped[str] = mapped_column(String(64), nullable=False, default="retail")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=OrderStatus.PENDING.value, nullable=False)
    pickup_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    customer_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
