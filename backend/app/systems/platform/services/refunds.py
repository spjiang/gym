"""退款预览、发起与成功落账（含会籍/课包权益终止）。"""

from __future__ import annotations

import math
import time
from datetime import datetime, timezone
from decimal import ROUND_DOWN, Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.systems.gym.models.course import PtOrderLink, PtPackage, PtPackageStatus
from app.systems.gym.models.membership import (
    Membership,
    MembershipOrderLink,
    MembershipProduct,
    MembershipStatus,
    ProductType,
)
from app.systems.gym.models.activity import ActivityRegistration, RegistrationStatus
from app.systems.gym.services.commission import scale_records_for_partial_refund, void_records_for_order
from app.systems.gym.services.coupon import restore_coupon_for_order
from app.systems.gym.services.fulfillment import void_membership
from app.systems.gym.services.retail_fulfillment import restock_retail_order
from app.systems.platform.models.access import AccessEvent
from app.systems.platform.models.commerce import Order, OrderStatus, Payment, PaymentChannel, PaymentKind
from app.systems.platform.models.payment_settings import PaymentIntent, RefundIntent
from app.systems.platform.services.audit import write_audit
from app.systems.platform.services.payment_settings import resolve_payment_settings
from app.systems.platform.services.rebate import reverse_order_rebate
from app.systems.platform.services.wechat_pay import create_wechat_refund


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _money(value: Decimal | str | float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)


def refundable_balance(order: Order) -> Decimal:
    refunded = _money(getattr(order, "refunded_amount", None) or 0)
    return _money(order.amount) - refunded


def _ensure_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _has_access_after(db: Session, *, member_id: int, since: datetime | None) -> bool:
    q = select(AccessEvent.id).where(
        AccessEvent.member_id == member_id,
        AccessEvent.allowed.is_(True),
    )
    if since is not None:
        q = q.where(AccessEvent.created_at >= since)
    return db.scalar(q.limit(1)) is not None


def preview_refund(db: Session, order: Order) -> dict[str, Any]:
    balance = refundable_balance(order)
    base = {
        "order_id": order.id,
        "order_type": order.order_type,
        "order_amount": str(_money(order.amount)),
        "refunded_amount": str(_money(getattr(order, "refunded_amount", None) or 0)),
        "refundable_balance": str(balance),
        "force_required_if_amount_differs": order.order_type in ("membership", "pt_package"),
    }
    if order.order_type == "membership":
        return {**base, **_preview_membership(db, order, balance)}
    if order.order_type == "pt_package":
        return {**base, **_preview_pt(db, order, balance)}
    # 零售/餐饮：建议退可退余额（默认全额剩余）
    return {
        **base,
        "suggested_amount": str(balance if balance > 0 else Decimal("0")),
        "unused": True,
        "basis": "order_balance",
        "detail": {},
        "entitlement_action": "none",
    }


def _preview_membership(db: Session, order: Order, balance: Decimal) -> dict[str, Any]:
    link = db.scalar(select(MembershipOrderLink).where(MembershipOrderLink.order_id == order.id))
    if link is None or link.fulfilled_membership_id is None:
        return {
            "suggested_amount": "0.00",
            "unused": False,
            "basis": "missing_fulfillment",
            "detail": {},
            "entitlement_action": "void_remaining",
        }
    m = db.get(Membership, link.fulfilled_membership_id)
    product = db.get(MembershipProduct, link.product_id)
    if m is None or product is None or m.status == MembershipStatus.VOID.value:
        return {
            "suggested_amount": "0.00",
            "unused": False,
            "basis": "void_or_missing",
            "detail": {},
            "entitlement_action": "void_remaining",
        }

    order_amt = _money(order.amount)
    unused = False
    suggested = Decimal("0.00")
    basis = product.product_type
    detail: dict[str, Any] = {"membership_id": m.id}

    if product.product_type == ProductType.TERM.value:
        total_days = max(int(product.duration_days or 0), 1)
        ends = _ensure_aware(m.ends_at)
        now = _now()
        remaining_days = 0
        if ends and ends > now:
            remaining_days = min(total_days, max(0, math.ceil((ends - now).total_seconds() / 86400)))
        unused = not _has_access_after(db, member_id=m.member_id, since=_ensure_aware(m.starts_at))
        suggested = order_amt if unused else _money(order_amt * Decimal(remaining_days) / Decimal(total_days))
        basis = "term_remaining_days"
        detail.update({"total_days": total_days, "remaining_days": remaining_days})
    elif product.product_type == ProductType.COUNT.value:
        original = int(product.session_count or 0) or 1
        remaining = int(m.remaining_sessions or 0)
        unused = remaining >= original
        suggested = order_amt if unused else _money(order_amt * Decimal(remaining) / Decimal(original))
        basis = "count_remaining_sessions"
        detail.update({"original_sessions": original, "remaining_sessions": remaining})
    else:
        # 储值
        stored = _money(product.stored_value or 0)
        bal = _money(m.balance or 0)
        unused = bal >= stored and stored > 0
        suggested = order_amt if unused else min(balance, bal)
        basis = "stored_balance"
        detail.update({"stored_value": str(stored), "balance": str(bal)})

    if remaining_is_zero_membership(m, product):
        suggested = Decimal("0.00")
    suggested = min(suggested, balance)
    return {
        "suggested_amount": str(suggested),
        "unused": unused,
        "basis": basis,
        "detail": detail,
        "entitlement_action": "void_remaining",
    }


