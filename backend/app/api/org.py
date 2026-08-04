"""商户类型、商户与业态子系统关联。"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import RequestContext, get_current_context
from app.domain.subsystems import (
    DEFAULT_SYSTEMS_BY_MERCHANT_TYPE,
    SYSTEM_CATALOG,
    merchant_subsystem_codes,
    replace_merchant_subsystems,
)
from app.errors import AppError
from app.models.org import Merchant, MerchantStatus, MerchantType
from app.schemas.common import MerchantIn, MerchantOut, MerchantSubsystemsIn, MerchantTypeIn, MerchantTypeOut
from app.services.audit import write_audit

router = APIRouter(tags=["organization"])


class SubsystemCatalogOut(BaseModel):
    code: str
    name: str
    short_name: str
    description: str
    permission: str
    is_business: bool


def _merchant_out(db: Session, row: Merchant) -> MerchantOut:
    return MerchantOut(
        id=row.id,
        site_id=row.site_id,
        merchant_type_id=row.merchant_type_id,
        name=row.name,
        status=row.status,
        created_at=row.created_at,
        subsystem_codes=merchant_subsystem_codes(db, row.id),
    )


@router.get("/subsystems", response_model=list[SubsystemCatalogOut])
def list_subsystems(ctx: RequestContext = Depends(get_current_context)):
    """子系统目录（供创建商户勾选与门户展示）。"""
    ctx.require_permission("org:read", "org:manage", "order:read", "*")
    return [
        SubsystemCatalogOut(
            code=v["code"],
            name=v["name"],
            short_name=v["short_name"],
            description=v["description"],
            permission=v["permission"],
            is_business=v["code"] in {"gym", "catering"},
        )
        for v in SYSTEM_CATALOG.values()
    ]


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
    rows = list(db.scalars(q.order_by(Merchant.id)).all())
    return [_merchant_out(db, row) for row in rows]


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
    if not body.name.strip():
        raise AppError("validation_error", "商户名称不能为空", status_code=422)

    codes = body.subsystem_codes
    if not codes:
        codes = DEFAULT_SYSTEMS_BY_MERCHANT_TYPE.get(mt.code, ["gym"])

    row = Merchant(
        site_id=site_id,
        merchant_type_id=body.merchant_type_id,
        name=body.name.strip(),
        status=body.status,
    )
    db.add(row)
    db.flush()
    linked = replace_merchant_subsystems(db, row.id, codes)
    write_audit(
        db,
        action="merchant.create",
        target_type="merchant",
        target_id=row.id,
        summary=f"创建商户 {row.name}，子系统 {','.join(linked)}",
        actor_staff_id=ctx.staff.id,
        site_id=site_id,
        merchant_id=row.id,
    )
    db.commit()
    db.refresh(row)
    return _merchant_out(db, row)


@router.put("/merchants/{merchant_id}/subsystems", response_model=MerchantOut)
def update_merchant_subsystems(
    merchant_id: int,
    body: MerchantSubsystemsIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    if not ctx.is_site_admin:
        raise AppError("forbidden", "仅场地超管可调整商户子系统", status_code=403)
    row = db.get(Merchant, merchant_id)
    if row is None or row.site_id != ctx.site_id:
        raise AppError("not_found", "商户不存在", status_code=404)
    linked = replace_merchant_subsystems(db, row.id, body.subsystem_codes)
    write_audit(
        db,
        action="merchant.subsystems_update",
        target_type="merchant",
        target_id=row.id,
        summary=f"更新商户子系统为 {','.join(linked)}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=row.id,
    )
    db.commit()
    db.refresh(row)
    return _merchant_out(db, row)


@router.get("/merchants/{merchant_id}/order-types")
def merchant_order_types(
    merchant_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """返回该商户当前业态允许的线下订单类型。"""
    ctx.require_permission("order:read", "order:write")
    mid = ctx.resolve_merchant_id(merchant_id)
    row = db.get(Merchant, mid)
    if row is None or row.site_id != ctx.site_id:
        raise AppError("not_found", "商户不存在", status_code=404)
    from app.domain.subsystems import ORDER_TYPE_LABELS, allowed_order_types_for_merchant

    allowed = sorted(allowed_order_types_for_merchant(db, mid))
    return [{"value": t, "label": ORDER_TYPE_LABELS.get(t, t)} for t in allowed]


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
    return _merchant_out(db, row)
