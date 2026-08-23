"""销售档案 API。"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import RequestContext, get_current_context
from app.core.merchant_scope import assert_merchant_in_site, gym_merchant_ids
from app.core.domain.subsystems import assert_merchant_has_system
from app.core.errors import AppError
from app.core.schemas.paging import PageOut, paginate
from app.systems.gym.models.commission import CommissionBeneficiary, CommissionRule
from app.systems.gym.models.sales import SalesRep
from app.systems.gym.services.commission import ORDER_SCOPES, validate_profile_commission_rule
from app.systems.gym.services.sales_member import link_sales_member
from app.systems.platform.models.identity import StaffUser
from app.systems.platform.models.member import Member
from app.systems.platform.services.audit import write_audit

router = APIRouter(tags=["sales"])


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SalesRepIn(BaseModel):
    merchant_id: int | None = None
    staff_user_id: int
    member_id: int
    display_name: str = Field(min_length=1, max_length=64)
    commission_rule_id: int | None = None


class SalesRepOut(BaseModel):
    id: int
    merchant_id: int
    staff_user_id: int
    member_id: int
    display_name: str
    commission_rule_id: int | None = None
    commission_rule_name: str | None = None
    is_active: bool
    created_at: datetime
    staff_username: str | None = None
    member_name: str | None = None
    member_phone: str | None = None


def _sales_out(db: Session, row: SalesRep) -> SalesRepOut:
    staff = db.get(StaffUser, row.staff_user_id)
    member = db.get(Member, row.member_id)
    rule = db.get(CommissionRule, row.commission_rule_id) if row.commission_rule_id else None
    return SalesRepOut(
        id=row.id,
        merchant_id=row.merchant_id,
        staff_user_id=row.staff_user_id,
        member_id=row.member_id,
        display_name=row.display_name,
        commission_rule_id=row.commission_rule_id,
        commission_rule_name=rule.name if rule else None,
        is_active=row.is_active,
        created_at=row.created_at,
        staff_username=staff.username if staff else None,
        member_name=member.name if member else None,
        member_phone=member.phone if member else None,
    )


def _assert_staff_available(
    db: Session, *, site_id: int, staff_user_id: int, sales_rep_id: int | None
) -> None:
    staff = db.get(StaffUser, staff_user_id)
    if staff is None or staff.site_id != site_id:
        raise AppError("not_found", "员工不存在", status_code=404)
    q = select(SalesRep.id).where(SalesRep.staff_user_id == staff_user_id)
    if sales_rep_id is not None:
        q = q.where(SalesRep.id != sales_rep_id)
    if db.scalar(q) is not None:
        raise AppError("staff_in_use", "该员工已绑定其他销售档案", status_code=400)


@router.get("/sales-reps", response_model=PageOut[SalesRepOut])
def list_sales_reps(
    merchant_id: int | None = None,
    is_active: bool | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("sales:manage", "commission:manage", "*")
    mid = ctx.resolve_merchant_id(merchant_id, required=False)
    stmt = select(SalesRep)
    if mid is not None:
        assert_merchant_has_system(db, mid, "gym")
        stmt = stmt.where(SalesRep.merchant_id == mid)
    else:
        gym_mids = gym_merchant_ids(db, ctx.site_id)
        stmt = stmt.where(SalesRep.merchant_id.in_(gym_mids or [-1]))
    if is_active is not None:
        stmt = stmt.where(SalesRep.is_active.is_(is_active))
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(
                SalesRep.display_name.ilike(like),
                SalesRep.staff_user_id.in_(
                    select(StaffUser.id).where(
                        or_(StaffUser.display_name.ilike(like), StaffUser.username.ilike(like))
                    )
                ),
                SalesRep.member_id.in_(
                    select(Member.id).where(or_(Member.name.ilike(like), Member.phone.ilike(like)))
                ),
            )
        )
    rows, total = paginate(db, stmt.order_by(SalesRep.id.desc()), page=page, page_size=page_size)
    return PageOut(items=[_sales_out(db, r) for r in rows], total=total, page=page, page_size=page_size)


@router.post("/sales-reps", response_model=SalesRepOut)
def create_sales_rep(
    body: SalesRepIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("sales:manage", "commission:manage", "*")
    mid = ctx.resolve_merchant_id(body.merchant_id)
    assert_merchant_has_system(db, mid, "gym")
    _assert_staff_available(db, site_id=ctx.site_id, staff_user_id=body.staff_user_id, sales_rep_id=None)
    validate_profile_commission_rule(
        db,
        rule_id=body.commission_rule_id,
        merchant_id=mid,
        allowed_scopes=set(ORDER_SCOPES.keys()),
        beneficiary=CommissionBeneficiary.SELLER.value,
    )
    name = body.display_name.strip()
    rep = SalesRep(
        merchant_id=mid,
        staff_user_id=body.staff_user_id,
        member_id=body.member_id,
        display_name=name,
        commission_rule_id=body.commission_rule_id,
        is_active=True,
    )
    db.add(rep)
    db.flush()
    link_sales_member(
        db, sales_rep=rep, site_id=ctx.site_id, merchant_id=mid, member_id=body.member_id
    )
    write_audit(
        db,
        action="sales_rep.create",
        target_type="sales_rep",
        target_id=rep.id,
        summary=f"创建销售档案 {rep.display_name}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=mid,
    )
    db.commit()
    db.refresh(rep)
    return _sales_out(db, rep)


@router.patch("/sales-reps/{sales_rep_id}", response_model=SalesRepOut)
def update_sales_rep(
    sales_rep_id: int,
    body: SalesRepIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("sales:manage", "commission:manage", "*")
    rep = db.get(SalesRep, sales_rep_id)
    if rep is None:
        raise AppError("not_found", "销售档案不存在", status_code=404)
    assert_merchant_in_site(db, ctx, rep.merchant_id)
    ctx.resolve_merchant_id(rep.merchant_id)
    if body.staff_user_id != rep.staff_user_id:
        _assert_staff_available(
            db, site_id=ctx.site_id, staff_user_id=body.staff_user_id, sales_rep_id=rep.id
        )
        rep.staff_user_id = body.staff_user_id
    rep.display_name = body.display_name.strip()
    validate_profile_commission_rule(
        db,
        rule_id=body.commission_rule_id,
        merchant_id=rep.merchant_id,
        allowed_scopes=set(ORDER_SCOPES.keys()),
        beneficiary=CommissionBeneficiary.SELLER.value,
    )
    rep.commission_rule_id = body.commission_rule_id
    link_sales_member(
        db,
        sales_rep=rep,
        site_id=ctx.site_id,
        merchant_id=rep.merchant_id,
        member_id=body.member_id,
    )
    write_audit(
        db,
        action="sales_rep.update",
        target_type="sales_rep",
        target_id=rep.id,
        summary=f"更新销售档案 {rep.display_name}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=rep.merchant_id,
    )
    db.commit()
    db.refresh(rep)
    return _sales_out(db, rep)


@router.post("/sales-reps/{sales_rep_id}/deactivate", response_model=SalesRepOut)
def deactivate_sales_rep(
    sales_rep_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("sales:manage", "commission:manage", "*")
    rep = db.get(SalesRep, sales_rep_id)
    if rep is None:
        raise AppError("not_found", "销售档案不存在", status_code=404)
    assert_merchant_in_site(db, ctx, rep.merchant_id)
    ctx.resolve_merchant_id(rep.merchant_id)
    rep.is_active = False
    write_audit(
        db,
        action="sales_rep.deactivate",
        target_type="sales_rep",
        target_id=rep.id,
        summary=f"停用销售档案 {rep.display_name}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=rep.merchant_id,
    )
    db.commit()
    db.refresh(rep)
    return _sales_out(db, rep)
