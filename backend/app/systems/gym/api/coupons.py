"""优惠券模板与发券 API。"""

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import RequestContext, get_current_context
from app.core.domain.member_brief import load_member_briefs
from app.core.domain.subsystems import assert_merchant_has_system
from app.core.errors import AppError
from app.core.schemas.common import MemberBrief
from app.core.schemas.paging import PageOut, paginate
from app.systems.gym.models.coupon import (
    ApplicableTo,
    CouponTemplate,
    DiscountType,
    MemberCoupon,
    MemberCouponStatus,
)
from app.systems.platform.models.member import Member, MerchantMember
from app.systems.platform.services.audit import write_audit
from app.systems.gym.services.coupon import _ensure_aware, issue_member_coupon

GYM_APPLICABLE = {ApplicableTo.RETAIL.value, ApplicableTo.MEMBERSHIP.value, ApplicableTo.BOTH.value, ApplicableTo.GYM.value}
CATERING_APPLICABLE = {ApplicableTo.DINING.value, ApplicableTo.CATERING.value}


def _system_for_applicable(applicable_to: str) -> str:
    return "catering" if applicable_to in CATERING_APPLICABLE else "gym"

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


class TemplatePatch(BaseModel):
    name: str | None = None
    discount_type: str | None = None
    threshold_amount: Decimal | None = None
    fixed_amount: Decimal | None = None
    percent_off: int | None = None
    applicable_to: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    total_limit: int | None = None
    claimable: bool | None = None
    per_member_limit: int | None = Field(default=None, ge=1, le=100)
    is_active: bool | None = None


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
    member: MemberBrief | None = None
    template_name: str | None = None
    discount_type: str | None = None
    threshold_amount: Decimal | None = None
    fixed_amount: Decimal | None = None
    percent_off: int | None = None
    applicable_to: str | None = None


class MemberCouponPatch(BaseModel):
    starts_at: datetime | None = None
    ends_at: datetime | None = None


def _template_in_scope(db: Session, ctx: RequestContext, template_id: int) -> CouponTemplate:
    t = db.get(CouponTemplate, template_id)
    if t is None:
        raise AppError("not_found", "券模板不存在", status_code=404)
    ctx.resolve_merchant_id(t.merchant_id, required=False)
    if not ctx.is_site_admin and ctx.merchant_id is not None and t.merchant_id != ctx.merchant_id:
        raise AppError("forbidden", "无权操作该券模板", status_code=403)
    return t


def _member_coupon_in_scope(db: Session, ctx: RequestContext, coupon_id: int) -> MemberCoupon:
    row = db.get(MemberCoupon, coupon_id)
    if row is None:
        raise AppError("not_found", "会员券不存在", status_code=404)
    if not ctx.is_site_admin and ctx.merchant_id is not None and row.merchant_id != ctx.merchant_id:
        raise AppError("forbidden", "无权操作该会员券", status_code=403)
    return row


def _build_member_coupon_out(
    row: MemberCoupon,
    tpl: CouponTemplate | None,
    member: MemberBrief | None = None,
) -> MemberCouponOut:
    return MemberCouponOut(
        id=row.id,
        merchant_id=row.merchant_id,
        template_id=row.template_id,
        member_id=row.member_id,
        status=row.status,
        starts_at=row.starts_at,
        ends_at=row.ends_at,
        used_order_id=row.used_order_id,
        member=member,
        template_name=tpl.name if tpl else None,
        discount_type=tpl.discount_type if tpl else None,
        threshold_amount=tpl.threshold_amount if tpl else None,
        fixed_amount=tpl.fixed_amount if tpl else None,
        percent_off=tpl.percent_off if tpl else None,
        applicable_to=tpl.applicable_to if tpl else None,
    )


def _member_coupon_out(db: Session, row: MemberCoupon, member: MemberBrief | None = None) -> MemberCouponOut:
    tpl = db.get(CouponTemplate, row.template_id)
    briefs = {row.member_id: member} if member is not None else load_member_briefs(db, {row.member_id})
    return _build_member_coupon_out(row, tpl, briefs.get(row.member_id))


def _validate_template_fields(
    *,
    discount_type: str,
    fixed_amount: Decimal | None,
    percent_off: int | None,
    applicable_to: str,
    starts_at: datetime,
    ends_at: datetime,
) -> None:
    if discount_type == DiscountType.FIXED.value:
        if fixed_amount is None or fixed_amount <= 0:
            raise AppError("invalid_coupon", "满减须配置正数金额", status_code=400)
    elif discount_type == DiscountType.PERCENT.value:
        if percent_off is None or not (1 <= percent_off <= 99):
            raise AppError("invalid_coupon", "折扣须为 1-99", status_code=400)
    else:
        raise AppError("invalid_coupon", "未知券类型", status_code=400)
    if applicable_to not in GYM_APPLICABLE | CATERING_APPLICABLE:
        raise AppError("invalid_coupon", "适用业务无效", status_code=400)
    if _ensure_aware(ends_at) <= _ensure_aware(starts_at):
        raise AppError("invalid_coupon", "有效期结束须晚于开始", status_code=400)


