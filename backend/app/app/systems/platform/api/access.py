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
    AccessPointPatch,
    DeviceOut,
    DevicePatch,
    DeviceRegisterIn,
    GrantIn,
    GrantOut,
    GrantPatch,
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


@router.get("/access-points")
def list_points(
    page: int | None = Query(default=None, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = None,
    merchant_id: int | None = None,
    is_public_area: bool | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("access:read", "access:manage")
    filters = [AccessPoint.site_id == ctx.site_id]
    if not ctx.is_site_admin:
        mid = ctx.resolve_merchant_id()
        filters.append((AccessPoint.merchant_id == mid) | (AccessPoint.is_public_area.is_(True)))
    elif merchant_id is not None:
        filters.append((AccessPoint.merchant_id == merchant_id) | (AccessPoint.is_public_area.is_(True)))
    if is_public_area is not None:
        filters.append(AccessPoint.is_public_area.is_(is_public_area))
    keyword = (q or "").strip()
    if keyword:
        filters.append(AccessPoint.name.ilike(f"%{keyword}%"))
    base = select(AccessPoint).where(*filters)
    if page is None:
        return list(db.scalars(base.order_by(AccessPoint.id)).all())
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = list(
        db.scalars(base.order_by(AccessPoint.id).offset((page - 1) * page_size).limit(page_size)).all()
    )
    return PageOut(
        items=[AccessPointOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


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


@router.patch("/access-points/{point_id}", response_model=AccessPointOut)
def patch_point(
    point_id: int,
    body: AccessPointPatch,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("access:manage")
    row = db.get(AccessPoint, point_id)
    if row is None or row.site_id != ctx.site_id:
        raise AppError("not_found", "门禁点不存在", status_code=404)
    if body.name is not None:
        row.name = body.name.strip()
    if body.is_public_area is not None:
        if body.is_public_area and not ctx.is_site_admin:
            raise AppError("forbidden", "仅超管可设为公共区域", status_code=403)
        row.is_public_area = body.is_public_area
        if body.is_public_area:
            row.merchant_id = None
    if body.merchant_id is not None and not row.is_public_area:
        row.merchant_id = ctx.resolve_merchant_id(body.merchant_id)
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


@router.get("/devices")
def list_devices(
    page: int | None = Query(default=None, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = None,
    access_point_id: int | None = None,
    is_online: bool | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("access:read", "access:manage")
    points = select(AccessPoint.id).where(AccessPoint.site_id == ctx.site_id)
    if not ctx.is_site_admin:
        mid = ctx.resolve_merchant_id()
        points = points.where((AccessPoint.merchant_id == mid) | (AccessPoint.is_public_area.is_(True)))
    filters = [AccessDevice.access_point_id.in_(points)]
    if access_point_id is not None:
        filters.append(AccessDevice.access_point_id == access_point_id)
    if is_online is not None:
        filters.append(AccessDevice.is_online.is_(is_online))
    keyword = (q or "").strip()
    if keyword:
        filters.append(AccessDevice.device_code.ilike(f"%{keyword}%"))
    base = select(AccessDevice).where(*filters)
    if page is None:
        return list(db.scalars(base.order_by(AccessDevice.id)).all())
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = list(
        db.scalars(base.order_by(AccessDevice.id).offset((page - 1) * page_size).limit(page_size)).all()
    )
    return PageOut(
        items=[DeviceOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch("/devices/{device_id}", response_model=DeviceOut)
def patch_device(
    device_id: int,
    body: DevicePatch,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("access:manage")
    device = db.get(AccessDevice, device_id)
    if device is None:
        raise AppError("not_found", "设备不存在", status_code=404)
    point = db.get(AccessPoint, device.access_point_id)
    if point is None or point.site_id != ctx.site_id:
        raise AppError("not_found", "设备不存在", status_code=404)
    if body.access_point_id is not None:
        new_point = db.get(AccessPoint, body.access_point_id)
        if new_point is None or new_point.site_id != ctx.site_id:
            raise AppError("not_found", "门禁点不存在", status_code=404)
        device.access_point_id = new_point.id
    if body.device_code is not None:
        code = body.device_code.strip()
        exists = db.scalar(
            select(AccessDevice).where(AccessDevice.device_code == code, AccessDevice.id != device.id)
        )
        if exists:
            raise AppError("conflict", "设备编码已存在", status_code=409)
        device.device_code = code
    if body.api_key:
        device.api_key_hash = hash_device_api_key(body.api_key)
    db.commit()
    db.refresh(device)
    return device


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


@router.get("/grants")
def list_grants(
    page: int | None = Query(default=None, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = None,
    access_point_id: int | None = None,
    revoked: bool | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("access:read", "access:manage")
    filters = [AccessPoint.site_id == ctx.site_id]
    if not ctx.is_site_admin:
        filters.append(AccessGrant.merchant_id == ctx.resolve_merchant_id())
    if access_point_id is not None:
        filters.append(AccessGrant.access_point_id == access_point_id)
    if revoked is not None:
        filters.append(AccessGrant.revoked.is_(revoked))
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        member_ids = select(Member.id).where(or_(Member.phone.ilike(like), Member.name.ilike(like)))
        filters.append(AccessGrant.member_id.in_(member_ids))
    base = select(AccessGrant).join(AccessPoint).where(*filters)
    if page is None:
        return list(db.scalars(base.order_by(AccessGrant.id.desc())).all())
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = list(
        db.scalars(base.order_by(AccessGrant.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    )
    return PageOut(
        items=[GrantOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch("/grants/{grant_id}", response_model=GrantOut)
def patch_grant(
    grant_id: int,
    body: GrantPatch,
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
    if body.access_point_id is not None:
        new_point = db.get(AccessPoint, body.access_point_id)
        if new_point is None or new_point.site_id != ctx.site_id:
            raise AppError("not_found", "门禁点不存在", status_code=404)
        grant.access_point_id = new_point.id
    if body.valid_from is not None:
        grant.valid_from = body.valid_from
    if body.valid_until is not None:
        grant.valid_until = body.valid_until
    if body.revoked is not None:
        grant.revoked = body.revoked
    db.commit()
    db.refresh(grant)
    return grant


@router.get("/access-events", response_model=PageOut[AccessEventAdminOut])
def list_access_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    merchant_id: int | None = None,
    access_point_id: int | None = None,
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
    if access_point_id is not None:
        filters.append(AccessEvent.access_point_id == access_point_id)
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


class AccessEventPatch(BaseModel):
    reason: str | None = None
    detail: str | None = None


@router.patch("/access-events/{event_id}", response_model=AccessEventAdminOut)
def patch_access_event(
    event_id: int,
    body: AccessEventPatch,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """补记通行事件原因/备注（不改放行结果）。"""
    ctx.require_permission("access:manage")
    row = db.get(AccessEvent, event_id)
    if row is None:
        raise AppError("not_found", "通行事件不存在", status_code=404)
    point = db.get(AccessPoint, row.access_point_id)
    if point is None or point.site_id != ctx.site_id:
        raise AppError("not_found", "通行事件不存在", status_code=404)
    if not ctx.is_site_admin:
        mid = ctx.resolve_merchant_id()
        if point.merchant_id not in (None, mid) and not point.is_public_area:
            raise AppError("forbidden", "禁止跨商户访问", status_code=403)
    if body.reason is not None:
        row.reason = body.reason.strip() or None
    if body.detail is not None:
        row.detail = body.detail.strip() or None
    db.commit()
    db.refresh(row)
    member = db.get(Member, row.member_id) if row.member_id else None
    return AccessEventAdminOut(
        id=row.id,
        device_id=row.device_id,
        access_point_id=row.access_point_id,
        member_id=row.member_id,
        allowed=row.allowed,
        reason=row.reason,
        created_at=row.created_at,
        member=MemberBrief(id=member.id, name=member.name, phone=member.phone) if member else None,
    )
