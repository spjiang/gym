"""支付入账编排：行锁、金额校验、幂等 ACK、关闭旧预下单。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.systems.platform.models.commerce import Order, OrderStatus
from app.systems.platform.models.payment_settings import PaymentIntent
from app.systems.platform.services.order_fulfill import fulfill_paid_order, mark_intent_succeeded
from app.systems.platform.services.order_lock import lock_order
from app.systems.platform.services.payment_settings import EffectivePaymentSettings, resolve_payment_settings
from app.systems.platform.services.wechat_pay import close_wechat_order


def new_out_trade_no(order_id: int) -> str:
    """微信 out_trade_no 最长 32 位；uuid 避免同一秒碰撞。"""
    return f"o{order_id}x{uuid.uuid4().hex[:16]}"


def new_out_refund_no(order_id: int) -> str:
    return f"r{order_id}x{uuid.uuid4().hex[:16]}"


def amount_fen_of(amount: Decimal | str | int) -> int:
    return int((Decimal(str(amount)) * 100).quantize(Decimal("1")))


def notify_amount_ok(
    *,
    order_amount: Decimal | str,
    intent_amount: Decimal | str,
    amount_fen: int | None,
    require_amount: bool,
) -> bool:
    if amount_fen is None:
        return not require_amount
    expect_order = amount_fen_of(order_amount)
    expect_intent = amount_fen_of(intent_amount)
    return int(amount_fen) == expect_order == expect_intent


@dataclass
class CaptureOutcome:
    order: Order
    fulfilled: bool
    skipped_reason: str | None = None


def lock_site_order(db: Session, order_id: int, *, site_id: int) -> Order:
    return lock_order(db, order_id, site_id=site_id)


def capture_wechat_success(
    db: Session,
    *,
    order: Order,
    intent: PaymentIntent,
    amount_fen: int | None,
    require_amount: bool,
    actor_staff_id: int | None = None,
) -> CaptureOutcome:
    """将微信 SUCCESS 落入本地；调用方须已对订单加行锁。

    已支付：幂等，不重复流水。已取消：不履约，但 intent 记成功便于对账。
    """
    if not notify_amount_ok(
        order_amount=order.amount,
        intent_amount=intent.amount,
        amount_fen=amount_fen,
        require_amount=require_amount,
    ):
        raise AppError("amount_mismatch", "支付金额与订单/支付意图不一致", status_code=400)

    if order.status == OrderStatus.PAID.value:
        was_new = intent.status != "succeeded"
        mark_intent_succeeded(db, intent, provider_ref=intent.out_trade_no)
        return CaptureOutcome(
            order=order,
            fulfilled=False,
            skipped_reason="duplicate_trade" if was_new else "already_paid",
        )

    if order.status == OrderStatus.CANCELLED.value:
        mark_intent_succeeded(db, intent, provider_ref=intent.out_trade_no)
        return CaptureOutcome(order=order, fulfilled=False, skipped_reason="cancelled")

    if order.status == OrderStatus.REFUNDED.value:
        mark_intent_succeeded(db, intent, provider_ref=intent.out_trade_no)
        return CaptureOutcome(order=order, fulfilled=False, skipped_reason="refunded")

    mark_intent_succeeded(db, intent, provider_ref=intent.out_trade_no)
    fulfill_paid_order(db, order, provider_ref=intent.out_trade_no, actor_staff_id=actor_staff_id)
    return CaptureOutcome(order=order, fulfilled=True)


def close_open_intents(
    db: Session,
    order: Order,
    cfg: EffectivePaymentSettings,
) -> PaymentIntent | None:
    """关闭同订单未完成预下单。若微信返回已支付，返回该 intent 供立即入账。"""
    rows = list(
        db.scalars(
            select(PaymentIntent).where(
                PaymentIntent.order_id == order.id,
                PaymentIntent.status == "created",
            )
        ).all()
    )
    for old in rows:
        paid = close_wechat_order(cfg, out_trade_no=old.out_trade_no)
        if paid:
            return old
        old.status = "closed"
    return None


def close_open_intents_for_order(db: Session, order: Order) -> PaymentIntent | None:
    cfg = resolve_payment_settings(db, order.site_id)
    return close_open_intents(db, order, cfg)
