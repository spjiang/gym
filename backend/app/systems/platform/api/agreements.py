"""后台协议管理。"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import RequestContext, get_current_context
from app.core.errors import AppError
from app.core.schemas.paging import PageOut, paginate
from app.systems.platform.models.agreement import LegalAgreement
from app.systems.platform.models.org import Merchant
from app.systems.platform.services.agreements import (
    AGREEMENT_SCENES,
    assert_scene,
    require_merchant_in_site,
    sanitize_agreement_html,
)
from app.systems.platform.services.audit import write_audit

router = APIRouter(prefix="/agreements", tags=["agreements"])

_SCENE_LABELS = {
    "membership": "会籍",
    "pt_package": "私教课包",
    "activity": "活动报名",
    "dining": "餐饮",
}


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AgreementIn(BaseModel):
    merchant_id: int
    scene: str
    title: str = Field(min_length=1, max_length=128)
    content: str = Field(min_length=1)
    is_enabled: bool = True


class AgreementPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=128)
    content: str | None = Field(default=None, min_length=1)
    is_enabled: bool | None = None


class AgreementOut(ORMModel):
    id: int
    site_id: int
    merchant_id: int
    merchant_name: str | None = None
    scene: str
    title: str
    content: str
    is_enabled: bool
    updated_at: datetime | None = None


def _out(row: LegalAgreement, merchant_name: str | None = None) -> AgreementOut:
    return AgreementOut(
        id=row.id,
        site_id=row.site_id,
        merchant_id=row.merchant_id,
        merchant_name=merchant_name,
        scene=row.scene,
        title=row.title,
        content=row.content,
        is_enabled=row.is_enabled,
        updated_at=row.updated_at,
    )


def _load(db: Session, ctx: RequestContext, agreement_id: int) -> LegalAgreement:
    row = db.get(LegalAgreement, agreement_id)
    if row is None or row.site_id != ctx.site_id:
        raise AppError("not_found", "协议不存在", status_code=404)
    ctx.assert_merchant_access(row.merchant_id)
    return row


@router.get("", response_model=PageOut[AgreementOut])
def list_agreements(
    merchant_id: int | None = None,
    scene: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("org:read", "org:write")
    mid = ctx.resolve_merchant_id(merchant_id, required=False)
    stmt = select(LegalAgreement).where(LegalAgreement.site_id == ctx.site_id)
    if mid is not None:
        stmt = stmt.where(LegalAgreement.merchant_id == mid)
    if scene:
        stmt = stmt.where(LegalAgreement.scene == assert_scene(scene))
    rows, total = paginate(db, stmt.order_by(LegalAgreement.id.desc()), page=page, page_size=page_size)
    names = {
        m.id: m.name
        for m in db.scalars(
            select(Merchant).where(Merchant.id.in_({r.merchant_id for r in rows} or {-1}))
        ).all()
    }
    return PageOut(
        items=[_out(r, names.get(r.merchant_id)) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/scenes")
def list_scenes(ctx: RequestContext = Depends(get_current_context)):
    """场景下拉：须写在 /{id} 之前，避免被路径参数吞掉。"""
    ctx.require_permission("org:read", "org:write")
    return [{"code": s, "name": _SCENE_LABELS[s]} for s in AGREEMENT_SCENES]


@router.post("", response_model=AgreementOut)
def create_agreement(
    body: AgreementIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("org:write")
    mid = ctx.resolve_merchant_id(body.merchant_id)
    merchant = require_merchant_in_site(db, merchant_id=mid, site_id=ctx.site_id)
    scene = assert_scene(body.scene)
    title = body.title.strip()
    content = sanitize_agreement_html(body.content)
    if not title or not content:
        raise AppError("validation_error", "请填写协议标题和正文", status_code=422)
    row = LegalAgreement(
        site_id=ctx.site_id,
        merchant_id=merchant.id,
        scene=scene,
        title=title,
        content=content,
        is_enabled=body.is_enabled,
        updated_by_staff_id=ctx.staff.id,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise AppError("conflict", "该商户该场景已有协议，请直接编辑", status_code=409) from exc
    write_audit(
        db,
        action="agreement.create",
        target_type="legal_agreement",
        target_id=row.id,
        summary=f"创建协议 {scene} merchant={merchant.id}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=merchant.id,
    )
    db.commit()
    db.refresh(row)
    return _out(row, merchant.name)


@router.patch("/{agreement_id}", response_model=AgreementOut)
def patch_agreement(
    agreement_id: int,
    body: AgreementPatch,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("org:write")
    row = _load(db, ctx, agreement_id)
    if body.title is not None:
        title = body.title.strip()
        if not title:
            raise AppError("validation_error", "请填写协议标题", status_code=422)
        row.title = title
    if body.content is not None:
        content = sanitize_agreement_html(body.content)
        if not content:
            raise AppError("validation_error", "请填写协议正文", status_code=422)
        row.content = content
    if body.is_enabled is not None:
        row.is_enabled = body.is_enabled
    row.updated_by_staff_id = ctx.staff.id
    write_audit(
        db,
        action="agreement.update",
        target_type="legal_agreement",
        target_id=row.id,
        summary=f"更新协议 {row.scene} merchant={row.merchant_id}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=row.merchant_id,
    )
    db.commit()
    db.refresh(row)
    merchant = db.get(Merchant, row.merchant_id)
    return _out(row, merchant.name if merchant else None)
