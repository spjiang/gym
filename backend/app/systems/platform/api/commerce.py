"""订单与支付骨架。"""

from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import RequestContext, get_current_context
from app.core.domain.subsystems import assert_order_type_allowed
from app.core.errors import AppError
from app.core.schemas.common import MemberBrief, OfflinePayIn, OnlinePayIn, OrderCreateIn, OrderOut
from app.core.schemas.paging import PageOut
from app.systems.gym.services.activity_fulfillment import fulfill_activity_order
from app.systems.gym.services.commission import accrue_order_commissions
from app.systems.gym.services.coupon import redeem_coupon_for_order
from app.systems.gym.services.fulfillment import fulfill_membership_order
from app.systems.gym.services.pt_fulfillment import fulfill_pt_package_order
from app.systems.gym.services.retail_fulfillment import (
    assert_retail_stock_available,
    fulfill_retail_order,
)
from app.systems.platform.models.commerce import Order, OrderStatus, Payment, PaymentChannel, PaymentKind
from app.systems.platform.models.member import Member
from app.systems.platform.services.audit import write_audit
from app.systems.platform.services.notifications import write_notification
from app.systems.platform.services.order_pricing import price_order
from app.systems.platform.services.payments import get_online_provider

router = APIRouter(prefix="/orders", tags=["commerce"])


def _order_out(db: Session, order: Order) -> OrderOut:
    member_brief = None
    if order.member_id is not None:
        m = db.get(Member, order.member_id)
        if m is not None:
            member_brief = MemberBrief(id=m.id, name=m.name, phone=m.phone)
    return OrderOut(
        id=order.id,
        site_id=order.site_id,
        merchant_id=order.merchant_id,
        member_id=order.member_id,
        order_type=order.order_type,
        title=order.title,
        amount=order.amount,
        original_amount=order.original_amount,
        promotion_discount_amount=order.promotion_discount_amount or Decimal("0"),
        promoter_code=order.promoter_code,
        refunded_amount=getattr(order, "refunded_amount", None) or Decimal("0"),
        status=order.status,
        pickup_code=order.pickup_code,
        customer_note=order.customer_note,
        dining_status=order.dining_status,
        created_at=order.created_at,
        member=member_brief,
    )