def remaining_is_zero_membership(m: Membership, product: MembershipProduct) -> bool:
    if m.status in (MembershipStatus.VOID.value, MembershipStatus.EXPIRED.value):
        return True
    if product.product_type == ProductType.TERM.value:
        ends = _ensure_aware(m.ends_at)
        return ends is None or ends <= _now()
    if product.product_type == ProductType.COUNT.value:
        return int(m.remaining_sessions or 0) <= 0
    return _money(m.balance or 0) <= 0


def _preview_pt(db: Session, order: Order, balance: Decimal) -> dict[str, Any]:
    link = db.scalar(select(PtOrderLink).where(PtOrderLink.order_id == order.id))
    if link is None or link.fulfilled_package_id is None:
        return {
            "suggested_amount": "0.00",
            "unused": False,
            "basis": "missing_fulfillment",
            "detail": {},
            "entitlement_action": "void_remaining",
        }
    pkg = db.get(PtPackage, link.fulfilled_package_id)
    if pkg is None or pkg.status == PtPackageStatus.VOID.value:
        return {
            "suggested_amount": "0.00",
            "unused": False,
            "basis": "void_or_missing",
            "detail": {},
            "entitlement_action": "void_remaining",
        }
    from app.systems.gym.models.course import PtPackageProduct

    product = db.get(PtPackageProduct, pkg.product_id)
    purchased = int(product.session_count if product else 0) or int(pkg.remaining_sessions or 0) or 1
    remaining = int(pkg.remaining_sessions or 0)
    order_amt = _money(order.amount)
    unused = remaining >= purchased
    if remaining <= 0 or pkg.status == PtPackageStatus.EXPIRED.value:
        suggested = Decimal("0.00")
    elif unused:
        suggested = order_amt
    else:
        suggested = _money(order_amt * Decimal(remaining) / Decimal(purchased))
    suggested = min(suggested, balance)
    return {
        "suggested_amount": str(suggested),
        "unused": unused,
        "basis": "pt_remaining_sessions",
        "detail": {"package_id": pkg.id, "purchased_sessions": purchased, "remaining_sessions": remaining},
        "entitlement_action": "void_remaining",
    }


def _original_pay_channel(db: Session, order: Order) -> str:
    pay = db.scalar(
        select(Payment)
        .where(Payment.order_id == order.id, Payment.kind == PaymentKind.CHARGE.value)
        .order_by(Payment.id.desc())
    )
    if pay is None:
        return PaymentChannel.ONLINE.value
    return pay.channel


def _latest_succeeded_trade_no(db: Session, order_id: int) -> str | None:
    intent = db.scalar(
        select(PaymentIntent)
        .where(PaymentIntent.order_id == order_id, PaymentIntent.status == "succeeded")
        .order_by(PaymentIntent.id.desc())
    )
    return intent.out_trade_no if intent else None


