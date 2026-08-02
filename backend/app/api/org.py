"""商户类型与商户。"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import RequestContext, get_current_context
from app.errors import AppError
from app.models.org import Merchant, MerchantStatus, MerchantType
from app.schemas.common import MerchantIn, MerchantOut, MerchantTypeIn, MerchantTypeOut
from app.services.audit import write_audit

router = APIRouter(tags=["organization"])


@router.get("/merchant-types", response_model=list[MerchantTypeOut])
def list_merchant_types(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("org:read", "org:manage")
    return list(db.scalars(select(MerchantType).order_by(MerchantType.id)).all())


@router.post("/merchant-types", response_model=MerchantTypeOut)
def create_merchant_type(
    body: MerchantTypeIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    if not ctx.is_site_admin:
        raise AppError("forbidden", "仅场地超管可管理商户类型", status_code=403)
    exists = db.scalar(select(MerchantType).where(MerchantType.code == body.code))
    if exists:
        raise AppError("conflict", "商户类型编码已存在", status_code=409)
    row = MerchantType(code=body.code, name=body.name, description=body.description)
    db.add(row)
    db.flush()
    write_audit(
        db,
        action="merchant_type.create",
        target_type="merchant_type",
        target_id=row.id,
        summary=f"创建商户类型 {row.code}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
    )
    db.commit()
    db.refresh(row)
    return row


@router.get("/merchants", response_model=list[MerchantOut])
def list_merchants(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("org:read", "org:manage")
    q = select(Merchant).where(Merchant.site_id == ctx.site_id)
    if not ctx.is_site_admin:
        if ctx.merchant_id is None:
            return []
        q = q.where(Merchant.id == ctx.merchant_id)
    return list(db.scalars(q.order_by(Merchant.id)).all())


@router.post("/merchants", response_model=MerchantOut)
def create_merchant(
    body: MerchantIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    if not ctx.is_site_admin:
        raise AppError("forbidden", "仅场地超管可创建商户", status_code=403)
    site_id = body.site_id or ctx.site_id
    mt = db.get(MerchantType, body.merchant_type_id)
    if mt is None:
        raise AppError("not_found", "商户类型不存在", status_code=404)
    if body.status not in {s.value for s in MerchantStatus}:
        raise AppError("invalid_status", "非法商户状态", status_code=400)
    row = Merchant(
        site_id=site_id,
        merchant_type_id=body.merchant_type_id,
        name=body.name,
        status=body.status,
    )
    db.add(row)
    db.flush()
    write_audit(
        db,
        action="merchant.create",
        target_type="merchant",
        target_id=row.id,
        summary=f"创建商户 {row.name}",
        actor_staff_id=ctx.staff.id,
        site_id=site_id,
        merchant_id=row.id,
    )
    db.commit()
    db.refresh(row)
    return row


@router.patch("/merchants/{merchant_id}", response_model=MerchantOut)
def update_merchant_status(
    merchant_id: int,
    status: str,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    if not ctx.is_site_admin:
        raise AppError("forbidden", "仅场地超管可变更商户状态", status_code=403)
    if status not in {s.value for s in MerchantStatus}:
        raise AppError("invalid_status", "非法商户状态", status_code=400)
    row = db.get(Merchant, merchant_id)
    if row is None or row.site_id != ctx.site_id:
        raise AppError("not_found", "商户不存在", status_code=404)
    row.status = status
    write_audit(
        db,
        action="merchant.status_update",
        target_type="merchant",
        target_id=row.id,
        summary=f"商户状态变更为 {status}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=row.id,
    )
    db.commit()
    db.refresh(row)
    return row
