"""微信支付回调、退款回调与会员 dry-run / 查单确认。"""

from __future__ import annotations

import json
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import MemberContext, get_current_member
from app.core.errors import AppError
from app.systems.platform.models.commerce import Order, OrderStatus
from app.systems.platform.models.org import Site
from app.systems.platform.models.payment_settings import PaymentIntent, RefundIntent
from app.systems.platform.services.error_events import record_error, record_notify_failure
from app.systems.platform.services.order_lock import lock_order
from app.systems.platform.services.payment_capture import capture_wechat_success
from app.systems.platform.services.payment_settings import (
    is_wechat_payment_mode,
    resolve_payment_settings,
)
from app.systems.platform.services.refunds import apply_refund_success
from app.systems.platform.services.wechat_pay import (
    parse_pay_notify_payload,
    parse_refund_notify_payload,
    query_wechat_order,
    verify_wechat_notify_signature,
)

router = APIRouter(tags=["payments"])


class DryRunConfirmIn(BaseModel):
    out_trade_no: str | None = None


def _first_site_cfg(db: Session):
    site = db.scalar(select(Site).limit(1))
    if site is None:
        return None, None
    return site, resolve_payment_settings(db, site.id)


@router.post("/payments/wechat/notify")
async def wechat_pay_notify(request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return record_notify_failure(request, "invalid json")

    site, cfg = _first_site_cfg(db)
    if site is None or cfg is None:
        return record_notify_failure(request, "no site")

    try:
        verify_wechat_notify_signature(cfg, request.headers, raw)
        parsed = parse_pay_notify_payload(cfg, payload)
    except AppError as exc:
        return record_notify_failure(request, exc.message, extra={"error_code": exc.code})

    out_trade_no = parsed.get("out_trade_no")
    if not out_trade_no:
        return record_notify_failure(request, "missing out_trade_no")
    if parsed.get("trade_state") and parsed["trade_state"] != "SUCCESS":
        return {"code": "SUCCESS", "message": "ignored non-success"}

    intent = db.scalar(select(PaymentIntent).where(PaymentIntent.out_trade_no == out_trade_no))
    if intent is None:
        return record_notify_failure(request, "intent not found", extra={"out_trade_no": out_trade_no})

    try:
        order = lock_order(db, intent.order_id, site_id=intent.site_id)
    except AppError as exc:
        return record_notify_failure(request, exc.message, extra={"error_code": exc.code, "out_trade_no": out_trade_no})

    cfg = resolve_payment_settings(db, order.site_id)
    amount_fen = parsed.get("amount_fen")
    try:
        outcome = capture_wechat_success(
            db,
            order=order,
            intent=intent,
            amount_fen=amount_fen,
            require_amount=not cfg.dry_run,
        )
    except AppError as exc:
        return record_notify_failure(
            request,
            exc.message,
            extra={"error_code": exc.code, "out_trade_no": out_trade_no, "order_id": order.id},
        )
    if outcome.skipped_reason in ("cancelled", "refunded", "duplicate_trade"):
        record_error(
            error_code="wechat_notify_invalid",
            message=f"订单已{outcome.skipped_reason}但仍收到支付成功",
            status_code=200,
            request=request,
            extra={"out_trade_no": out_trade_no, "order_id": order.id, "reason": outcome.skipped_reason},
        )
    db.commit()
    return {"code": "SUCCESS", "message": "成功"}


@router.post("/payments/wechat/refund-notify")
async def wechat_refund_notify(request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return record_notify_failure(request, "invalid json")

    site, cfg = _first_site_cfg(db)
    if site is None or cfg is None:
        return record_notify_failure(request, "no site")
    try:
        verify_wechat_notify_signature(cfg, request.headers, raw)
        parsed = parse_refund_notify_payload(cfg, payload)
    except AppError as exc:
        return record_notify_failure(request, exc.message, extra={"error_code": exc.code})

    out_refund_no = parsed.get("out_refund_no")
    if not out_refund_no:
        return record_notify_failure(request, "missing out_refund_no")
    if parsed.get("refund_status") not in (None, "SUCCESS", "success"):
        return {"code": "SUCCESS", "message": "ignored"}

    intent = db.scalar(select(RefundIntent).where(RefundIntent.out_refund_no == out_refund_no))
    if intent is None:
        return record_notify_failure(request, "refund intent not found", extra={"out_refund_no": out_refund_no})
    lock_order(db, intent.order_id, site_id=intent.site_id)
    apply_refund_success(db, intent)
    db.commit()
    return {"code": "SUCCESS", "message": "成功"}


@router.post("/member/orders/{order_id}/pay/dry-run-confirm")
def member_dry_run_confirm(
    order_id: int,
    body: DryRunConfirmIn | None = None,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    order = lock_order(db, order_id, site_id=mctx.site_id)
    if order.member_id != mctx.member.id:
        raise AppError("not_found", "订单不存在", status_code=404)
    cfg = resolve_payment_settings(db, order.site_id)
    if not is_wechat_payment_mode(cfg.mode) or not cfg.dry_run:
        raise AppError("forbidden", "仅微信支付 DRY_RUN 可确认干跑支付", status_code=403)

    q = select(PaymentIntent).where(PaymentIntent.order_id == order_id).order_by(PaymentIntent.id.desc())
    if body and body.out_trade_no:
        q = q.where(PaymentIntent.out_trade_no == body.out_trade_no)
    intent = db.scalar(q)
    if intent is None:
        raise AppError("not_found", "支付意图不存在，请先预下单", status_code=404)

    capture_wechat_success(
        db,
        order=order,
        intent=intent,
        amount_fen=None,
        require_amount=False,
    )
    db.commit()
    db.refresh(order)
    return {
        "order_id": order.id,
        "status": order.status,
        "pickup_code": order.pickup_code,
    }


def sync_pay_query(db: Session, order: Order) -> dict:
    """查单并在已支付时履约；扫描该订单全部 intent，避免只看最新一笔漏单。"""
    order = lock_order(db, order.id, site_id=order.site_id)
    intents = list(
        db.scalars(select(PaymentIntent).where(PaymentIntent.order_id == order.id).order_by(PaymentIntent.id)).all()
    )
    if not intents:
        return {"order_id": order.id, "status": order.status, "trade_state": None, "message": "无支付意图"}

    if order.status == OrderStatus.PAID.value:
        latest = intents[-1]
        return {
            "order_id": order.id,
            "status": order.status,
            "trade_state": "SUCCESS",
            "out_trade_no": latest.out_trade_no,
        }

    cfg = resolve_payment_settings(db, order.site_id)
    if cfg.dry_run:
        latest = intents[-1]
        return {
            "order_id": order.id,
            "status": order.status,
            "trade_state": latest.status.upper() if latest.status == "succeeded" else "NOTPAY",
            "out_trade_no": latest.out_trade_no,
            "dry_run": True,
        }

    paid_trade: str | None = None
    last_state = "NOTPAY"
    for intent in intents:
        if intent.status == "failed":
            continue
        result = query_wechat_order(cfg, out_trade_no=intent.out_trade_no)
        last_state = result.trade_state
        if result.trade_state == "SUCCESS":
            capture_wechat_success(
                db,
                order=order,
                intent=intent,
                amount_fen=result.amount_fen,
                require_amount=True,
            )
            paid_trade = intent.out_trade_no
            db.refresh(order)
        elif result.trade_state in ("CLOSED", "REVOKED", "PAYERROR") and intent.status == "created":
            intent.status = "closed"
    db.commit()
    db.refresh(order)
    return {
        "order_id": order.id,
        "status": order.status,
        "trade_state": "SUCCESS" if paid_trade else last_state,
        "out_trade_no": paid_trade or intents[-1].out_trade_no,
    }


@router.post("/member/orders/{order_id}/pay/query")
def member_pay_query(
    order_id: int,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    order = db.get(Order, order_id)
    if order is None or order.member_id != mctx.member.id:
        raise AppError("not_found", "订单不存在", status_code=404)
    return sync_pay_query(db, order)
