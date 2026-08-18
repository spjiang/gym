"""订单支付履约（回调 / dry-run 共用）。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.systems.gym.services.activity_fulfillment import fulfill_activity_order
from app.systems.gym.services.commission import accrue_order_commissions
from app.systems.gym.services.coupon import redeem_coupon_for_order
from app.systems.gym.services.fulfillment import fulfill_membership_order
from app.systems.gym.services.pt_fulfillment import fulfill_pt_package_order
from app.systems.gym.services.retail_fulfillment import assert_retail_stock_available, fulfill_retail_order
from app.systems.platform.models.commerce import Order, OrderStatus, Payment, PaymentChannel, PaymentKind
from app.systems.platform.models.payment_settings import PaymentIntent
from app.systems.platform.services.notifications import write_notification


def fulfill_paid_order(
    db: Session,
    order: Order,
    *,
    provider_ref: str | None,
    actor_staff_id: int | None = None,
) -> Order:
    """将待支付订单置为已付并履约；已支付则幂等返回。"""
    if order.status == OrderStatus.PAID.value:
        return order
    if order.status != OrderStatus.PENDING.value:
        raise AppError("invalid_state", "仅待支付订单可确认收款", status_code=400)

    assert_retail_stock_available(db, order)
    order.status = OrderStatus.PAID.value
    from app.systems.catering.services.kitchen import start_dining_kitchen

    start_dining_kitchen(order)
    db.add(
        Payment(
            order_id=order.id,
            kind=PaymentKind.CHARGE.value,
            channel=PaymentChannel.ONLINE.value,
            amount=order.amount,
            note=provider_ref,
        )
    )
    fulfill_membership_order(db, order, actor_staff_id=actor_staff_id)
    fulfill_pt_package_order(db, order, actor_staff_id=actor_staff_id)
    fulfill_retail_order(db, order, actor_staff_id=actor_staff_id)
    fulfill_activity_order(db, order, actor_staff_id=actor_staff_id)
    redeem_coupon_for_order(db, order, actor_staff_id=actor_staff_id)
    accrue_order_commissions(db, order)
    if order.member_id is not None:
        write_notification(
            db,
            site_id=order.site_id,
            merchant_id=order.merchant_id,
            member_id=order.member_id,
            event_type="order.paid",
            title="支付成功",
            body=f"订单 #{order.id} {order.title} 已支付 ¥{order.amount}",
        )
    return order


def mark_intent_succeeded(db: Session, intent: PaymentIntent, *, provider_ref: str | None = None) -> None:
    if intent.status == "succeeded":
        return
    intent.status = "succeeded"
    intent.succeeded_at = datetime.now(timezone.utc)
    if provider_ref:
        intent.provider_ref = provider_ref
