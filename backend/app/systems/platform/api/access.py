"""门禁点、设备、授权（员工侧）。"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import RequestContext, get_current_context
from app.core.errors import AppError
from app.core.schemas.common import (
    AccessPointIn,
    AccessPointOut,
    DeviceOut,
    DeviceRegisterIn,
    GrantIn,
    GrantOut,
    MemberBrief,
)
from app.core.schemas.paging import PageOut
from app.core.security import hash_device_api_key
from app.systems.platform.models.access import AccessDevice, AccessEvent, AccessGrant, AccessPoint
from app.systems.platform.models.member import Member
from app.systems.platform.services.audit import write_audit
from app.systems.platform.services.sync_queue import GrantSyncMessage, publish_grant_sync

router = APIRouter(tags=["access"])


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AccessEventAdminOut(ORMModel):
    id: int
    device_id: int
    access_point_id: int
    member_id: int | None
    allowed: bool
    reason: str | None
    created_at: datetime
    member: MemberBrief | None = None


@router.get("/access-points", response_model=list[AccessPointOut])
def list_points(db: Session = Depends(get_db), ctx: RequestContext = Depends(get_current_context)):
    ctx.require_permission("access:read", "access:manage")
    q = select(AccessPoint).where(AccessPoint.site_id == ctx.site_id)
    if not ctx.is_site_admin:
        mid = ctx.resolve_merchant_id()
        q = q.where((AccessPoint.merchant_id == mid) | (AccessPoint.is_public_area.is_(True)))
    return list(db.scalars(q.order_by(AccessPoint.id)).all())


@router.post("/access-points", response_model=AccessPointOut)
def create_point(
    body: AccessPointIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("access:manage")
    merchant_id = None
    if not body.is_public_area:
        merchant_id = ctx.resolve_merchant_id(body.merchant_id)
    elif not ctx.is_site_admin:
        raise AppError("forbidden", "仅超管可创建公共区域门禁点", status_code=403)
    row = AccessPoint(
        site_id=ctx.site_id,
        merchant_id=merchant_id,
        name=body.name,
        is_public_area=body.is_public_area,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.post("/devices", response_model=DeviceOut)
def register_device(
    body: DeviceRegisterIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("access:manage")
    point = db.get(AccessPoint, body.access_point_id)
    if point is None or point.site_id != ctx.site_id:
        raise AppError("not_found", "门禁点不存在", status_code=404)
    if not ctx.is_site_admin and point.merchant_id != ctx.merchant_id and not point.is_public_area:
        raise AppError("forbidden", "禁止跨商户注册设备", status_code=403)
    if db.scalar(select(AccessDevice).where(AccessDevice.device_code == body.device_code)):
        raise AppError("conflict", "设备编码已存在", status_code=409)
    device = AccessDevice(
        access_point_id=point.id,
        device_code=body.device_code,
        api_key_hash=hash_device_api_key(body.api_key),
        is_online=False,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


@router.get("/devices", response_model=list[DeviceOut])
def list_devices(db: Session = Depends(get_db), ctx: RequestContext = Depends(get_current_context)):
    ctx.require_permission("access:read", "access:manage")
    points = select(AccessPoint.id).where(AccessPoint.site_id == ctx.site_id)
    if not ctx.is_site_admin:
        mid = ctx.resolve_merchant_id()
        points = points.where((AccessPoint.merchant_id == mid) | (AccessPoint.is_public_area.is_(True)))
    return list(
        db.scalars(select(AccessDevice).where(AccessDevice.access_point_id.in_(points)).order_by(AccessDevice.id)).all()
    )


@router.post("/grants", response_model=GrantOut)
def create_grant(
    body: GrantIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("access:manage")
    member = db.get(Member, body.member_id)
    if member is None or member.site_id != ctx.site_id:
        raise AppError("not_found", "会员不存在", status_code=404)
    point = db.get(AccessPoint, body.access_point_id)
    if point is None or point.site_id != ctx.site_id:
        raise AppError("not_found", "门禁点不存在", status_code=404)
    merchant_id = body.merchant_id
    if not point.is_public_area:
        merchant_id = ctx.resolve_merchant_id(body.merchant_id or point.merchant_id)

    grant = AccessGrant(
        member_id=body.member_id,
        access_point_id=body.access_point_id,
        merchant_id=merchant_id,
        valid_from=body.valid_from,
        valid_until=body.valid_until,
        revoked=False,
    )
    db.add(grant)
    db.flush()
    write_audit(
        db,
        action="grant.create",
        target_type="access_grant",
        target_id=grant.id,
        summary=f"授予会员 {body.member_id} 门禁点 {body.access_point_id}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=merchant_id,
    )
    db.commit()
    db.refresh(grant)
    publish_grant_sync(
        GrantSyncMessage(
            grant_id=grant.id,
            access_point_id=grant.access_point_id,
            member_id=grant.member_id,
            action="upsert",
        )
    )
    return grant


@router.post("/grants/{grant_id}/revoke", response_model=GrantOut)
def revoke_grant(
    grant_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("access:manage")
    grant = db.get(AccessGrant, grant_id)
    if grant is None:
        raise AppError("not_found", "授权不存在", status_code=404)
    point = db.get(AccessPoint, grant.access_point_id)
    if point is None or point.site_id != ctx.site_id:
        raise AppError("not_found", "授权不存在", status_code=404)
    if not ctx.is_site_admin and grant.merchant_id != ctx.merchant_id:
        raise AppError("forbidden", "禁止跨商户撤销", status_code=403)
    grant.revoked = True
    write_audit(
        db,
        action="grant.revoke",
        target_type="access_grant",
        target_id=grant.id,
        summary=f"撤销授权 {grant.id}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=grant.merchant_id,
    )
    db.commit()
    db.refresh(grant)
    publish_grant_sync(
        GrantSyncMessage(
            grant_id=grant.id,
            access_point_id=grant.access_point_id,
            member_id=grant.member_id,
            action="revoke",
        )
    )
    return grant


@router.get("/grants", response_model=list[GrantOut])
def list_grants(db: Session = Depends(get_db), ctx: RequestContext = Depends(get_current_context)):
    ctx.require_permission("access:read", "access:manage")
    q = select(AccessGrant).join(AccessPoint).where(AccessPoint.site_id == ctx.site_id)
    if not ctx.is_site_admin:
        q = q.where(AccessGrant.merchant_id == ctx.resolve_merchant_id())
    return list(db.scalars(q.order_by(AccessGrant.id.desc())).all())


@router.get("/access-events", response_model=PageOut[AccessEventAdminOut])
def list_access_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    merchant_id: int | None = None,
    allowed: bool | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """通行事件列表（服务端分页）。"""
    ctx.require_permission("access:read", "access:manage")
    filters = [AccessPoint.site_id == ctx.site_id]
    if not ctx.is_site_admin:
        mid = ctx.resolve_merchant_id()
        filters.append((AccessPoint.merchant_id == mid) | (AccessPoint.is_public_area.is_(True)))
    elif merchant_id is not None:
        filters.append(
            (AccessPoint.merchant_id == merchant_id) | (AccessPoint.is_public_area.is_(True))
        )
    if allowed is not None:
        filters.append(AccessEvent.allowed.is_(allowed))
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        member_ids = select(Member.id).where(or_(Member.phone.ilike(like), Member.name.ilike(like)))
        filters.append(AccessEvent.member_id.in_(member_ids))

    base = (
        select(AccessEvent)
        .join(AccessPoint, AccessEvent.access_point_id == AccessPoint.id)
        .where(*filters)
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = list(
        db.scalars(
            base.order_by(AccessEvent.id.desc()).offset((page - 1) * page_size).limit(page_size)
        ).all()
    )
    member_map = {
        m.id: m
        for m in db.scalars(
            select(Member).where(
                Member.id.in_({r.member_id for r in rows if r.member_id is not None} or {-1})
            )
        ).all()
    }
    items = []
    for r in rows:
        m = member_map.get(r.member_id) if r.member_id else None
        items.append(
            AccessEventAdminOut(
                id=r.id,
                device_id=r.device_id,
                access_point_id=r.access_point_id,
                member_id=r.member_id,
                allowed=r.allowed,
                reason=r.reason,
                created_at=r.created_at,
                member=MemberBrief(id=m.id, name=m.name, phone=m.phone) if m else None,
            )
        )
    return PageOut(items=items, total=total, page=page, page_size=page_size)
