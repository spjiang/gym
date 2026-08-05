"""器材台账与报修 API。"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import RequestContext, get_current_context
from app.core.domain.subsystems import assert_merchant_has_system
from app.core.errors import AppError
from app.core.schemas.paging import PageOut
from app.systems.gym.models.equipment import (
    EquipmentAsset,
    EquipmentRepairTicket,
    EquipmentStatus,
    RepairTicketStatus,
)
from app.systems.platform.services.audit import write_audit

router = APIRouter(prefix="/equipment", tags=["equipment"])


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AssetIn(BaseModel):
    merchant_id: int | None = None
    name: str = Field(min_length=1, max_length=128)
    category: str = "other"
    brand_model: str | None = None
    asset_code: str = Field(min_length=1, max_length=64)
    area: str | None = None
    status: str = EquipmentStatus.IN_USE.value
    note: str | None = None


class AssetOut(ORMModel):
    id: int
    merchant_id: int
    name: str
    category: str
    brand_model: str | None
    asset_code: str
    area: str | None
    status: str
    note: str | None
    created_at: datetime


class AssetPatch(BaseModel):
    name: str | None = None
    category: str | None = None
    brand_model: str | None = None
    area: str | None = None
    status: str | None = None
    note: str | None = None


class RepairIn(BaseModel):
    merchant_id: int | None = None
    asset_id: int
    description: str = Field(min_length=1)


class RepairCompleteIn(BaseModel):
    resolution: str | None = None
    asset_status: str = EquipmentStatus.IN_USE.value


class RepairOut(ORMModel):
    id: int
    merchant_id: int
    asset_id: int
    reporter_staff_id: int | None
    description: str
    status: str
    resolution: str | None
    created_at: datetime


_VALID_ASSET_STATUS = {s.value for s in EquipmentStatus}


@router.get("/assets", response_model=PageOut[AssetOut])
def list_assets(
    merchant_id: int | None = None,
    status: str | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("equipment:read", "equipment:manage", "equipment:repair")
    mid = ctx.resolve_merchant_id(merchant_id)
    filters = [EquipmentAsset.merchant_id == mid]
    if status is not None:
        filters.append(EquipmentAsset.status == status)
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        filters.append(
            or_(
                EquipmentAsset.name.ilike(like),
                EquipmentAsset.asset_code.ilike(like),
                EquipmentAsset.area.ilike(like),
            )
        )
    total = db.scalar(select(func.count()).select_from(EquipmentAsset).where(*filters)) or 0
    rows = list(
        db.scalars(
            select(EquipmentAsset)
            .where(*filters)
            .order_by(EquipmentAsset.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return PageOut(items=rows, total=total, page=page, page_size=page_size)


@router.post("/assets", response_model=AssetOut)
def create_asset(
    body: AssetIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("equipment:manage")
    if body.status not in _VALID_ASSET_STATUS:
        raise AppError("invalid_status", "器材状态无效", status_code=400)
    mid = ctx.resolve_merchant_id(body.merchant_id)
    assert_merchant_has_system(db, mid, "gym")
    exists = db.scalar(
        select(EquipmentAsset).where(
            EquipmentAsset.merchant_id == mid,
            EquipmentAsset.asset_code == body.asset_code,
        )
    )
    if exists is not None:
        raise AppError("duplicate_asset_code", "资产编号已存在", status_code=409)
    asset = EquipmentAsset(
        merchant_id=mid,
        name=body.name,
        category=body.category,
        brand_model=body.brand_model,
        asset_code=body.asset_code,
        area=body.area,
        status=body.status,
        note=body.note,
    )
    db.add(asset)
    db.flush()
    write_audit(
        db,
        action="equipment.create",
        target_type="equipment_asset",
        target_id=asset.id,
        summary=f"创建器材 {asset.asset_code}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=mid,
    )
    db.commit()
    db.refresh(asset)
    return asset


@router.patch("/assets/{asset_id}", response_model=AssetOut)
def patch_asset(
    asset_id: int,
    body: AssetPatch,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("equipment:manage")
    asset = db.get(EquipmentAsset, asset_id)
    if asset is None:
        raise AppError("not_found", "器材不存在", status_code=404)
    ctx.resolve_merchant_id(asset.merchant_id)
    data = body.model_dump(exclude_unset=True)
    if "status" in data and data["status"] not in _VALID_ASSET_STATUS:
        raise AppError("invalid_status", "器材状态无效", status_code=400)
    for k, v in data.items():
        setattr(asset, k, v)
    db.commit()
    db.refresh(asset)
    return asset


@router.get("/repairs", response_model=PageOut[RepairOut])
def list_repairs(
    merchant_id: int | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("equipment:read", "equipment:manage", "equipment:repair")
    mid = ctx.resolve_merchant_id(merchant_id)
    filters = [EquipmentRepairTicket.merchant_id == mid]
    if status is not None:
        filters.append(EquipmentRepairTicket.status == status)
    total = db.scalar(select(func.count()).select_from(EquipmentRepairTicket).where(*filters)) or 0
    rows = list(
        db.scalars(
            select(EquipmentRepairTicket)
            .where(*filters)
            .order_by(EquipmentRepairTicket.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return PageOut(items=rows, total=total, page=page, page_size=page_size)


@router.post("/repairs", response_model=RepairOut)
def create_repair(
    body: RepairIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("equipment:repair", "equipment:manage")
    mid = ctx.resolve_merchant_id(body.merchant_id)
    assert_merchant_has_system(db, mid, "gym")
    asset = db.get(EquipmentAsset, body.asset_id)
    if asset is None or asset.merchant_id != mid:
        raise AppError("not_found", "器材不存在", status_code=404)
    ticket = EquipmentRepairTicket(
        merchant_id=mid,
        asset_id=asset.id,
        reporter_staff_id=ctx.staff.id,
        description=body.description,
        status=RepairTicketStatus.OPEN.value,
    )
    asset.status = EquipmentStatus.REPAIR.value
    db.add(ticket)
    db.flush()
    write_audit(
        db,
        action="equipment.repair_open",
        target_type="equipment_repair_ticket",
        target_id=ticket.id,
        summary=f"报修 asset={asset.id}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=mid,
    )
    db.commit()
    db.refresh(ticket)
    return ticket


@router.post("/repairs/{ticket_id}/complete", response_model=RepairOut)
def complete_repair(
    ticket_id: int,
    body: RepairCompleteIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("equipment:manage")
    if body.asset_status not in _VALID_ASSET_STATUS:
        raise AppError("invalid_status", "器材状态无效", status_code=400)
    ticket = db.get(EquipmentRepairTicket, ticket_id)
    if ticket is None:
        raise AppError("not_found", "报修单不存在", status_code=404)
    ctx.resolve_merchant_id(ticket.merchant_id)
    if ticket.status in {RepairTicketStatus.DONE.value, RepairTicketStatus.CLOSED.value}:
        raise AppError("invalid_state", "报修单已结束", status_code=400)
    asset = db.get(EquipmentAsset, ticket.asset_id)
    if asset is None:
        raise AppError("not_found", "器材不存在", status_code=404)
    ticket.status = RepairTicketStatus.DONE.value
    ticket.resolution = body.resolution
    asset.status = body.asset_status
    write_audit(
        db,
        action="equipment.repair_complete",
        target_type="equipment_repair_ticket",
        target_id=ticket.id,
        summary=f"完成报修 asset_status={body.asset_status}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=ticket.merchant_id,
    )
    db.commit()
    db.refresh(ticket)
    return ticket