def create_refund(
    db: Session,
    order: Order,
    *,
    amount: Decimal,
    channel: str,
    reason: str | None,
    force: bool,
    actor_staff_id: int | None,
    is_site_admin: bool,
) -> RefundIntent:
    if order.status not in (OrderStatus.PAID.value, OrderStatus.REFUNDED.value):
        # 部分退后仍为 paid；已 refunded 且余额 0 会在下方拦截
        if order.status != OrderStatus.PAID.value:
            raise AppError("invalid_state", "仅已支付（含部分退）订单可退款", status_code=400)
    balance = refundable_balance(order)
    amount = _money(amount)
    if amount <= 0 or amount > balance:
        raise AppError("validation_error", "退款金额不合法", status_code=422)

    preview = preview_refund(db, order)
    suggested = _money(preview["suggested_amount"])

    if channel not in (
        PaymentChannel.WECHAT_ORIGINAL.value,
        PaymentChannel.OFFLINE_CASH.value,
        PaymentChannel.OFFLINE_TRANSFER.value,
    ):
        raise AppError("validation_error", "退款渠道无效", status_code=422)

    orig = _original_pay_channel(db, order)
    if channel == PaymentChannel.WECHAT_ORIGINAL.value:
        if orig not in (PaymentChannel.ONLINE.value, PaymentChannel.WECHAT_ORIGINAL.value):
            # 线下收款不能原路微信
            if orig in (PaymentChannel.OFFLINE_CASH.value, PaymentChannel.OFFLINE_TRANSFER.value):
                raise AppError("validation_error", "线下收款订单请选择现金/转账退款", status_code=400)
        out_trade_no = _latest_succeeded_trade_no(db, order.id)
        # mock 即时支付可能无 intent：允许 dry_run / 用合成单号
        if out_trade_no is None and orig == PaymentChannel.ONLINE.value:
            out_trade_no = f"legacy-online-{order.id}"
    else:
        out_trade_no = None
        if orig == PaymentChannel.ONLINE.value:
            # 允许运营对线上单改线下退，但需 force
            if not force:
                raise AppError(
                    "validation_error",
                    "线上支付默认原路退；线下退款需超管 force",
                    status_code=400,
                )

    if order.order_type in ("membership", "pt_package"):
        if force and not is_site_admin:
            raise AppError("forbidden", "仅场地超管可强制退款", status_code=403)
        if not force:
            if suggested <= 0:
                raise AppError("invalid_state", "当前无可退剩余价值", status_code=400)
            if amount != suggested:
                raise AppError(
                    "validation_error",
                    f"会籍/课包非强制退款金额须等于建议额 {suggested}",
                    status_code=422,
                )
        elif force and not is_site_admin:
            raise AppError("forbidden", "权限不足", status_code=403)

    out_refund_no = f"r{order.id}t{int(time.time())}{out_trade_no[-4:] if out_trade_no else 'xx'}"
    intent = RefundIntent(
        site_id=order.site_id,
        order_id=order.id,
        out_refund_no=out_refund_no,
        out_trade_no=out_trade_no,
        amount=amount,
        suggested_amount=suggested,
        channel=channel,
        status="created",
        force=bool(force),
        reason=reason,
        actor_staff_id=actor_staff_id,
    )
    db.add(intent)
    db.flush()

    if channel == PaymentChannel.WECHAT_ORIGINAL.value:
        cfg = resolve_payment_settings(db, order.site_id)
        result = create_wechat_refund(
            cfg,
            out_trade_no=out_trade_no or f"o{order.id}",
            out_refund_no=out_refund_no,
            refund_amount=amount,
            total_amount=order.amount,
            reason=reason,
        )
        intent.provider_ref = result.provider_ref
        if result.status == "SUCCESS" or result.dry_run:
            apply_refund_success(db, intent, actor_staff_id=actor_staff_id)
        else:
            intent.status = "processing"
    else:
        apply_refund_success(db, intent, actor_staff_id=actor_staff_id)

    write_audit(
        db,
        action="order.refund",
        target_type="order",
        target_id=order.id,
        summary=f"退款 {amount} channel={channel} force={force} suggested={suggested}",
        actor_staff_id=actor_staff_id,
        site_id=order.site_id,
        merchant_id=order.merchant_id,
    )
    return intent


