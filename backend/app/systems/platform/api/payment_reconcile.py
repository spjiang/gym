"""支付对账 / 补单台。"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import RequestContext, get_current_context
from app.core.errors import AppError
from app.systems.platform.api.payment_notify import sync_pay_query
from app.systems.platform.models.commerce import Order, OrderStatus, Payment, PaymentKind
from app.systems.platform.models.member import Member
from app.systems.platform.models.payment_settings import PaymentIntent, RefundIntent
from app.systems.platform.services.audit import write_audit
from app.systems.platform.services.order_fulfill import fulfill_paid_order, mark_intent_succeeded
from app.systems.platform.services.refunds import apply_refund_success, refresh_processing_refunds

router = APIRouter(prefix="/site/payment-reconcile", tags=["payment-reconcile"])

STALE_MINUTES = 15


def _order_brief(db: Session, order: Order | None) -> dict:
    """给对账列表补上订单号、标题和会员，避免只显示内部编号。"""
    if order is None:
        return {
            "order_no": None,
            "title": None,
            "member_name": None,
            "member_phone": None,
            "order_status": None,
            "amount": None,
        }
    member = db.get(Member, order.member_id) if order.member_id else None
    return {
        "order_no": order.order_no,
        "title": order.title,
        "member_name": member.name if member is not None else None,
        "member_phone": member.phone if member is not None else None,
        "order_status": order.status,
        "amount": str(order.amount),
    }


def _refund_issue(status: str, error_message: str | None) -> str:
    if status == "processing":
        return "退款已提交微信，系统仍停在处理中。若客人已收到退款，可确认为已退款。"
    if status == "failed":
        return error_message or "退款失败，钱可能还在原账户。"
    return "退款没有完成。"


class ReconcileActionIn(BaseModel):
    order_id: int | None = None
    intent_id: int | None = None
    refund_intent_id: int | None = None
    reason: str | None = None


@router.get("/items")
def list_reconcile_items(
    kind: str = Query("pay_stale"),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("payment:reconcile", "*")
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=STALE_MINUTES)
    items: list[dict] = []

    if kind == "pay_stale":
        rows = db.scalars(
            select(PaymentIntent).where(
                PaymentIntent.site_id == ctx.site_id,
                PaymentIntent.status == "created",
                PaymentIntent.created_at < cutoff,
            )
        ).all()
        for it in rows:
            order = db.get(Order, it.order_id)
            if order and order.status == OrderStatus.PENDING.value:
                items.append(
                    {
                        "kind": "pay_stale",
                        "intent_id": it.id,
                        "order_id": order.id,
                        "out_trade_no": it.out_trade_no,
                        "wechat_transaction_id": it.wechat_transaction_id,
                        "amount": str(it.amount),
                        "created_at": it.created_at,
                        "issue": "客人已发起支付，超过 15 分钟仍未到账。",
                        **_order_brief(db, order),
                        "amount": str(it.amount),
                    }
                )
    elif kind == "pay_mismatch":
        succeeded = db.scalars(
            select(PaymentIntent).where(
                PaymentIntent.site_id == ctx.site_id,
                PaymentIntent.status == "succeeded",
            )
        ).all()
        for it in succeeded:
            order = db.get(Order, it.order_id)
            if order and order.status != OrderStatus.PAID.value and order.status != OrderStatus.REFUNDED.value:
                items.append(
                    {
                        "kind": "pay_mismatch",
                        "intent_id": it.id,
                        "order_id": order.id,
                        "status": order.status,
                        "out_trade_no": it.out_trade_no,
                        "wechat_transaction_id": it.wechat_transaction_id,
                        "created_at": it.succeeded_at or it.created_at,
                        "issue": "微信已收款，订单还没记成已收款。",
                        **_order_brief(db, order),
                        "amount": str(it.amount),
                    }
                )
        paid_orders = db.scalars(
            select(Order).where(Order.site_id == ctx.site_id, Order.status == OrderStatus.PAID.value)
        ).all()
        for order in paid_orders:
            has_charge = db.scalar(
                select(Payment.id).where(
                    Payment.order_id == order.id,
                    Payment.kind == PaymentKind.CHARGE.value,
                )
            )
            if has_charge is None:
                items.append(
                    {
                        "kind": "pay_mismatch",
                        "order_id": order.id,
                        "status": order.status,
                        "note": "missing_charge",
                        "created_at": order.created_at,
                        "issue": "订单显示已收款，但没有收款记录。",
                        **_order_brief(db, order),
                    }
                )
            succeeded_n = db.scalar(
                select(func.count())
                .select_from(PaymentIntent)
                .where(PaymentIntent.order_id == order.id, PaymentIntent.status == "succeeded")
            ) or 0
            if int(succeeded_n) > 1:
                items.append(
                    {
                        "kind": "pay_mismatch",
                        "order_id": order.id,
                        "status": order.status,
                        "note": "duplicate_succeeded_intents",
                        "created_at": order.created_at,
                        "issue": "同一订单有多笔成功支付，需要核对是否重复收款。",
                        **_order_brief(db, order),
                    }
                )
    elif kind == "refund_abnormal":
        rows = db.scalars(
            select(RefundIntent).where(
                RefundIntent.site_id == ctx.site_id,
                RefundIntent.status.in_(("processing", "failed", "created")),
            )
        ).all()
        if refresh_processing_refunds(db, list(rows)):
            db.commit()
        for it in rows:
            if it.status not in ("processing", "failed", "created"):
                continue
            if it.status == "created" and it.succeeded_at is None:
                # 线下应已成功；created 残留视为异常
                pass
            order = db.get(Order, it.order_id)
            items.append(
                {
                    "kind": "refund_abnormal",
                    "refund_intent_id": it.id,
                    "order_id": it.order_id,
                    "status": it.status,
                    "refund_status": it.status,
                    "amount": str(it.amount),
                    "out_refund_no": it.out_refund_no,
                    "error_message": it.error_message,
                    "created_at": it.created_at,
                    "issue": _refund_issue(it.status, it.error_message),
                    **_order_brief(db, order),
                    "amount": str(it.amount),
                }
            )
    else:
        raise AppError("validation_error", "未知 kind", status_code=422)
    return {"items": items, "kind": kind}


@router.post("/actions/query-pay")
def action_query_pay(
    body: ReconcileActionIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("payment:reconcile", "*")
    order = db.get(Order, body.order_id)
    if order is None or order.site_id != ctx.site_id:
        raise AppError("not_found", "订单不存在", status_code=404)
    if not ctx.is_site_wide:
        ctx.assert_merchant_access(order.merchant_id)
    return sync_pay_query(db, order)


@router.post("/actions/close-intent")
def action_close_intent(
    body: ReconcileActionIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("payment:reconcile", "*")
    intent = db.get(PaymentIntent, body.intent_id)
    if intent is None or intent.site_id != ctx.site_id:
        raise AppError("not_found", "支付意图不存在", status_code=404)
    intent.status = "closed"
    write_audit(
        db,
        action="reconcile.close_intent",
        target_type="payment_intent",
        target_id=intent.id,
        summary=body.reason or "关闭支付意图",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
    )
    db.commit()
    return {"ok": True, "intent_id": intent.id, "status": intent.status}


@router.post("/actions/force-fulfill")
def action_force_fulfill(
    body: ReconcileActionIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    if not ctx.can_force_payment_reconcile:
        raise AppError("forbidden", "仅超管或财务对账可强制补履约", status_code=403)
    if body.order_id is None:
        raise AppError("validation_error", "缺少 order_id", status_code=422)
    from app.systems.platform.services.order_lock import lock_order

    order = lock_order(db, body.order_id, site_id=ctx.site_id)
    intent = db.scalar(
        select(PaymentIntent).where(PaymentIntent.order_id == order.id).order_by(PaymentIntent.id.desc())
    )
    if intent:
        mark_intent_succeeded(db, intent, provider_ref=intent.out_trade_no)
    fulfill_paid_order(db, order, provider_ref="force-fulfill", actor_staff_id=ctx.staff.id)
    write_audit(
        db,
        action="reconcile.force_fulfill",
        target_type="order",
        target_id=order.id,
        summary=body.reason or "强制补履约",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=order.merchant_id,
    )
    db.commit()
    return {"ok": True, "order_id": order.id, "status": order.status}


@router.post("/actions/force-refund-success")
def action_force_refund_success(
    body: ReconcileActionIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    if not ctx.can_force_payment_reconcile:
        raise AppError("forbidden", "仅超管或财务对账可强制补退结果", status_code=403)
    intent = db.get(RefundIntent, body.refund_intent_id)
    if intent is None or intent.site_id != ctx.site_id:
        raise AppError("not_found", "退款意图不存在", status_code=404)
    apply_refund_success(db, intent, actor_staff_id=ctx.staff.id)
    write_audit(
        db,
        action="reconcile.force_refund_success",
        target_type="refund_intent",
        target_id=intent.id,
        summary=body.reason or "强制补退结果",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
    )
    db.commit()
    return {"ok": True, "refund_intent_id": intent.id, "status": intent.status}


@router.post("/actions/mark-offline-refunded")
def action_mark_offline_refunded(
    body: ReconcileActionIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("payment:reconcile", "*")
    from app.systems.platform.models.commerce import PaymentChannel

    intent = db.get(RefundIntent, body.refund_intent_id)
    if intent is None or intent.site_id != ctx.site_id:
        raise AppError("not_found", "退款意图不存在", status_code=404)
    if intent.channel not in {
        PaymentChannel.OFFLINE_CASH.value,
        PaymentChannel.OFFLINE_TRANSFER.value,
    }:
        raise AppError("validation_error", "仅线下退款意图可标记线下已退", status_code=400)
    if intent.status in ("succeeded", "processing"):
        raise AppError("invalid_state", "该退款意图已在处理或已完成", status_code=400)
    apply_refund_success(db, intent, actor_staff_id=ctx.staff.id)
    db.commit()
    return {"ok": True, "refund_intent_id": intent.id, "status": intent.status}
