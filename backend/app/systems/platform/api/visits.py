"""临访登记 API。"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import RequestContext, get_current_context
from app.core.errors import AppError
from app.core.schemas.paging import PageOut
from app.systems.platform.models.access import AccessGrant, AccessPoint
from app.systems.platform.models.member import Member, MerchantMember
from app.systems.platform.models.visit import VisitPass
from app.systems.platform.services.audit import write_audit
from app.systems.platform.services.sync_queue import GrantSyncMessage, publish_grant_sync

router = APIRouter(prefix="/visits", tags=["visits"])


class VisitIn(BaseModel):
    merchant_id: int | None = None
    member_id: int
    access_point_id: int
    hours: int = Field(default=2, ge=1, le=72)


class VisitPatch(BaseModel):
    member_id: int | None = None
    access_point_id: int | None = None
    hours: int | None = Field(default=None, ge=1, le=72)


class VisitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    merchant_id: int
    member_id: int
    access_point_id: int
    grant_id: int
    hours: int
    status: str
    created_at: datetime


@router.get("")
def list_visits(
    merchant_id: int | None = None,
    access_point_id: int | None = None,
    q: str | None = None,
    status: str | None = None,
    page: int | None = Query(default=None, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("access:manage", "access:read")
    mid = ctx.resolve_merchant_id(merchant_id, required=False)
    filters = []
    if mid is not None:
        filters.append(VisitPass.merchant_id == mid)
    elif not ctx.is_site_admin:
        filters.append(VisitPass.merchant_id == ctx.resolve_merchant_id())
    if status:
        filters.append(VisitPass.status == status)
    if access_point_id is not None:
        filters.append(VisitPass.access_point_id == access_point_id)
    keyword = (q or "").strip()
    query = select(VisitPass)
    if keyword:
        like = f"%{keyword}%"
        query = query.join(Member, Member.id == VisitPass.member_id)
        filters.append(or_(Member.phone.ilike(like), Member.name.ilike(like)))
    if filters:
        query = query.where(*filters)
    if page is None:
        return list(db.scalars(query.order_by(VisitPass.id.desc())).all())
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = list(
        db.scalars(query.order_by(VisitPass.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    )
    return PageOut(
        items=[VisitOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=VisitOut)
def create_visit(
    body: VisitIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("access:manage")
    mid = ctx.resolve_merchant_id(body.merchant_id)
    member = db.get(Member, body.member_id)
    if member is None or member.site_id != ctx.site_id:
        raise AppError("not_found", "会员不存在", status_code=404)
    point = db.get(AccessPoint, body.access_point_id)
    if point is None or point.site_id != ctx.site_id:
        raise AppError("not_found", "门禁点不存在", status_code=404)
    if not point.is_public_area and point.merchant_id not in {None, mid}:
        raise AppError("forbidden", "门禁点不属于当前商户", status_code=403)

    link = db.scalar(
        select(MerchantMember).where(
            MerchantMember.member_id == member.id,
            MerchantMember.merchant_id == mid,
        )
    )
    if link is None:
        db.add(MerchantMember(member_id=member.id, merchant_id=mid))
        db.flush()

    now = datetime.now(timezone.utc)
    grant = AccessGrant(
        member_id=member.id,
        access_point_id=point.id,
        merchant_id=mid,
        valid_from=now,
        valid_until=now + timedelta(hours=body.hours),
        revoked=False,
    )
    db.add(grant)
    db.flush()
    visit = VisitPass(
        merchant_id=mid,
        member_id=member.id,
        access_point_id=point.id,
        grant_id=grant.id,
        hours=body.hours,
        status="active",
        created_by_staff_id=ctx.staff.id,
    )
    db.add(visit)
    db.flush()
    write_audit(
        db,
        action="visit.create",
        target_type="visit_pass",
        target_id=visit.id,
        summary=f"临访 member={member.id} hours={body.hours}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=mid,
    )
    db.commit()
    db.refresh(visit)
    publish_grant_sync(
        GrantSyncMessage(
            grant_id=grant.id,
            access_point_id=grant.access_point_id,
            member_id=grant.member_id,
            action="upsert",
        )
    )
    return visit


@router.post("/{visit_id}/revoke", response_model=VisitOut)
def revoke_visit(
    visit_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("access:manage")
    visit = db.get(VisitPass, visit_id)
    if visit is None:
        raise AppError("not_found", "临访记录不存在", status_code=404)
    ctx.resolve_merchant_id(visit.merchant_id)
    if visit.status != "active":
        raise AppError("invalid_state", "临访已结束", status_code=400)
    grant = db.get(AccessGrant, visit.grant_id)
    if grant is not None:
        grant.revoked = True
    visit.status = "revoked"
    write_audit(
        db,
        action="visit.revoke",
        target_type="visit_pass",
        target_id=visit.id,
        summary="撤销临访",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=visit.merchant_id,
    )
    db.commit()
    db.refresh(visit)
    if grant is not None:
        publish_grant_sync(
            GrantSyncMessage(
                grant_id=grant.id,
                access_point_id=grant.access_point_id,
                member_id=grant.member_id,
                action="revoke",
            )
        )
    return visit


@router.patch("/{visit_id}", response_model=VisitOut)
def patch_visit(
    visit_id: int,
    body: VisitPatch,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("access:manage")
    visit = db.get(VisitPass, visit_id)
    if visit is None:
        raise AppError("not_found", "临访记录不存在", status_code=404)
    ctx.resolve_merchant_id(visit.merchant_id)
    if visit.status != "active":
        raise AppError("invalid_state", "仅有效临访可编辑", status_code=400)
    if body.member_id is not None:
        member = db.get(Member, body.member_id)
        if member is None or member.site_id != ctx.site_id:
            raise AppError("not_found", "会员不存在", status_code=404)
        visit.member_id = member.id
    if body.access_point_id is not None:
        point = db.get(AccessPoint, body.access_point_id)
        if point is None or point.site_id != ctx.site_id:
            raise AppError("not_found", "门禁点不存在", status_code=404)
        visit.access_point_id = point.id
    if body.hours is not None:
        visit.hours = body.hours
    grant = db.get(AccessGrant, visit.grant_id)
    if grant is not None:
        grant.member_id = visit.member_id
        grant.access_point_id = visit.access_point_id
        grant.valid_until = grant.valid_from + timedelta(hours=visit.hours)
    write_audit(
        db,
        action="visit.update",
        target_type="visit_pass",
        target_id=visit.id,
        summary=f"编辑临访 hours={visit.hours}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=visit.merchant_id,
    )
    db.commit()
    db.refresh(visit)
    return visit


@router.delete("/{visit_id}")
def delete_visit(
    visit_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("access:manage")
    visit = db.get(VisitPass, visit_id)
    if visit is None:
        raise AppError("not_found", "临访记录不存在", status_code=404)
    ctx.resolve_merchant_id(visit.merchant_id)
    grant = db.get(AccessGrant, visit.grant_id)
    if grant is not None:
        grant.revoked = True
    db.delete(visit)
    write_audit(
        db,
        action="visit.delete",
        target_type="visit_pass",
        target_id=visit_id,
        summary="删除临访",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=visit.merchant_id,
    )
    db.commit()
    return {"ok": True}
