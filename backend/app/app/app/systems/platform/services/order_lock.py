"""订单并发控制：支付/退款路径对同一订单加行锁。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.systems.platform.models.commerce import Order


def lock_order(db: Session, order_id: int, *, site_id: int) -> Order:
    order = db.scalar(
        select(Order).where(Order.id == order_id, Order.site_id == site_id).with_for_update()
    )
    if order is None:
        raise AppError("not_found", "订单不存在", status_code=404)
    return order
