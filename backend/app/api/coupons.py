"""优惠券模板与发券 API。"""

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import RequestContext, get_current_context
from app.domain.subsystems import assert_merchant_has_system
from app.errors import AppError
from app.models.coupon import (
    ApplicableTo,
    CouponTemplate,
    DiscountType,
    MemberCoupon,
)
from app.models.member import Member
from app.services.audit import write_audit
from app.services.coupon import _ensure_aware, issue_member_coupon

router = APIRouter(prefix="/coupons", tags=["coupons"])


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TemplateIn(BaseModel):
    merchant_id: int | None = None
    name: str
    discount_type: str
    threshold_amount: Decimal = Decimal("0")
    fixed_amount: Decimal | None = None
    percent_off: int | None = None
    applicable_to: str
    starts_at: datetime
    ends_at: datetime
    total_limit: int | None = None
    claimable: bool = False
    per_member_limit: int = Field(default=1, ge=1, le=100)


class TemplateOut(ORMModel):
    id: int
    merchant_id: int
    name: str
    discount_type: str
    threshold_amount: Decimal
    fixed_amount: Decimal | None
    percent_off: int | None
    applicable_to: str
    starts_at: datetime
    ends_at: datetime
    total_limit: int | None
    issued_count: int
    claimable: bool
    per_member_limit: int
    is_active: bool


class IssueIn(BaseModel):
    merchant_id: int | None = None
    template_id: int
    member_id: int


class MemberCouponOut(ORMModel):
    id: int
    merchant_id: int
    template_id: int
    member_id: int
    status: str
    starts_at: datetime
    ends_at: datetime
    used_order_id: int | None


def _validate_template_body(body: TemplateIn) -> None:
    if body.discount_type == DiscountType.FIXED.value:
        if body.fixed_amount is None or body.fixed_amount <= 0:
            raise AppError("invalid_coupon", "满减须配置正数金额", status_code=400)
    elif body.discount_type == DiscountType.PERCENT.value:
        if body.percent_off is None or not (1 <= body.percent_off <= 99):
            raise AppError("invalid_coupon", "折扣须为 1-99", status_code=400)
    else:
        raise AppError("invalid_coupon", "未知券类型", status_code=400)
    if body.applicable_to not in {
        ApplicableTo.RETAIL.value,
        ApplicableTo.MEMBERSHIP.value,
        ApplicableTo.BOTH.value,
    }:
        raise AppError("invalid_coupon", "适用业务无效", status_code=400)
    if _ensure_aware(body.ends_at) <= _ensure_aware(body.starts_at):
        raise AppError("invalid_coupon", "有效期结束须晚于开始", status_code=400)


@router.get("/templates", response_model=list[TemplateOut])
def list_templates(
    merchant_id: int | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("coupon:read", "coupon:manage", "coupon:redeem")
    mid = ctx.resolve_merchant_id(merchant_id)
    return list(
        db.scalars(
            select(CouponTemplate).where(CouponTemplate.merchant_id == mid).order_by(CouponTemplate.id.desc())
        ).all()
    )


@router.post("/templates", response_model=TemplateOut)
def create_template(
    body: TemplateIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("coupon:manage")
    _validate_template_body(body)
    mid = ctx.resolve_merchant_id(body.merchant_id)
    assert_merchant_has_system(db, mid, "gym")
    t = CouponTemplate(
        merchant_id=mid,
        name=body.name,
        discount_type=body.discount_type,
        threshold_amount=body.threshold_amount,
        fixed_amount=body.fixed_amount,
        percent_off=body.percent_off,
        applicable_to=body.applicable_to,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        total_limit=body.total_limit,
        issued_count=0,
        claimable=body.claimable,
        per_member_limit=body.per_member_limit,
        is_active=True,
    )
    db.add(t)
    db.flush()
    write_audit(
        db,
        action="coupon.template_create",
        target_type="coupon_template",
        target_id=t.id,
        summary=f"创建券模板 {t.name}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=mid,
    )
    db.commit()
    db.refresh(t)
    return t


@router.post("/templates/{template_id}/deactivate", response_model=TemplateOut)
def deactivate_template(
    template_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("coupon:manage")
    t = db.get(CouponTemplate, template_id)
    if t is None:
        raise AppError("not_found", "券模板不存在", status_code=404)
    ctx.resolve_merchant_id(t.merchant_id)
    t.is_active = False
    db.commit()
    db.refresh(t)
    return t


@router.post("/issue", response_model=MemberCouponOut)
def issue_coupon(
    body: IssueIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("coupon:manage")
    mid = ctx.resolve_merchant_id(body.merchant_id)
    assert_merchant_has_system(db, mid, "gym")
    t = db.get(CouponTemplate, body.template_id)
    if t is None or t.merchant_id != mid:
        raise AppError("not_found", "券模板不存在", status_code=404)
    if not t.is_active:
        raise AppError("coupon_inactive", "券模板已停用", status_code=400)
    member = db.get(Member, body.member_id)
    if member is None or member.site_id != ctx.site_id:
        raise AppError("not_found", "会员不存在", status_code=404)

    mc = issue_member_coupon(
        db,
        template=t,
        member_id=body.member_id,
        require_claimable=False,
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        audit_action="coupon.issue",
    )
    db.commit()
    db.refresh(mc)
    return mc


@router.get("/member-coupons", response_model=list[MemberCouponOut])
def list_member_coupons(
    merchant_id: int | None = None,
    member_id: int | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("coupon:read", "coupon:manage", "coupon:redeem")
    mid = ctx.resolve_merchant_id(merchant_id)
    q = select(MemberCoupon).where(MemberCoupon.merchant_id == mid)
    if member_id is not None:
        q = q.where(MemberCoupon.member_id == member_id)
    if status is not None:
        q = q.where(MemberCoupon.status == status)
    return list(db.scalars(q.order_by(MemberCoupon.id.desc())).all())
