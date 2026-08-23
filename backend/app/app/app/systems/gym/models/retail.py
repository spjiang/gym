"""零售商品与库存模型。"""

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


class StockMovementType(str, Enum):
    IN = "in"
    OUT = "out"
    ADJUST = "adjust"
    SALE = "sale"
    REFUND = "refund"


class ProductCategory(Base):
    __tablename__ = "product_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RetailSku(Base):
    __tablename__ = "retail_skus"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("product_categories.id"), index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False, default="件")
    barcode: Mapped[str | None] = mapped_column(String(64))
    stock_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    promo_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    promo_starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    promo_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    remark: Mapped[str | None] = mapped_column(Text)
    image_urls: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    sku_id: Mapped[int] = mapped_column(ForeignKey("retail_skus.id"), nullable=False, index=True)
    movement_type: Mapped[str] = mapped_column(String(32), nullable=False)
    quantity_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    stock_after: Mapped[int] = mapped_column(Integer, nullable=False)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), index=True)
    note: Mapped[str | None] = mapped_column(String(255))
    actor_staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RetailOrderLink(Base):
    __tablename__ = "retail_order_links"
    __table_args__ = (UniqueConstraint("order_id", name="uq_retail_order_link_order"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    member_id: Mapped[int | None] = mapped_column(ForeignKey("members.id"))
    fulfilled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fulfill_error: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RetailOrderItem(Base):
    __tablename__ = "retail_order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_link_id: Mapped[int] = mapped_column(ForeignKey("retail_order_links.id"), nullable=False, index=True)
    sku_id: Mapped[int] = mapped_column(ForeignKey("retail_skus.id"), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
