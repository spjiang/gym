"""优惠券计价、绑定、核销与回退。"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models.commerce import Order
from app.models.coupon import (
    ApplicableTo,
    CouponTemplate,
    DiscountType,
    MemberCoupon,
    MemberCouponStatus,
    OrderCouponLink,
)
from app.services.audit import write_audit

MIN_PAYABLE = Decimal("0.01")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def compute_payable(original: Decimal, template: CouponTemplate) -> tuple[Decimal, Decimal]:
    """返回 (实付, 抵扣金额)。"""
    if original < template.threshold_amount:
        raise AppError("coupon_threshold", "未达到用券门槛", status_code=400)
    if template.discount_type == DiscountType.FIXED.value:
        if template.fixed_amount is None or template.fixed_amount <= 0:
            raise AppError("invalid_coupon", "满减金额无效", status_code=400)
        discount = min(template.fixed_amount, original)
    elif template.discount_type == DiscountType.PERCENT.value:
        if not template.percent_off or not (1 <= template.percent_off <= 99):
            raise AppError("invalid_coupon", "折扣比例无效", status_code=400)
        discount = (original * Decimal(template.percent_off) / Decimal(100)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    else:
        raise AppError("invalid_coupon", "未知券类型", status_code=400)
    payable = original - discount
    if payable < MIN_PAYABLE:
        payable = MIN_PAYABLE
        discount = original - payable
    return payable, discount


def _applicable(template: CouponTemplate, order_type: str) -> bool:
    if template.applicable_to == ApplicableTo.BOTH.value:
        return order_type in {"retail", "membership"}
    return template.applicable_to == order_type


def attach_coupon_to_order(
    db: Session,
    *,
    order: Order,
    member_coupon_id: int,
    original_amount: Decimal,
    member_id: int | None,
) -> Decimal:
    """校验并绑定券，返回实付金额；不核销。"""
    if member_id is None:
        raise AppError("coupon_member_required", "用券须指定会员", status_code=400)
    mc = db.scalar(select(MemberCoupon).where(MemberCoupon.id == member_coupon_id).with_for_update())
    if mc is None or mc.merchant_id != order.merchant_id:
        raise AppError("not_found", "券不存在", status_code=404)
    if mc.member_id != member_id:
        raise AppError("coupon_member_mismatch", "券不属于该会员", status_code=400)
    if mc.status != MemberCouponStatus.UNUSED.value:
        raise AppError("coupon_unavailable", "券不可用", status_code=400)
    now = _now()
    if _ensure_aware(mc.ends_at) < now or _ensure_aware(mc.starts_at) > now:
        raise AppError("coupon_expired", "券不在有效期内", status_code=400)
    template = db.get(CouponTemplate, mc.template_id)
    if template is None or not template.is_active:
        raise AppError("coupon_inactive", "券模板不可用", status_code=400)
    if not _applicable(template, order.order_type):
        raise AppError("coupon_not_applicable", "券不适用于该业务", status_code=400)
    payable, discount = compute_payable(original_amount, template)
    db.add(
        OrderCouponLink(
            order_id=order.id,
            member_coupon_id=mc.id,
            discount_amount=discount,
        )
    )
    return payable


def redeem_coupon_for_order(db: Session, order: Order, *, actor_staff_id: int | None = None) -> None:
    link = db.scalar(select(OrderCouponLink).where(OrderCouponLink.order_id == order.id))
    if link is None:
        return
    mc = db.scalar(select(MemberCoupon).where(MemberCoupon.id == link.member_coupon_id).with_for_update())
    if mc is None:
        return
    if mc.status == MemberCouponStatus.USED.value and mc.used_order_id == order.id:
        return
    if mc.status != MemberCouponStatus.UNUSED.value:
        raise AppError("coupon_unavailable", "券已被占用或不可用", status_code=400)
    mc.status = MemberCouponStatus.USED.value
    mc.used_order_id = order.id
    mc.used_at = _now()
    write_audit(
        db,
        action="coupon.redeem",
        target_type="member_coupon",
        target_id=mc.id,
        summary=f"核销券 order={order.id}",
        actor_staff_id=actor_staff_id,
        site_id=order.site_id,
        merchant_id=order.merchant_id,
    )


def restore_coupon_for_order(db: Session, order: Order, *, actor_staff_id: int | None = None) -> None:
    link = db.scalar(select(OrderCouponLink).where(OrderCouponLink.order_id == order.id))
    if link is None:
        return
    mc = db.scalar(select(MemberCoupon).where(MemberCoupon.id == link.member_coupon_id).with_for_update())
    if mc is None or mc.status != MemberCouponStatus.USED.value:
        return
    now = _now()
    if _ensure_aware(mc.ends_at) < now:
        mc.status = MemberCouponStatus.EXPIRED.value
    else:
        mc.status = MemberCouponStatus.UNUSED.value
    mc.used_order_id = None
    mc.used_at = None
    write_audit(
        db,
        action="coupon.restore",
        target_type="member_coupon",
        target_id=mc.id,
        summary=f"退款回退券 order={order.id} status={mc.status}",
        actor_staff_id=actor_staff_id,
        site_id=order.site_id,
        merchant_id=order.merchant_id,
    )


def member_claim_count(db: Session, *, template_id: int, member_id: int) -> int:
    return len(
        list(
            db.scalars(
                select(MemberCoupon).where(
                    MemberCoupon.template_id == template_id,
                    MemberCoupon.member_id == member_id,
                )
            ).all()
        )
    )


def issue_member_coupon(
    db: Session,
    *,
    template: CouponTemplate,
    member_id: int,
    require_claimable: bool = False,
    actor_staff_id: int | None = None,
    site_id: int | None = None,
    audit_action: str = "coupon.issue",
) -> MemberCoupon:
    """发放一张会员券；require_claimable=True 时校验自助领取规则。"""
    if not template.is_active:
        raise AppError("coupon_inactive", "券模板已停用", status_code=400)
    now = _now()
    if _ensure_aware(template.ends_at) < now or _ensure_aware(template.starts_at) > now:
        raise AppError("coupon_expired", "券模板不在有效期内", status_code=400)
    if require_claimable and not template.claimable:
        raise AppError("coupon_not_claimable", "该券不可自助领取", status_code=400)
    if template.total_limit is not None and template.issued_count >= template.total_limit:
        raise AppError("coupon_limit", "已达发放上限", status_code=400)
    claimed = member_claim_count(db, template_id=template.id, member_id=member_id)
    if claimed >= template.per_member_limit:
        raise AppError("coupon_member_limit", "已达每人领取上限", status_code=400)

    mc = MemberCoupon(
        merchant_id=template.merchant_id,
        template_id=template.id,
        member_id=member_id,
        status=MemberCouponStatus.UNUSED.value,
        starts_at=template.starts_at,
        ends_at=template.ends_at,
    )
    template.issued_count += 1
    db.add(mc)
    db.flush()
    write_audit(
        db,
        action=audit_action,
        target_type="member_coupon",
        target_id=mc.id,
        summary=f"发券 template={template.id} member={member_id}",
        actor_staff_id=actor_staff_id,
        site_id=site_id,
        merchant_id=template.merchant_id,
    )
    return mc


def list_claimable_templates(db: Session, *, merchant_id: int) -> list[CouponTemplate]:
    now = _now()
    rows = db.scalars(
        select(CouponTemplate)
        .where(
            CouponTemplate.merchant_id == merchant_id,
            CouponTemplate.is_active.is_(True),
            CouponTemplate.claimable.is_(True),
        )
        .order_by(CouponTemplate.id.desc())
    ).all()
    return [
        t
        for t in rows
        if _ensure_aware(t.starts_at) <= now <= _ensure_aware(t.ends_at)
        and (t.total_limit is None or t.issued_count < t.total_limit)
    ]