@router.get("", response_model=PageOut[OrderOut])
def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    merchant_id: int | None = None,
    order_type: str | None = None,
    status: str | None = None,
    dining_status: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("order:read", "order:write")
    filters = [Order.site_id == ctx.site_id]
    if not ctx.is_site_wide:
        filters.append(Order.merchant_id == ctx.resolve_merchant_id())
    elif merchant_id is not None:
        filters.append(Order.merchant_id == merchant_id)
    if order_type:
        filters.append(Order.order_type == order_type)
    if status:
        filters.append(Order.status == status)
    if dining_status:
        filters.append(Order.dining_status == dining_status)
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        member_ids = select(Member.id).where(
            or_(Member.phone.ilike(like), Member.name.ilike(like))
        )
        if keyword.isdigit():
            filters.append(or_(Order.id == int(keyword), Order.member_id.in_(member_ids), Order.title.ilike(like)))
        else:
            filters.append(or_(Order.title.ilike(like), Order.member_id.in_(member_ids)))

    total = db.scalar(select(func.count()).select_from(Order).where(*filters)) or 0
    rows = list(
        db.scalars(
            select(Order)
            .where(*filters)
            .order_by(Order.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return PageOut(
        items=[_order_out(db, o) for o in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=OrderOut)
def create_order(
    body: OrderCreateIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("order:write")
    merchant_id = ctx.resolve_merchant_id(body.merchant_id)
    assert_order_type_allowed(db, merchant_id, body.order_type)
    if body.amount <= 0:
        raise AppError("validation_error", "订单金额必须大于 0", status_code=422)
    if not body.title.strip():
        raise AppError("validation_error", "订单标题不能为空", status_code=422)
    order = Order(
        site_id=ctx.site_id,
        merchant_id=merchant_id,
        member_id=body.member_id,
        order_type=body.order_type,
        title=body.title.strip(),
        amount=body.amount,
        status=OrderStatus.PENDING.value,
        seller_staff_id=ctx.staff.id,
    )
    db.add(order)
    db.flush()
    price_order(db, order=order, original_amount=body.amount)
    db.commit()
    db.refresh(order)
    return _order_out(db, order)


@router.post("/{order_id}/pay/offline", response_model=OrderOut)
def pay_offline(
    order_id: int,
    body: OfflinePayIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("order:write")
    from app.systems.platform.services.order_lock import lock_order

    order = lock_order(db, order_id, site_id=ctx.site_id)
    ctx.assert_merchant_access(order.merchant_id)
    if order.status != OrderStatus.PENDING.value:
        raise AppError("invalid_state", "仅待支付订单可登记线下收款", status_code=400)
    if body.channel not in {PaymentChannel.OFFLINE_CASH.value, PaymentChannel.OFFLINE_TRANSFER.value}:
        raise AppError("invalid_channel", "非法线下支付方式", status_code=400)

    # 零售：支付前校验库存，不足则拒付
    assert_retail_stock_available(db, order)

    order.status = OrderStatus.PAID.value
    from app.systems.catering.services.kitchen import start_dining_kitchen

    start_dining_kitchen(order)
    if order.seller_staff_id is None:
        order.seller_staff_id = ctx.staff.id
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
    fulfill_activity_order(db, order, actor_staff_id=ctx.staff.id)
    redeem_coupon_for_order(db, order, actor_staff_id=ctx.staff.id)
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
    db.commit()
    db.refresh(order)
    return _order_out(db, order)


@router.post("/{order_id}/pay/online", response_model=OrderOut)
def pay_online(
    order_id: int,
    body: OnlinePayIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("order:write")
    from app.systems.platform.services.order_lock import lock_order

    order = lock_order(db, order_id, site_id=ctx.site_id)
    ctx.assert_merchant_access(order.merchant_id)
    if order.status != OrderStatus.PENDING.value:
        raise AppError("invalid_state", "仅待支付订单可发起线上支付", status_code=400)
    if order.seller_staff_id is None:
        order.seller_staff_id = ctx.staff.id

    result = get_online_provider(db, ctx.site_id).create_payment(
        order_id=order.id,
        amount=str(order.amount),
        title=order.title,
        out_trade_no=f"staff-{order.id}-{int(__import__('time').time())}",
        pay_scene=getattr(body, "pay_scene", None) or "miniprogram",
        staff_capture=True,
    )
    if not result.ok:
        raise AppError("online_pay_failed", result.message, status_code=400)

    from app.systems.platform.services.order_fulfill import fulfill_paid_order

    if result.immediate_capture:
        fulfill_paid_order(db, order, provider_ref=result.provider_ref, actor_staff_id=ctx.staff.id)
    write_audit(
        db,
        action="order.pay_online",
        target_type="order",
        target_id=order.id,
        summary=f"线上支付 {result.provider_ref}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=order.merchant_id,
    )
    db.commit()
    db.refresh(order)
    return _order_out(db, order)


class RefundIn(BaseModel):
    amount: Decimal | None = None
    channel: str = Field(default="wechat_original")
    reason: str | None = None
    force: bool = False


@router.get("/{order_id}/refund/preview")
def refund_preview(
    order_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("order:write", "order:read")
    order = db.get(Order, order_id)
    if order is None or order.site_id != ctx.site_id:
        raise AppError("not_found", "订单不存在", status_code=404)
    ctx.assert_merchant_access(order.merchant_id)
    from app.systems.platform.services.refunds import preview_refund

    return preview_refund(db, order)


@router.post("/{order_id}/pay/query")
def pay_query(
    order_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("order:write", "payment:reconcile")
    order = db.get(Order, order_id)
    if order is None or order.site_id != ctx.site_id:
        raise AppError("not_found", "订单不存在", status_code=404)
    ctx.assert_merchant_access(order.merchant_id)
    from app.systems.platform.api.payment_notify import sync_pay_query

    return sync_pay_query(db, order)


@router.post("/{order_id}/refund", response_model=OrderOut)
def refund_order(
    order_id: int,
    body: RefundIn | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("order:write")
    from app.systems.platform.services.order_lock import lock_order

    order = lock_order(db, order_id, site_id=ctx.site_id)
    ctx.assert_merchant_access(order.merchant_id)

    body = body or RefundIn()
    from app.systems.platform.services.refunds import create_refund, preview_refund, refundable_balance

    amount = body.amount
    if amount is None:
        amount = Decimal(preview_refund(db, order)["suggested_amount"])
        if amount <= 0:
            amount = refundable_balance(order)

    # 原支付渠道推断默认 channel
    channel = body.channel
    pay = db.scalar(
        select(Payment)
        .where(Payment.order_id == order.id, Payment.kind == PaymentKind.CHARGE.value)
        .order_by(Payment.id.desc())
    )
    if pay and pay.channel in (PaymentChannel.OFFLINE_CASH.value, PaymentChannel.OFFLINE_TRANSFER.value):
        if channel == PaymentChannel.WECHAT_ORIGINAL.value:
            channel = pay.channel

    create_refund(
        db,
        order,
        amount=Decimal(str(amount)),
        channel=channel,
        reason=body.reason,
        force=body.force,
        actor_staff_id=ctx.staff.id,
        can_force=ctx.can_force_payment_reconcile,
    )
    db.commit()
    db.refresh(order)
    return _order_out(db, order)