def _validate_template_body(body: TemplateIn) -> None:
    _validate_template_fields(
        discount_type=body.discount_type,
        fixed_amount=body.fixed_amount,
        percent_off=body.percent_off,
        applicable_to=body.applicable_to,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
    )


@router.get("/templates", response_model=PageOut[TemplateOut])
def list_templates(
    merchant_id: int | None = None,
    q: str | None = None,
    discount_type: str | None = None,
    applicable_to: str | None = None,
    is_active: bool | None = None,
    system: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("coupon:read", "coupon:manage", "coupon:redeem")
    mid = ctx.resolve_merchant_id(merchant_id, required=False)
    stmt = select(CouponTemplate)
    if mid is not None:
        stmt = stmt.where(CouponTemplate.merchant_id == mid)
    keyword = (q or "").strip()
    if keyword:
        stmt = stmt.where(CouponTemplate.name.ilike(f"%{keyword}%"))
    if discount_type:
        stmt = stmt.where(CouponTemplate.discount_type == discount_type)
    if applicable_to:
        stmt = stmt.where(CouponTemplate.applicable_to == applicable_to)
    elif system == "catering":
        stmt = stmt.where(CouponTemplate.applicable_to.in_(CATERING_APPLICABLE))
    elif system == "gym":
        stmt = stmt.where(CouponTemplate.applicable_to.in_(GYM_APPLICABLE))
    if is_active is not None:
        stmt = stmt.where(CouponTemplate.is_active == is_active)
    rows, total = paginate(db, stmt.order_by(CouponTemplate.id.desc()), page=page, page_size=page_size)
    return PageOut(items=rows, total=total, page=page, page_size=page_size)


@router.get("/templates/{template_id}", response_model=TemplateOut)
def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("coupon:read", "coupon:manage", "coupon:redeem")
    return _template_in_scope(db, ctx, template_id)


@router.patch("/templates/{template_id}", response_model=TemplateOut)
def update_template(
    template_id: int,
    body: TemplatePatch,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("coupon:manage")
    t = _template_in_scope(db, ctx, template_id)
    data = body.model_dump(exclude_unset=True)
    if "name" in data:
        name = (data["name"] or "").strip()
        if not name:
            raise AppError("validation_error", "模板名称不能为空", status_code=422)
        t.name = name
    for field in (
        "discount_type",
        "threshold_amount",
        "fixed_amount",
        "percent_off",
        "applicable_to",
        "starts_at",
        "ends_at",
        "total_limit",
        "claimable",
        "per_member_limit",
        "is_active",
    ):
        if field in data:
            setattr(t, field, data[field])
    _validate_template_fields(
        discount_type=t.discount_type,
        fixed_amount=t.fixed_amount,
        percent_off=t.percent_off,
        applicable_to=t.applicable_to,
        starts_at=t.starts_at,
        ends_at=t.ends_at,
    )
    if t.applicable_to:
        assert_merchant_has_system(db, t.merchant_id, _system_for_applicable(t.applicable_to))
    write_audit(
        db,
        action="coupon.template_update",
        target_type="coupon_template",
        target_id=t.id,
        summary=f"更新券模板 {t.name}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=t.merchant_id,
    )
    db.commit()
    db.refresh(t)
    return t


@router.post("/templates", response_model=TemplateOut)
def create_template(
    body: TemplateIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("coupon:manage")
    _validate_template_body(body)
    mid = ctx.resolve_merchant_id(body.merchant_id)
    assert_merchant_has_system(db, mid, _system_for_applicable(body.applicable_to))
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
    t = _template_in_scope(db, ctx, template_id)
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


class IssueBatchIn(BaseModel):
    merchant_id: int | None = None
    template_id: int
    member_ids: list[int] | None = None


class IssueBatchOut(BaseModel):
    issued: int
    skipped: int
    total: int


@router.post("/issue-batch", response_model=IssueBatchOut)
def issue_coupon_batch(
    body: IssueBatchIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """按商户批量发券：不传 member_ids 则发给该商户全部关联会员。"""
    ctx.require_permission("coupon:manage")
    mid = ctx.resolve_merchant_id(body.merchant_id)
    t = db.get(CouponTemplate, body.template_id)
    if t is None or t.merchant_id != mid:
        raise AppError("not_found", "券模板不存在", status_code=404)
    if not t.is_active:
        raise AppError("coupon_inactive", "券模板已停用", status_code=400)
    if body.member_ids:
        member_ids = list(dict.fromkeys(body.member_ids))
    else:
        member_ids = list(
            db.scalars(select(MerchantMember.member_id).where(MerchantMember.merchant_id == mid)).all()
        )
    issued = 0
    skipped = 0
    for member_id in member_ids:
        member = db.get(Member, member_id)
        if member is None or member.site_id != ctx.site_id:
            skipped += 1
            continue
        try:
            issue_member_coupon(
                db,
                template=t,
                member_id=member_id,
                require_claimable=False,
                actor_staff_id=ctx.staff.id,
                site_id=ctx.site_id,
                audit_action="coupon.issue_batch",
            )
            issued += 1
        except AppError:
            skipped += 1
    db.commit()
    return IssueBatchOut(issued=issued, skipped=skipped, total=len(member_ids))


@router.get("/member-coupons", response_model=PageOut[MemberCouponOut])
def list_member_coupons(
    merchant_id: int | None = None,
    member_id: int | None = None,
    template_id: int | None = None,
    status: str | None = None,
    system: str | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("coupon:read", "coupon:manage", "coupon:redeem")
    mid = ctx.resolve_merchant_id(merchant_id, required=False)
    filters = [MemberCoupon.merchant_id == mid] if mid is not None else []
    if member_id is not None:
        filters.append(MemberCoupon.member_id == member_id)
    if template_id is not None:
        filters.append(MemberCoupon.template_id == template_id)
    if status is not None:
        filters.append(MemberCoupon.status == status)
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        mid_sq = select(Member.id).where(or_(Member.phone.ilike(like), Member.name.ilike(like)))
        filters.append(MemberCoupon.member_id.in_(mid_sq))
    base = select(MemberCoupon)
    if system == "catering" or system == "gym":
        base = base.join(CouponTemplate, CouponTemplate.id == MemberCoupon.template_id)
        if system == "catering":
            base = base.where(CouponTemplate.applicable_to.in_(CATERING_APPLICABLE))
        else:
            base = base.where(CouponTemplate.applicable_to.in_(GYM_APPLICABLE))
    if filters:
        base = base.where(*filters)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = list(
        db.scalars(
            base
            .order_by(MemberCoupon.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    briefs = load_member_briefs(db, {r.member_id for r in rows})
    tpl_ids = {r.template_id for r in rows}
    tpl_map = {
        t.id: t
        for t in db.scalars(select(CouponTemplate).where(CouponTemplate.id.in_(tpl_ids))).all()
    } if tpl_ids else {}
    items = [
        _build_member_coupon_out(r, tpl_map.get(r.template_id), briefs.get(r.member_id))
        for r in rows
    ]
    return PageOut(items=items, total=total, page=page, page_size=page_size)


@router.get("/member-coupons/{coupon_id}", response_model=MemberCouponOut)
def get_member_coupon(
    coupon_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("coupon:read", "coupon:manage", "coupon:redeem")
    return _member_coupon_out(db, _member_coupon_in_scope(db, ctx, coupon_id))


@router.patch("/member-coupons/{coupon_id}", response_model=MemberCouponOut)
def update_member_coupon(
    coupon_id: int,
    body: MemberCouponPatch,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """调整未使用会员券的有效期。"""
    ctx.require_permission("coupon:manage")
    row = _member_coupon_in_scope(db, ctx, coupon_id)
    if row.status == MemberCouponStatus.USED.value:
        raise AppError("invalid_state", "已使用的券不能编辑", status_code=400)
    if row.status == MemberCouponStatus.VOID.value:
        raise AppError("invalid_state", "已停用的券不能编辑", status_code=400)
    if body.starts_at is not None:
        row.starts_at = body.starts_at
    if body.ends_at is not None:
        row.ends_at = body.ends_at
    if _ensure_aware(row.ends_at) <= _ensure_aware(row.starts_at):
        raise AppError("invalid_coupon", "有效期结束须晚于开始", status_code=400)
    write_audit(
        db,
        action="coupon.member_update",
        target_type="member_coupon",
        target_id=row.id,
        summary=f"调整会员券有效期 member={row.member_id}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=row.merchant_id,
    )
    db.commit()
    db.refresh(row)
    return _member_coupon_out(db, row)


@router.post("/member-coupons/{coupon_id}/deactivate", response_model=MemberCouponOut)
def deactivate_member_coupon(
    coupon_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """停用未使用的会员券，停用后不可核销。"""
    ctx.require_permission("coupon:manage")
    row = _member_coupon_in_scope(db, ctx, coupon_id)
    if row.status == MemberCouponStatus.USED.value:
        raise AppError("invalid_state", "已使用的券不能停用", status_code=400)
    if row.status == MemberCouponStatus.VOID.value:
        return _member_coupon_out(db, row)
    row.status = MemberCouponStatus.VOID.value
    write_audit(
        db,
        action="coupon.member_deactivate",
        target_type="member_coupon",
        target_id=row.id,
        summary=f"停用会员券 member={row.member_id}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=row.merchant_id,
    )
    db.commit()
    db.refresh(row)
    return _member_coupon_out(db, row)
