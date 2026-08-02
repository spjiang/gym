"""订单与支付骨架。"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import RequestContext, get_current_context
from app.errors import AppError
from app.models.commerce import Order, OrderStatus, Payment, PaymentChannel, PaymentKind
from app.schemas.common import OfflinePayIn, OnlinePayIn, OrderCreateIn, OrderOut
from app.services.audit import write_audit
from app.services.fulfillment import fulfill_membership_order
from app.services.payments import get_online_provider
from app.services.pt_fulfillment import fulfill_pt_package_order
from app.services.retail_fulfillment import (
    assert_retail_stock_available,
    fulfill_retail_order,
    restock_retail_order,
)
from app.services.coupon import redeem_coupon_for_order, restore_coupon_for_order
from app.services.notifications import write_notification

router = APIRouter(prefix="/orders", tags=["commerce"])


@router.get("", response_model=list[OrderOut])
def list_orders(db: Session = Depends(get_db), ctx: RequestContext = Depends(get_current_context)):
    ctx.require_permission("order:read", "order:write")
    q = select(Order).where(Order.site_id == ctx.site_id)
    if not ctx.is_site_admin:
        q = q.where(Order.merchant_id == ctx.resolve_merchant_id())
    return list(db.scalars(q.order_by(Order.id.desc())).all())


@router.post("", response_model=OrderOut)
def create_order(
    body: OrderCreateIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("order:write")
    merchant_id = ctx.resolve_merchant_id(body.merchant_id)
    order = Order(
        site_id=ctx.site_id,
        merchant_id=merchant_id,
        member_id=body.member_id,
        order_type=body.order_type,
        title=body.title,
        amount=body.amount,
        status=OrderStatus.PENDING.value,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


@router.post("/{order_id}/pay/offline", response_model=OrderOut)
def pay_offline(
    order_id: int,
    body: OfflinePayIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("order:write")
    order = db.get(Order, order_id)
    if order is None or order.site_id != ctx.site_id:
        raise AppError("not_found", "订单不存在", status_code=404)
    if not ctx.is_site_admin and order.merchant_id != ctx.merchant_id:
        raise AppError("forbidden", "禁止跨商户操作", status_code=403)
    if order.status != OrderStatus.PENDING.value:
        raise AppError("invalid_state", "仅待支付订单可登记线下收款", status_code=400)
    if body.channel not in {PaymentChannel.OFFLINE_CASH.value, PaymentChannel.OFFLINE_TRANSFER.value}:
        raise AppError("invalid_channel", "非法线下支付方式", status_code=400)

    # 零售：支付前校验库存，不足则拒付
    assert_retail_stock_available(db, order)

    order.status = OrderStatus.PAID.value
    db.add(
        Payment(
            order_id=order.id,
            kind=PaymentKind.CHARGE.value,
            channel=body.channel,
            amount=order.amount,
            note=body.note,
        )
    )
    write_audit(
        db,
        action="order.pay_offline",
        target_type="order",
        target_id=order.id,
        summary=f"线下支付 {body.channel}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=order.merchant_id,
    )
    fulfill_membership_order(db, order, actor_staff_id=ctx.staff.id)
    fulfill_pt_package_order(db, order, actor_staff_id=ctx.staff.id)
    fulfill_retail_order(db, order, actor_staff_id=ctx.staff.id)
    redeem_coupon_for_order(db, order, actor_staff_id=ctx.staff.id)
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
    db.commit()
    db.refresh(order)
    return order


@router.post("/{order_id}/pay/online", response_model=OrderOut)
def pay_online(
    order_id: int,
    body: OnlinePayIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("order:write")
    order = db.get(Order, order_id)
    if order is None or order.site_id != ctx.site_id:
        raise AppError("not_found", "订单不存在", status_code=404)
    if not ctx.is_site_admin and order.merchant_id != ctx.merchant_id:
        raise AppError("forbidden", "禁止跨商户操作", status_code=403)
    if order.status != OrderStatus.PENDING.value:
        raise AppError("invalid_state", "仅待支付订单可发起线上支付", status_code=400)

    result = get_online_provider().create_payment(
        order_id=order.id, amount=str(order.amount), title=order.title
    )
    if not result.ok:
        raise AppError("online_pay_failed", result.message, status_code=400)

    assert_retail_stock_available(db, order)

    order.status = OrderStatus.PAID.value
    db.add(
        Payment(
            order_id=order.id,
            kind=PaymentKind.CHARGE.value,
            channel=PaymentChannel.ONLINE.value,
            amount=order.amount,
            note=result.provider_ref,
        )
    )
    fulfill_membership_order(db, order, actor_staff_id=ctx.staff.id)
    fulfill_pt_package_order(db, order, actor_staff_id=ctx.staff.id)
    fulfill_retail_order(db, order, actor_staff_id=ctx.staff.id)
    redeem_coupon_for_order(db, order, actor_staff_id=ctx.staff.id)
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
    db.commit()
    db.refresh(order)
    return order


@router.post("/{order_id}/refund", response_model=OrderOut)
def refund_order(
    order_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("order:write")
    order = db.get(Order, order_id)
    if order is None or order.site_id != ctx.site_id:
        raise AppError("not_found", "订单不存在", status_code=404)
    if not ctx.is_site_admin and order.merchant_id != ctx.merchant_id:
        raise AppError("forbidden", "禁止跨商户操作", status_code=403)
    if order.status != OrderStatus.PAID.value:
        raise AppError("invalid_state", "仅已支付订单可退款", status_code=400)

    restock_retail_order(db, order, actor_staff_id=ctx.staff.id)
    restore_coupon_for_order(db, order, actor_staff_id=ctx.staff.id)

    order.status = OrderStatus.REFUNDED.value
    db.add(
        Payment(
            order_id=order.id,
            kind=PaymentKind.REFUND.value,
            channel=PaymentChannel.OFFLINE_CASH.value,
            amount=order.amount,
            note="全额退款",
        )
    )
    write_audit(
        db,
        action="order.refund",
        target_type="order",
        target_id=order.id,
        summary="全额退款",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=order.merchant_id,
    )
    db.commit()
    db.refresh(order)
    return order
