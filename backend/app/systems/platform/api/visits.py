"""临访登记 API。"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import RequestContext, get_current_context
from app.core.errors import AppError
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


@router.get("", response_model=list[VisitOut])
def list_visits(
    merchant_id: int | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("access:manage", "access:read")
    mid = ctx.resolve_merchant_id(merchant_id)
    return list(
        db.scalars(
            select(VisitPass).where(VisitPass.merchant_id == mid).order_by(VisitPass.id.desc())
        ).all()
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
