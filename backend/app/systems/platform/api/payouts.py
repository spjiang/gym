"""提现单据：审核与线下打款登记（教练佣金 / 会员返点）。"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import RequestContext, get_current_context
from app.core.errors import AppError
from app.core.schemas.paging import PageOut, paginate
from app.systems.gym.models.commission import BeneficiaryType
from app.systems.gym.models.course import Coach
from app.systems.platform.models.identity import StaffUser
from app.systems.platform.models.member import Member
from app.systems.platform.models.payout import (
    Payout,
    PayoutItem,
    PayoutSource,
    PayoutStatus,
)
from app.systems.platform.services.payouts import (
    approve_payout,
    create_commission_payout,
    create_rebate_payout,
    mark_payout_paid,
    reject_payout,
    settleable_records,
)
from app.systems.platform.services.promotion import money

router = APIRouter(tags=["payout"])


class PayoutCreateIn(BaseModel):
    source: str = PayoutSource.COMMISSION.value
    beneficiary_type: str | None = None
    beneficiary_id: int
    merchant_id: int | None = None
    # 佣金提现：留空表示结算全部可提现记录
    record_ids: list[int] | None = None
    # 返点提现必填
    amount: Decimal | None = None
    note: str | None = Field(default=None, max_length=255)


class PayoutPayIn(BaseModel):
    method: str = "offline_transfer"
    external_ref: str | None = Field(default=None, max_length=64)
    note: str | None = Field(default=None, max_length=255)


class PayoutRejectIn(BaseModel):
    reason: str | None = Field(default=None, max_length=255)


class PayoutItemOut(BaseModel):
    commission_record_id: int
    amount: Decimal


class PayoutOut(BaseModel):
    id: int
    site_id: int
    merchant_id: int | None
    source: str
    beneficiary_type: str
    beneficiary_id: int
    beneficiary_name: str
    amount: Decimal
    status: str
    method: str | None
    external_ref: str | None
    note: str | None
    reject_reason: str | None
    requested_by_staff_id: int | None
    requested_by_member_id: int | None
    reviewed_at: datetime | None
    paid_at: datetime | None
    created_at: datetime
    item_count: int = 0


class SettleablePreviewOut(BaseModel):
    beneficiary_type: str
    beneficiary_id: int
    record_count: int
    total_amount: Decimal


def _day_bounds(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    start = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
    end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
    return start, end


def payout_out(db: Session, row: Payout) -> PayoutOut:
    item_count = len(
        list(db.scalars(select(PayoutItem.id).where(PayoutItem.payout_id == row.id)).all())
    )
    return PayoutOut(
        id=row.id,
        site_id=row.site_id,
        merchant_id=row.merchant_id,
        source=row.source,
        beneficiary_type=row.beneficiary_type,
        beneficiary_id=row.beneficiary_id,
        beneficiary_name=row.beneficiary_name,
        amount=money(row.amount),
        status=row.status,
        method=row.method,
        external_ref=row.external_ref,
        note=row.note,
        reject_reason=row.reject_reason,
        requested_by_staff_id=row.requested_by_staff_id,
        requested_by_member_id=row.requested_by_member_id,
        reviewed_at=row.reviewed_at,
        paid_at=row.paid_at,
        created_at=row.created_at,
        item_count=item_count,
    )


def _load_payout(db: Session, ctx: RequestContext, payout_id: int) -> Payout:
    payout = db.get(Payout, payout_id)
    if payout is None or payout.site_id != ctx.site_id:
        raise AppError("not_found", "提现单不存在", status_code=404)
    if payout.merchant_id is not None and not ctx.is_site_admin:
        ctx.resolve_merchant_id(payout.merchant_id)
    elif payout.merchant_id is None and not ctx.is_site_admin:
        raise AppError("forbidden", "场地级提现单仅超管可处理", status_code=403)
    return payout


def _beneficiary_name(db: Session, beneficiary_type: str, beneficiary_id: int) -> str:
    if beneficiary_type == BeneficiaryType.COACH.value:
        coach = db.get(Coach, beneficiary_id)
        if coach is None:
            raise AppError("not_found", "教练不存在", status_code=404)
        return coach.display_name
    if beneficiary_type == BeneficiaryType.STAFF.value:
        staff = db.get(StaffUser, beneficiary_id)
        if staff is None:
            raise AppError("not_found", "员工不存在", status_code=404)
        return staff.display_name
    member = db.get(Member, beneficiary_id)
    if member is None:
        raise AppError("not_found", "会员不存在", status_code=404)
    return f"{member.name} {member.phone}"


@router.get("/payouts", response_model=PageOut[PayoutOut])
def list_payouts(
    source: str | None = None,
    status: str | None = None,
    beneficiary_type: str | None = None,
    beneficiary_id: int | None = None,
    merchant_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("payout:read", "payout:manage")
    stmt = select(Payout).where(Payout.site_id == ctx.site_id)
    mid = ctx.resolve_merchant_id(merchant_id, required=False)
    if not ctx.is_site_admin:
        stmt = stmt.where(Payout.merchant_id == mid)
    elif mid is not None:
        stmt = stmt.where(Payout.merchant_id == mid)
    if source:
        stmt = stmt.where(Payout.source == source)
    if status:
        stmt = stmt.where(Payout.status == status)
    if beneficiary_type:
        stmt = stmt.where(Payout.beneficiary_type == beneficiary_type)
    if beneficiary_id is not None:
        stmt = stmt.where(Payout.beneficiary_id == beneficiary_id)
    if date_from is not None and date_to is not None:
        start, end = _day_bounds(date_from, date_to)
        stmt = stmt.where(Payout.created_at >= start, Payout.created_at < end)
    rows, total = paginate(db, stmt.order_by(Payout.id.desc()), page=page, page_size=page_size)
    return PageOut(
        items=[payout_out(db, r) for r in rows], total=total, page=page, page_size=page_size
    )


@router.get("/payouts/settleable", response_model=SettleablePreviewOut)
def preview_settleable(
    beneficiary_type: str,
    beneficiary_id: int,
    merchant_id: int | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """可提现的已确认提成汇总。"""
    ctx.require_permission("payout:read", "payout:manage")
    mid = ctx.resolve_merchant_id(merchant_id, required=False)
    records = settleable_records(
        db, beneficiary_type=beneficiary_type, beneficiary_id=beneficiary_id, merchant_id=mid
    )
    return SettleablePreviewOut(
        beneficiary_type=beneficiary_type,
        beneficiary_id=beneficiary_id,
        record_count=len(records),
        total_amount=sum((money(r.amount) for r in records), Decimal("0.00")),
    )


@router.post("/payouts", response_model=PayoutOut)
def create_payout(
    body: PayoutCreateIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """后台代为发起提现申请。"""
    ctx.require_permission("payout:manage")
    if body.source == PayoutSource.REBATE.value:
        if body.amount is None:
            raise AppError("validation_error", "返点提现需填写金额", status_code=422)
        member = db.get(Member, body.beneficiary_id)
        if member is None or member.site_id != ctx.site_id:
            raise AppError("not_found", "会员不存在", status_code=404)
        payout = create_rebate_payout(
            db,
            member=member,
            amount=body.amount,
            note=body.note,
            requested_by_staff_id=ctx.staff.id,
        )
    elif body.source == PayoutSource.COMMISSION.value:
        beneficiary_type = body.beneficiary_type or BeneficiaryType.MEMBER.value
        if beneficiary_type not in {
            BeneficiaryType.COACH.value,
            BeneficiaryType.STAFF.value,
            BeneficiaryType.MEMBER.value,
        }:
            raise AppError("invalid_beneficiary", "佣金提现受益人须为教练、员工或会员", status_code=400)
        mid = ctx.resolve_merchant_id(body.merchant_id, required=False)
        payout = create_commission_payout(
            db,
            site_id=ctx.site_id,
            beneficiary_type=beneficiary_type,
            beneficiary_id=body.beneficiary_id,
            beneficiary_name=_beneficiary_name(db, beneficiary_type, body.beneficiary_id),
            merchant_id=mid,
            record_ids=body.record_ids,
            note=body.note,
            requested_by_staff_id=ctx.staff.id,
        )
    else:
        raise AppError("invalid_source", "未知提现来源", status_code=400)
    db.commit()
    db.refresh(payout)
    return payout_out(db, payout)


@router.post("/payouts/{payout_id}/approve", response_model=PayoutOut)
def approve(
    payout_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("payout:manage")
    payout = _load_payout(db, ctx, payout_id)
    approve_payout(db, payout, actor_staff_id=ctx.staff.id)
    db.commit()
    db.refresh(payout)
    return payout_out(db, payout)


@router.post("/payouts/{payout_id}/reject", response_model=PayoutOut)
def reject(
    payout_id: int,
    body: PayoutRejectIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("payout:manage")
    payout = _load_payout(db, ctx, payout_id)
    reject_payout(db, payout, reason=body.reason, actor_staff_id=ctx.staff.id)
    db.commit()
    db.refresh(payout)
    return payout_out(db, payout)


@router.post("/payouts/{payout_id}/pay", response_model=PayoutOut)
def pay(
    payout_id: int,
    body: PayoutPayIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """线下打款完成后登记，回写提成状态或返点账户。"""
    ctx.require_permission("payout:manage")
    payout = _load_payout(db, ctx, payout_id)
    if payout.status == PayoutStatus.REQUESTED.value:
        approve_payout(db, payout, actor_staff_id=ctx.staff.id)
    mark_payout_paid(
        db,
        payout,
        method=body.method,
        external_ref=body.external_ref,
        note=body.note,
        actor_staff_id=ctx.staff.id,
    )
    db.commit()
    db.refresh(payout)
    return payout_out(db, payout)
