"""零售订单履约与退款回补。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.systems.platform.models.commerce import Order
from app.systems.gym.models.retail import (
    RetailOrderItem,
    RetailOrderLink,
    RetailSku,
    StockMovementType,
)
from app.systems.platform.services.audit import write_audit
from app.systems.gym.services.retail_stock import apply_stock_delta


def _items_for_order(db: Session, order_id: int) -> tuple[RetailOrderLink, list[RetailOrderItem]]:
    link = db.scalar(select(RetailOrderLink).where(RetailOrderLink.order_id == order_id))
    if link is None:
        raise AppError("not_found", "零售订单关联不存在", status_code=404)
    items = list(
        db.scalars(select(RetailOrderItem).where(RetailOrderItem.order_link_id == link.id)).all()
    )
    return link, items


def assert_retail_stock_available(db: Session, order: Order) -> None:
    """支付前校验：库存不足则抛错，调用方不得将订单标为已支付。"""
    if order.order_type != "retail":
        return
    link = db.scalar(select(RetailOrderLink).where(RetailOrderLink.order_id == order.id))
    if link is None:
        # 非 /retail/orders 创建的占位单，不做库存校验
        return
    items = list(
        db.scalars(select(RetailOrderItem).where(RetailOrderItem.order_link_id == link.id)).all()
    )
    if not items:
        raise AppError("empty_order", "零售订单无行项目", status_code=400)
    for item in items:
        sku = db.scalar(select(RetailSku).where(RetailSku.id == item.sku_id).with_for_update())
        if sku is None or sku.merchant_id != order.merchant_id:
            raise AppError("sku_missing", "商品不存在", status_code=400)
        if not sku.is_active:
            raise AppError("sku_inactive", f"商品已停用: {sku.name}", status_code=400)
        if sku.stock_qty < item.quantity:
            raise AppError(
                "insufficient_stock",
                f"库存不足: {sku.name} 需 {item.quantity} 剩 {sku.stock_qty}",
                status_code=400,
            )


def fulfill_retail_order(db: Session, order: Order, *, actor_staff_id: int | None = None) -> None:
    """支付成功后扣库存；假定调用方已通过 assert_retail_stock_available。"""
    if order.order_type != "retail":
        return
    link = db.scalar(select(RetailOrderLink).where(RetailOrderLink.order_id == order.id))
    if link is None:
        return
    items = list(
        db.scalars(select(RetailOrderItem).where(RetailOrderItem.order_link_id == link.id)).all()
    )
    if link.fulfilled:
        return
    try:
        for item in items:
            sku = db.scalar(select(RetailSku).where(RetailSku.id == item.sku_id).with_for_update())
            if sku is None:
                raise AppError("sku_missing", "商品不存在", status_code=400)
            apply_stock_delta(
                db,
                sku,
                delta=-item.quantity,
                movement_type=StockMovementType.SALE.value,
                note="零售出库",
                order_id=order.id,
                actor_staff_id=actor_staff_id,
            )
        link.fulfilled = True
        link.fulfill_error = None
        write_audit(
            db,
            action="retail.fulfill",
            target_type="order",
            target_id=order.id,
            summary="零售履约扣库存",
            actor_staff_id=actor_staff_id,
            site_id=order.site_id,
            merchant_id=order.merchant_id,
        )
    except Exception as exc:  # noqa: BLE001
        link.fulfill_error = str(exc)[:250]
        raise


def restock_retail_order(db: Session, order: Order, *, actor_staff_id: int | None = None) -> None:
    """全额退款时回补已履约库存。"""
    if order.order_type != "retail":
        return
    link = db.scalar(select(RetailOrderLink).where(RetailOrderLink.order_id == order.id))
    if link is None or not link.fulfilled:
        return
    items = list(
        db.scalars(select(RetailOrderItem).where(RetailOrderItem.order_link_id == link.id)).all()
    )
    for item in items:
        sku = db.scalar(select(RetailSku).where(RetailSku.id == item.sku_id).with_for_update())
        if sku is None:
            continue
        apply_stock_delta(
            db,
            sku,
            delta=item.quantity,
            movement_type=StockMovementType.REFUND.value,
            note="零售退款回补",
            order_id=order.id,
            actor_staff_id=actor_staff_id,
        )
    link.fulfilled = False
    write_audit(
        db,
        action="retail.restock",
        target_type="order",
        target_id=order.id,
        summary="零售退款回补库存",
        actor_staff_id=actor_staff_id,
        site_id=order.site_id,
        merchant_id=order.merchant_id,
    )
