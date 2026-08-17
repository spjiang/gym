"""微信支付回调、退款回调与会员 dry-run / 查单确认。"""

from __future__ import annotations

import json
from decimal import Decimal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import MemberContext, get_current_member
from app.core.errors import AppError
from app.systems.platform.models.commerce import Order, OrderStatus
from app.systems.platform.models.payment_settings import PaymentIntent, RefundIntent
from app.systems.platform.services.order_fulfill import fulfill_paid_order, mark_intent_succeeded
from app.systems.platform.services.payment_settings import resolve_payment_settings
from app.systems.platform.services.refunds import apply_refund_success
from app.systems.platform.services.wechat_pay import (
    parse_pay_notify_payload,
    parse_refund_notify_payload,
    query_wechat_order,
)

router = APIRouter(tags=["payments"])


class DryRunConfirmIn(BaseModel):
    out_trade_no: str | None = None


def _amount_matches(order: Order, amount_fen: int | None) -> bool:
    if amount_fen is None:
        return True
    expect = int((Decimal(str(order.amount)) * 100).quantize(Decimal("1")))
    return expect == int(amount_fen)


@router.post("/payments/wechat/notify")
async def wechat_pay_notify(request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return {"code": "FAIL", "message": "invalid json"}

    # 先用 payload 内 site 未知：用 intent 定位后再取配置
    # dry_run 明文带 out_trade_no；真实必须含 resource.ciphertext
    preliminary_out = payload.get("out_trade_no")
    resource = payload.get("resource") or {}
    if not preliminary_out and isinstance(resource, dict):
        preliminary_out = resource.get("out_trade_no")

    # 无 out_trade_no 时仍尝试按 dry_run/密文路径解析需要 cfg——先找任意？不行。
    # 真实通知解密前不知道 out_trade_no：用临时：若有 ciphertext，需要先拿到 site 的 key。
    # 简化：单场地系统——取 intent 前若只有密文，遍历不可行。
    # 实践：微信回调 URL 可带 site；本系统单 site，取第一笔 pending 配置：
    from app.systems.platform.models.org import Site

    site = db.scalar(select(Site).limit(1))
    if site is None:
        return {"code": "FAIL", "message": "no site"}
    cfg = resolve_payment_settings(db, site.id)

    try:
        parsed = parse_pay_notify_payload(cfg, payload)
    except AppError as exc:
        return {"code": "FAIL", "message": exc.message}

    out_trade_no = parsed.get("out_trade_no")
    if not out_trade_no:
        return {"code": "FAIL", "message": "missing out_trade_no"}
    if parsed.get("trade_state") and parsed["trade_state"] != "SUCCESS":
        return {"code": "SUCCESS", "message": "ignored non-success"}

    intent = db.scalar(select(PaymentIntent).where(PaymentIntent.out_trade_no == out_trade_no))
    if intent is None:
        return {"code": "FAIL", "message": "intent not found"}
    order = db.get(Order, intent.order_id)
    if order is None:
        return {"code": "FAIL", "message": "order not found"}

    cfg = resolve_payment_settings(db, order.site_id)
    if not _amount_matches(order, parsed.get("amount_fen")):
        # dry_run 明文可能无金额
        if not cfg.dry_run:
            return {"code": "FAIL", "message": "amount mismatch"}

    mark_intent_succeeded(db, intent, provider_ref=out_trade_no)
    try:
        fulfill_paid_order(db, order, provider_ref=out_trade_no)
    except AppError as exc:
        return {"code": "FAIL", "message": exc.message}
    db.commit()
    return {"code": "SUCCESS", "message": "成功"}


@router.post("/payments/wechat/refund-notify")
async def wechat_refund_notify(request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return {"code": "FAIL", "message": "invalid json"}

    from app.systems.platform.models.org import Site

    site = db.scalar(select(Site).limit(1))
    if site is None:
        return {"code": "FAIL", "message": "no site"}
    cfg = resolve_payment_settings(db, site.id)
    try:
        parsed = parse_refund_notify_payload(cfg, payload)
    except AppError as exc:
        return {"code": "FAIL", "message": exc.message}

    out_refund_no = parsed.get("out_refund_no")
    if not out_refund_no:
        return {"code": "FAIL", "message": "missing out_refund_no"}
    if parsed.get("refund_status") not in (None, "SUCCESS", "success"):
        return {"code": "SUCCESS", "message": "ignored"}

    intent = db.scalar(select(RefundIntent).where(RefundIntent.out_refund_no == out_refund_no))
    if intent is None:
        return {"code": "FAIL", "message": "refund intent not found"}
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
    order = db.get(Order, order_id)
    if order is None or order.member_id != mctx.member.id:
        raise AppError("not_found", "订单不存在", status_code=404)
    cfg = resolve_payment_settings(db, order.site_id)
    if cfg.mode not in {"wechat", "jdpay"} or not cfg.dry_run:
        raise AppError("forbidden", "仅微信 DRY_RUN 可确认干跑支付", status_code=403)

    q = select(PaymentIntent).where(PaymentIntent.order_id == order_id).order_by(PaymentIntent.id.desc())
    if body and body.out_trade_no:
        q = q.where(PaymentIntent.out_trade_no == body.out_trade_no)
    intent = db.scalar(q)
    if intent is None:
        raise AppError("not_found", "支付意图不存在，请先预下单", status_code=404)

    mark_intent_succeeded(db, intent, provider_ref=intent.provider_ref or intent.out_trade_no)
    fulfill_paid_order(db, order, provider_ref=intent.provider_ref)
    db.commit()
    db.refresh(order)
    return {
        "order_id": order.id,
        "status": order.status,
        "pickup_code": order.pickup_code,
    }


def sync_pay_query(db: Session, order: Order) -> dict:
    """查单并在已支付时履约。"""
    intent = db.scalar(
        select(PaymentIntent).where(PaymentIntent.order_id == order.id).order_by(PaymentIntent.id.desc())
    )
    if intent is None:
        return {"order_id": order.id, "status": order.status, "trade_state": None, "message": "无支付意图"}

    if order.status == OrderStatus.PAID.value:
        return {"order_id": order.id, "status": order.status, "trade_state": "SUCCESS", "out_trade_no": intent.out_trade_no}

    cfg = resolve_payment_settings(db, order.site_id)
    if cfg.dry_run:
        # dry_run 查单不自动成功，需 dry-run-confirm
        return {
            "order_id": order.id,
            "status": order.status,
            "trade_state": intent.status.upper() if intent.status == "succeeded" else "NOTPAY",
            "out_trade_no": intent.out_trade_no,
            "dry_run": True,
        }

    result = query_wechat_order(cfg, out_trade_no=intent.out_trade_no)
    if result.trade_state == "SUCCESS":
        if result.amount_fen is not None and not _amount_matches(order, result.amount_fen):
            raise AppError("amount_mismatch", "查单金额与订单不一致", status_code=400)
        mark_intent_succeeded(db, intent, provider_ref=intent.out_trade_no)
        fulfill_paid_order(db, order, provider_ref=intent.out_trade_no)
        db.commit()
        db.refresh(order)
    elif result.trade_state in ("CLOSED", "REVOKED", "PAYERROR"):
        intent.status = "closed"
        db.commit()
    return {
        "order_id": order.id,
        "status": order.status,
        "trade_state": result.trade_state,
        "out_trade_no": intent.out_trade_no,
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
