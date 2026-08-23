"""优惠券计价、绑定、核销与回退。"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.systems.platform.models.commerce import Order, OrderStatus
from app.systems.gym.models.coupon import (
    ApplicableTo,
    CouponTemplate,
    DiscountType,
    MemberCoupon,
    MemberCouponStatus,
    OrderCouponLink,
)
from app.systems.platform.services.audit import write_audit

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
    if template.applicable_to in {ApplicableTo.BOTH.value, ApplicableTo.GYM.value}:
        return order_type in {"retail", "membership"}
    if template.applicable_to in {ApplicableTo.DINING.value, ApplicableTo.CATERING.value}:
        return order_type == "dining"
    return template.applicable_to == order_type


def _applicable_to_system(template: CouponTemplate, system: str | None) -> bool:
    if not system:
        return True
    if system == "catering":
        return _applicable(template, "dining")
    if system == "gym":
        return _applicable(template, "retail") or _applicable(template, "membership")
    return True


def _load_coupon_for_use(
    db: Session,
    *,
    member_coupon_id: int,
    merchant_id: int,
    member_id: int,
    order_type: str,
    for_update: bool = False,
) -> tuple[MemberCoupon, CouponTemplate]:
    stmt = select(MemberCoupon).where(MemberCoupon.id == member_coupon_id)
    if for_update:
        stmt = stmt.with_for_update()
    mc = db.scalar(stmt)
    if mc is None or mc.merchant_id != merchant_id:
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
    if not _applicable(template, order_type):
        raise AppError("coupon_not_applicable", "券不适用于该业务", status_code=400)
    return mc, template


def preview_coupon_discount(
    db: Session,
    *,
    member_coupon_id: int,
    merchant_id: int,
    member_id: int,
    order_type: str,
    original_amount: Decimal,
) -> tuple[Decimal, Decimal]:
    """预览用券实付与抵扣，不落库。"""
    _mc, template = _load_coupon_for_use(
        db,
        member_coupon_id=member_coupon_id,
        merchant_id=merchant_id,
        member_id=member_id,
        order_type=order_type,
    )
    return compute_payable(original_amount, template)


def list_unused_coupons_for_order_type(
    db: Session,
    *,
    member_id: int,
    merchant_id: int,
    order_type: str,
) -> list[tuple[MemberCoupon, CouponTemplate]]:
    """列出该会员在该商户、适用于指定业务的未使用券。"""
    now = _now()
    rows = list(
        db.execute(
            select(MemberCoupon, CouponTemplate)
            .join(CouponTemplate, CouponTemplate.id == MemberCoupon.template_id)
            .where(
                MemberCoupon.member_id == member_id,
                MemberCoupon.merchant_id == merchant_id,
                MemberCoupon.status == MemberCouponStatus.UNUSED.value,
                CouponTemplate.is_active.is_(True),
            )
            .order_by(MemberCoupon.id.desc())
        ).all()
    )
    usable: list[tuple[MemberCoupon, CouponTemplate]] = []
    for mc, tpl in rows:
        if _ensure_aware(mc.ends_at) < now or _ensure_aware(mc.starts_at) > now:
            continue
        if not _applicable(tpl, order_type):
            continue
        usable.append((mc, tpl))
    return usable


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
    mc, template = _load_coupon_for_use(
        db,
        member_coupon_id=member_coupon_id,
        merchant_id=order.merchant_id,
        member_id=member_id,
        order_type=order.order_type,
        for_update=True,
    )
    busy = db.scalar(
        select(OrderCouponLink.id)
        .join(Order, Order.id == OrderCouponLink.order_id)
        .where(
            OrderCouponLink.member_coupon_id == mc.id,
            Order.status == OrderStatus.PENDING.value,
            OrderCouponLink.order_id != order.id,
        )
    )
    if busy is not None:
        raise AppError("coupon_in_use", "券已绑定其他待支付订单", status_code=400)
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
    now = _now()
    if _ensure_aware(mc.ends_at) < now or _ensure_aware(mc.starts_at) > now:
        raise AppError("coupon_expired", "券不在有效期内", status_code=400)
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


def detach_coupon_link_for_order(db: Session, order: Order) -> None:
    """待支付取消时解绑优惠券，券仍为未使用。"""
    link = db.scalar(select(OrderCouponLink).where(OrderCouponLink.order_id == order.id))
    if link is None:
        return
    db.delete(link)


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
    locked = db.scalar(
        select(CouponTemplate).where(CouponTemplate.id == template.id).with_for_update()
    )
    if locked is None:
        raise AppError("not_found", "券模板不存在", status_code=404)
    template = locked
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


def list_claimable_templates(
    db: Session,
    *,
    merchant_id: int,
    member_id: int,
    system: str | None = None,
) -> list[CouponTemplate]:
    """仅返回当前会员还能领的券：已达每人上限的不出现在可领列表。"""
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
    out: list[CouponTemplate] = []
    for t in rows:
        if _ensure_aware(t.starts_at) > now or _ensure_aware(t.ends_at) < now:
            continue
        if t.total_limit is not None and t.issued_count >= t.total_limit:
            continue
        if not _applicable_to_system(t, system):
            continue
        if member_claim_count(db, template_id=t.id, member_id=member_id) >= t.per_member_limit:
            continue
        out.append(t)
    return out
