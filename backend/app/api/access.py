"""门禁点、设备、授权（员工侧）。"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import RequestContext, get_current_context
from app.errors import AppError
from app.models.access import AccessDevice, AccessGrant, AccessPoint
from app.models.member import Member
from app.schemas.common import (
    AccessPointIn,
    AccessPointOut,
    DeviceOut,
    DeviceRegisterIn,
    GrantIn,
    GrantOut,
)
from app.security import hash_device_api_key
from app.services.audit import write_audit
from app.services.sync_queue import GrantSyncMessage, publish_grant_sync

router = APIRouter(tags=["access"])


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