def apply_refund_success(
    db: Session,
    intent: RefundIntent,
    *,
    actor_staff_id: int | None = None,
) -> Order:
    if intent.status == "succeeded":
        order = db.get(Order, intent.order_id)
        assert order is not None
        return order

    order = db.get(Order, intent.order_id)
    if order is None:
        raise AppError("not_found", "订单不存在", status_code=404)

    this_amount = _money(intent.amount)
    suggested = _money(preview_refund(db, order)["suggested_amount"])

    intent.status = "succeeded"
    intent.succeeded_at = _now()
    order.refunded_amount = _money(getattr(order, "refunded_amount", None) or 0) + this_amount
    db.add(
        Payment(
            order_id=order.id,
            kind=PaymentKind.REFUND.value,
            channel=intent.channel,
            amount=intent.amount,
            note=f"{intent.out_refund_no} {intent.reason or ''}".strip(),
        )
    )

    # 会员返点按本次退款占比冲回，部分退也生效
    reverse_order_rebate(db, order, refund_id=intent.id, refund_amount=this_amount)

    full = _money(order.refunded_amount) >= _money(order.amount)
    if full:
        order.status = OrderStatus.REFUNDED.value
        # 全额退：未结算与已打款提成一并作废（已打款需人工扣回）
        void_records_for_order(db, order.id)
        if order.order_type == "dining":
            order.dining_status = None
    else:
        scale_records_for_partial_refund(db, order, refund_amount=this_amount)

    if order.order_type == "activity":
        if full:
            _cancel_activity_registration(db, order, actor_staff_id=actor_staff_id)
            restore_coupon_for_order(db, order, actor_staff_id=actor_staff_id)
    elif order.order_type in ("membership", "pt_package"):
        # 全额退或退满建议剩余价值时终止权益；force 部分退保留卡/课包
        if full or this_amount >= suggested:
            _void_entitlements(db, order, actor_staff_id=actor_staff_id)
        if full:
            restore_coupon_for_order(db, order, actor_staff_id=actor_staff_id)
    elif order.order_type in ("retail", "dining") or order.order_type == "retail":
        if full:
            if order.order_type != "dining":
                restock_retail_order(db, order, actor_staff_id=actor_staff_id)
            restore_coupon_for_order(db, order, actor_staff_id=actor_staff_id)
    else:
        if full:
            restore_coupon_for_order(db, order, actor_staff_id=actor_staff_id)
            try:
                restock_retail_order(db, order, actor_staff_id=actor_staff_id)
            except Exception:  # noqa: BLE001 — 非零售无库存
                pass

    return order


def _cancel_activity_registration(db: Session, order: Order, *, actor_staff_id: int | None) -> None:
    """活动订单全额退款后释放名额。"""
    registration = db.scalar(
        select(ActivityRegistration).where(ActivityRegistration.order_id == order.id)
    )
    if registration is None or registration.status == RegistrationStatus.CANCELLED.value:
        return
    registration.status = RegistrationStatus.CANCELLED.value
    write_audit(
        db,
        action="activity.registration_refunded",
        target_type="activity_registration",
        target_id=registration.id,
        summary=f"退款取消报名 order={order.id}",
        actor_staff_id=actor_staff_id,
        site_id=order.site_id,
        merchant_id=order.merchant_id,
    )


def _void_entitlements(db: Session, order: Order, *, actor_staff_id: int | None) -> None:
    if order.order_type == "membership":
        link = db.scalar(select(MembershipOrderLink).where(MembershipOrderLink.order_id == order.id))
        if link and link.fulfilled_membership_id:
            m = db.get(Membership, link.fulfilled_membership_id)
            if m:
                void_membership(
                    db,
                    m,
                    actor_staff_id=actor_staff_id or 0,
                    site_id=order.site_id,
                )
    elif order.order_type == "pt_package":
        link = db.scalar(select(PtOrderLink).where(PtOrderLink.order_id == order.id))
        if link and link.fulfilled_package_id:
            pkg = db.get(PtPackage, link.fulfilled_package_id)
            if pkg and pkg.status != PtPackageStatus.VOID.value:
                pkg.status = PtPackageStatus.VOID.value
                write_audit(
                    db,
                    action="pt.void_on_refund",
                    target_type="pt_package",
                    target_id=pkg.id,
                    summary=f"退款作废课包 order={order.id}",
                    actor_staff_id=actor_staff_id,
                    site_id=order.site_id,
                    merchant_id=order.merchant_id,
                )
