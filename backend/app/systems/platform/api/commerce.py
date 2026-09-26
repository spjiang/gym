"""订单与支付骨架。"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import RequestContext, get_current_context
from app.core.domain.subsystems import assert_order_type_allowed
from app.core.errors import AppError
from app.core.schemas.common import (
    MemberBrief,
    OfflinePayIn,
    OnlinePayIn,
    OrderBuyerOut,
    OrderCreateIn,
    OrderDetailOut,
    OrderOut,
    OrderPaymentLineOut,
    OrderStoreOut,
)
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
from app.systems.platform.models.identity import StaffUser
from app.systems.platform.models.payment_settings import PaymentIntent, RefundIntent
from app.systems.platform.models.member import Member
from app.systems.platform.models.org import Merchant
from app.systems.platform.services.audit import write_audit
from app.systems.platform.services.notifications import write_notification
from app.systems.platform.services.order_pricing import price_order
from app.systems.platform.services.payments import get_online_provider

router = APIRouter(prefix="/orders", tags=["commerce"])
_SHANGHAI = ZoneInfo("Asia/Shanghai")


def _shanghai_bounds(day_from: date, day_to: date) -> tuple[datetime, datetime]:
    """按北京时间把日期区间收成 [开始日 0 点, 结束日次日 0 点)。"""
    if day_to < day_from:
        raise AppError("invalid_range", "结束日期不能早于开始日期", status_code=400)
    start = datetime.combine(day_from, time.min, tzinfo=_SHANGHAI)
    end = datetime.combine(day_to + timedelta(days=1), time.min, tzinfo=_SHANGHAI)
    return start, end


def _paid_at_expr():
    """列表筛选用的支付时间：微信成功时间优先，否则取最早一笔收款流水。"""
    succeeded_at = (
        select(PaymentIntent.succeeded_at)
        .where(
            PaymentIntent.order_id == Order.id,
            PaymentIntent.status == "succeeded",
            PaymentIntent.succeeded_at.is_not(None),
        )
        .order_by(PaymentIntent.id.desc())
        .limit(1)
        .correlate(Order)
        .scalar_subquery()
    )
    charge_at = (
        select(func.min(Payment.created_at))
        .where(Payment.order_id == Order.id, Payment.kind == PaymentKind.CHARGE.value)
        .correlate(Order)
        .scalar_subquery()
    )
    return func.coalesce(succeeded_at, charge_at)


def _charge_paid_at(db: Session, order_ids: list[int]) -> dict[int, datetime]:
    if not order_ids:
        return {}
    rows = db.execute(
        select(Payment.order_id, func.min(Payment.created_at))
        .where(Payment.order_id.in_(order_ids), Payment.kind == PaymentKind.CHARGE.value)
        .group_by(Payment.order_id)
    ).all()
    return {order_id: paid_at for order_id, paid_at in rows}


def _trade_by_order(db: Session, order_ids: list[int]) -> dict[int, PaymentIntent]:
    """每个订单取最近一笔成功支付；没有成功记录时取最新一笔意图。"""
    if not order_ids:
        return {}
    rows = list(
        db.scalars(
            select(PaymentIntent).where(PaymentIntent.order_id.in_(order_ids)).order_by(PaymentIntent.id)
        ).all()
    )
    grouped: dict[int, list[PaymentIntent]] = {}
    for row in rows:
        grouped.setdefault(row.order_id, []).append(row)
    picked: dict[int, PaymentIntent] = {}
    for order_id, intents in grouped.items():
        succeeded = [it for it in intents if it.status == "succeeded"]
        picked[order_id] = (succeeded or intents)[-1]
    return picked


def _order_out(
    db: Session,
    order: Order,
    trade: PaymentIntent | None = None,
    charge_paid_at: datetime | None = None,
) -> OrderOut:
    member_brief = None
    if order.member_id is not None:
        m = db.get(Member, order.member_id)
        if m is not None:
            member_brief = MemberBrief(id=m.id, name=m.name, phone=m.phone)
    merchant = db.get(Merchant, order.merchant_id)
    return OrderOut(
        id=order.id,
        order_no=order.order_no,
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
        merchant_name=merchant.name if merchant is not None else None,
        member=member_brief,
        out_trade_no=trade.out_trade_no if trade is not None else None,
        wechat_transaction_id=trade.wechat_transaction_id if trade is not None else None,
        paid_at=(
            trade.succeeded_at
            if trade is not None and trade.status == "succeeded" and trade.succeeded_at is not None
            else charge_paid_at
        ),
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
    created_from: date | None = None,
    created_to: date | None = None,
    paid_from: date | None = None,
    paid_to: date | None = None,
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
        trade_order_ids = select(PaymentIntent.order_id).where(
            PaymentIntent.site_id == ctx.site_id,
            or_(
                PaymentIntent.out_trade_no.ilike(like),
                PaymentIntent.wechat_transaction_id.ilike(like),
            ),
        )
        id_match = []
        if keyword.isdigit() and int(keyword) <= 2_147_483_647:
            id_match.append(Order.id == int(keyword))
        filters.append(
            or_(
                *id_match,
                Order.order_no.ilike(like),
                Order.title.ilike(like),
                Order.member_id.in_(member_ids),
                Order.id.in_(trade_order_ids),
            )
        )
    if created_from is not None or created_to is not None:
        start, end = _shanghai_bounds(created_from or created_to, created_to or created_from)
        filters.append(Order.created_at >= start)
        filters.append(Order.created_at < end)
    if paid_from is not None or paid_to is not None:
        start, end = _shanghai_bounds(paid_from or paid_to, paid_to or paid_from)
        paid_at = _paid_at_expr()
        filters.append(paid_at >= start)
        filters.append(paid_at < end)

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
    order_ids = [o.id for o in rows]
    trades = _trade_by_order(db, order_ids)
    charges = _charge_paid_at(db, order_ids)
    return PageOut(
        items=[_order_out(db, o, trades.get(o.id), charges.get(o.id)) for o in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


def _order_detail(db: Session, order: Order) -> OrderDetailOut:
    trade = _trade_by_order(db, [order.id]).get(order.id)
    base = _order_out(db, order, trade, _charge_paid_at(db, [order.id]).get(order.id))
    merchant = db.get(Merchant, order.merchant_id)
    store = None
    if merchant is not None:
        store = OrderStoreOut(
            id=merchant.id,
            name=merchant.name,
            status=merchant.status,
            legal_name=merchant.legal_name,
            business_address=merchant.business_address,
            contact_phone=merchant.contact_phone,
            business_hours=merchant.business_hours,
            tagline=merchant.tagline,
        )
    buyer = None
    if order.member_id is not None:
        member = db.get(Member, order.member_id)
        if member is not None:
            buyer = OrderBuyerOut(
                id=member.id,
                name=member.name,
                phone=member.phone,
                gender=member.gender,
                email=member.email,
                remark=member.remark,
                created_at=member.created_at,
            )
    payments = list(
        db.scalars(select(Payment).where(Payment.order_id == order.id).order_by(Payment.id)).all()
    )
    return OrderDetailOut(
        **base.model_dump(),
        store=store,
        buyer=buyer,
        payments=[
            OrderPaymentLineOut(
                id=pay.id,
                kind=pay.kind,
                channel=pay.channel,
                amount=pay.amount,
                note=pay.note,
                created_at=pay.created_at,
            )
            for pay in payments
        ],
        wechat_payload=trade.wechat_payload if trade is not None else None,
    )


class RefundRecordOut(BaseModel):
    id: int
    order_id: int
    order_no: str
    title: str
    merchant_id: int
    merchant_name: str | None = None
    member_name: str | None = None
    member_phone: str | None = None
    amount: Decimal
    channel: str
    status: str
    reason: str | None = None
    out_refund_no: str
    provider_ref: str | None = None
    actor_name: str | None = None
    created_at: datetime
    succeeded_at: datetime | None = None


@router.get("/refunds", response_model=PageOut[RefundRecordOut])
def list_refunds(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    merchant_id: int | None = None,
    status: str | None = None,
    q: str | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """退款记录：按退款单列出，含处理中与已到账。"""
    ctx.require_permission("order:read", "order:write")
    filters = [RefundIntent.site_id == ctx.site_id]
    if not ctx.is_site_wide:
        filters.append(Order.merchant_id == ctx.resolve_merchant_id())
    elif merchant_id is not None:
        filters.append(Order.merchant_id == merchant_id)
    if status:
        filters.append(RefundIntent.status == status)
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        filters.append(
            or_(
                Order.order_no.ilike(like),
                Order.title.ilike(like),
                RefundIntent.out_refund_no.ilike(like),
                RefundIntent.provider_ref.ilike(like),
                Member.name.ilike(like),
                Member.phone.ilike(like),
            )
        )
    if created_from is not None or created_to is not None:
        start, end = _shanghai_bounds(created_from or created_to, created_to or created_from)
        filters.append(RefundIntent.created_at >= start)
        filters.append(RefundIntent.created_at < end)

    base = (
        select(RefundIntent, Order, Merchant, Member, StaffUser)
        .join(Order, Order.id == RefundIntent.order_id)
        .outerjoin(Merchant, Merchant.id == Order.merchant_id)
        .outerjoin(Member, Member.id == Order.member_id)
        .outerjoin(StaffUser, StaffUser.id == RefundIntent.actor_staff_id)
        .where(*filters)
    )
    total = db.scalar(select(func.count()).select_from(base.order_by(None).subquery())) or 0
    rows = db.execute(
        base.order_by(RefundIntent.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [
        RefundRecordOut(
            id=intent.id,
            order_id=order.id,
            order_no=order.order_no,
            title=order.title,
            merchant_id=order.merchant_id,
            merchant_name=merchant.name if merchant is not None else None,
            member_name=member.name if member is not None else None,
            member_phone=member.phone if member is not None else None,
            amount=intent.amount,
            channel=intent.channel,
            status=intent.status,
            reason=intent.reason,
            out_refund_no=intent.out_refund_no,
            provider_ref=intent.provider_ref,
            actor_name=staff.display_name if staff is not None else None,
            created_at=intent.created_at,
            succeeded_at=intent.succeeded_at,
        )
        for intent, order, merchant, member, staff in rows
    ]
    return PageOut(items=items, total=total, page=page, page_size=page_size)


@router.get("/{order_id}", response_model=OrderDetailOut)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """订单详情：订单、支付、店铺与下单用户。"""
    ctx.require_permission("order:read", "order:write", "promoter:read", "promoter:manage")
    order = db.get(Order, order_id)
    if order is None or order.site_id != ctx.site_id:
        raise AppError("not_found", "订单不存在", status_code=404)
    ctx.assert_merchant_access(order.merchant_id)
    return _order_detail(db, order)


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
    from app.systems.platform.models.payment_settings import PaymentIntent
    from app.systems.platform.services.order_lock import lock_order
    from app.systems.platform.services.order_fulfill import fulfill_paid_order, mark_intent_succeeded
    from app.systems.platform.services.payment_capture import new_out_trade_no

    order = lock_order(db, order_id, site_id=ctx.site_id)
    ctx.assert_merchant_access(order.merchant_id)
    if order.status != OrderStatus.PENDING.value:
        raise AppError("invalid_state", "仅待支付订单可发起线上支付", status_code=400)
    if order.seller_staff_id is None:
        order.seller_staff_id = ctx.staff.id

    out_trade_no = new_out_trade_no(order.id)
    result = get_online_provider(db, ctx.site_id).create_payment(
        order_id=order.id,
        amount=str(order.amount),
        title=order.title,
        out_trade_no=out_trade_no,
        pay_scene=getattr(body, "pay_scene", None) or "miniprogram",
        staff_capture=True,
    )
    if not result.ok:
        raise AppError("online_pay_failed", result.message, status_code=400)

    intent = PaymentIntent(
        site_id=order.site_id,
        order_id=order.id,
        out_trade_no=out_trade_no,
        scene=getattr(body, "pay_scene", None) or "miniprogram",
        status="created",
        amount=order.amount,
        provider_ref=result.provider_ref,
    )
    db.add(intent)

    if result.immediate_capture:
        fulfill_paid_order(db, order, provider_ref=result.provider_ref, actor_staff_id=ctx.staff.id)
        mark_intent_succeeded(db, intent, provider_ref=result.provider_ref)
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
