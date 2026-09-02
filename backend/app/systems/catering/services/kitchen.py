"""餐饮后厨履约：制作中 → 待取餐 → 已完成。"""

from __future__ import annotations

from enum import Enum

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.systems.platform.models.commerce import Order, OrderStatus
from app.systems.platform.services.audit import write_audit
from app.systems.platform.services.notifications import write_notification


class DiningStatus(str, Enum):
    PREPARING = "preparing"
    READY = "ready"
    COMPLETED = "completed"


def start_dining_kitchen(order: Order) -> None:
    """支付成功后进入制作中，并补发取餐号。"""
    if order.order_type != "dining":
        return
    if not order.pickup_code:
        from app.systems.catering.api.member_catering import assign_pickup_code

        order.pickup_code = assign_pickup_code(order.id)
    if not order.dining_status:
        order.dining_status = DiningStatus.PREPARING.value


def _require_paid_dining(order: Order | None) -> Order:
    if order is None or order.order_type != "dining":
        raise AppError("not_found", "餐饮订单不存在", status_code=404)
    if order.status != OrderStatus.PAID.value:
        raise AppError("invalid_state", "仅已支付订单可更新制作状态", status_code=400)
    return order


def mark_dining_ready(
    db: Session,
    order: Order,
    *,
    actor_staff_id: int | None = None,
) -> Order:
    row = _require_paid_dining(order)
    current = row.dining_status or DiningStatus.PREPARING.value
    if current != DiningStatus.PREPARING.value:
        raise AppError("invalid_state", "当前不是制作中，无法出餐", status_code=400)
    row.dining_status = DiningStatus.READY.value
    write_audit(
        db,
        action="catering.ready",
        target_type="order",
        target_id=row.id,
        summary=f"出餐待取 取餐号 {row.pickup_code or '—'}",
        actor_staff_id=actor_staff_id,
        site_id=row.site_id,
        merchant_id=row.merchant_id,
    )
    if row.member_id is not None:
        write_notification(
            db,
            site_id=row.site_id,
            merchant_id=row.merchant_id,
            member_id=row.member_id,
            event_type="dining.ready",
            title="可以取餐了",
            body=f"订单 #{row.id} 已出餐，取餐号 {row.pickup_code or '—'}",
        )
    return row


def mark_dining_completed(
    db: Session,
    order: Order,
    *,
    actor_staff_id: int | None = None,
) -> Order:
    row = _require_paid_dining(order)
    if row.dining_status != DiningStatus.READY.value:
        raise AppError("invalid_state", "仅待取餐订单可完成", status_code=400)
    row.dining_status = DiningStatus.COMPLETED.value
    write_audit(
        db,
        action="catering.complete",
        target_type="order",
        target_id=row.id,
        summary=f"完成取餐 取餐号 {row.pickup_code or '—'}",
        actor_staff_id=actor_staff_id,
        site_id=row.site_id,
        merchant_id=row.merchant_id,
    )
    return row


def undo_dining_status(
    db: Session,
    order: Order,
    *,
    actor_staff_id: int | None = None,
) -> Order:
    """厨房误操作回退：ready→preparing，completed→ready。"""
    row = _require_paid_dining(order)
    current = row.dining_status or DiningStatus.PREPARING.value
    if current == DiningStatus.READY.value:
        row.dining_status = DiningStatus.PREPARING.value
        summary = "回退为制作中"
    elif current == DiningStatus.COMPLETED.value:
        row.dining_status = DiningStatus.READY.value
        summary = "回退为待取餐"
    else:
        raise AppError("invalid_state", "当前状态不可回退", status_code=400)
    write_audit(
        db,
        action="catering.undo",
        target_type="order",
        target_id=row.id,
        summary=f"{summary} 取餐号 {row.pickup_code or '—'}",
        actor_staff_id=actor_staff_id,
        site_id=row.site_id,
        merchant_id=row.merchant_id,
    )
    return row


def cancel_pending_dining_order(
    db: Session,
    order: Order,
    *,
    actor_staff_id: int | None = None,
) -> Order:
    """待支付餐饮单取消：关支付意图、退回优惠券、订单作废。"""
    from app.systems.platform.services.order_lock import lock_order
    from app.systems.platform.services.payment_capture import (
        capture_wechat_success,
        close_open_intents_for_order,
    )

    order = lock_order(db, order.id, site_id=order.site_id)
    if order.order_type != "dining":
        raise AppError("not_found", "餐饮订单不存在", status_code=404)
    if order.status != OrderStatus.PENDING.value:
        raise AppError("invalid_state", "仅待支付订单可取消", status_code=400)

    from app.systems.gym.services.coupon import detach_coupon_link_for_order

    paid_stale = close_open_intents_for_order(db, order)
    if paid_stale is not None:
        capture_wechat_success(
            db,
            order=order,
            intent=paid_stale,
            amount_fen=None,
            require_amount=False,
        )
        raise AppError("invalid_state", "订单已支付，无法取消", status_code=400)

    detach_coupon_link_for_order(db, order)
    order.status = OrderStatus.CANCELLED.value
    write_audit(
        db,
        action="catering.cancel",
        target_type="order",
        target_id=order.id,
        summary="取消待支付餐饮订单",
        actor_staff_id=actor_staff_id,
        site_id=order.site_id,
        merchant_id=order.merchant_id,
    )
    return order
