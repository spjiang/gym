"""教练自助：查看本人佣金、提现申请与提现进度。

数据严格限定在登录账号绑定的教练本人，避免看到同商户其他教练的收入。
"""

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
from app.systems.gym.models.commission import (
    BeneficiaryType,
    CommissionRecord,
    CommissionStatus,
)
from app.systems.gym.models.course import Coach
from app.systems.platform.models.payout import Payout, PayoutSource, PayoutStatus
from app.systems.platform.api.payouts import PayoutOut, payout_out
from app.systems.platform.services.payouts import create_commission_payout, settleable_records
from app.systems.platform.services.promotion import money

router = APIRouter(prefix="/my", tags=["coach-self"])


class CoachProfileOut(BaseModel):
    coach_id: int
    merchant_id: int
    display_name: str
    title: str | None
    hourly_rate: Decimal | None
    pt_commission_rate: Decimal | None
    is_active: bool


class CommissionRecordOut(BaseModel):
    id: int
    merchant_id: int
    scope: str
    source_type: str
    source_id: int
    order_id: int | None
    base_amount: Decimal
    quantity: int | None
    rate: Decimal | None
    amount: Decimal
    status: str
    note: str | None
    settled_at: datetime | None
    created_at: datetime


class CommissionScopeRow(BaseModel):
    scope: str
    count: int
    amount: Decimal


class CommissionSummaryOut(BaseModel):
    coach_id: int
    display_name: str
    pending_amount: Decimal
    confirmed_amount: Decimal
    paid_amount: Decimal
    total_amount: Decimal
    settleable_amount: Decimal
    settleable_count: int
    withdrawing_amount: Decimal
    by_scope: list[CommissionScopeRow]


class PayoutRequestIn(BaseModel):
    record_ids: list[int] | None = None
    note: str | None = Field(default=None, max_length=255)


def _own_coach(db: Session, ctx: RequestContext) -> Coach:
    coach = db.scalar(select(Coach).where(Coach.staff_user_id == ctx.staff.id))
    if coach is None:
        raise AppError("not_found", "当前账号未绑定教练档案", status_code=404)
    return coach


def _day_bounds(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    start = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
    end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
    return start, end


@router.get("/coach-profile", response_model=CoachProfileOut)
def my_coach_profile(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("commission:self", "commission:read", "commission:manage")
    coach = _own_coach(db, ctx)
    return CoachProfileOut(
        coach_id=coach.id,
        merchant_id=coach.merchant_id,
        display_name=coach.display_name,
        title=coach.title,
        hourly_rate=coach.hourly_rate,
        pt_commission_rate=coach.pt_commission_rate,
        is_active=coach.is_active,
    )


@router.get("/commission-summary", response_model=CommissionSummaryOut)
def my_commission_summary(
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """本人佣金汇总与可提现额度。"""
    ctx.require_permission("commission:self", "commission:read", "commission:manage")
    coach = _own_coach(db, ctx)
    stmt = select(CommissionRecord).where(
        CommissionRecord.beneficiary_type == BeneficiaryType.COACH.value,
        CommissionRecord.beneficiary_id == coach.id,
        CommissionRecord.status != CommissionStatus.VOID.value,
    )
    if date_from is not None and date_to is not None:
        start, end = _day_bounds(date_from, date_to)
        stmt = stmt.where(CommissionRecord.created_at >= start, CommissionRecord.created_at < end)

    pending = confirmed = paid = Decimal("0.00")
    scope_map: dict[str, tuple[int, Decimal]] = {}
    for row in db.scalars(stmt).all():
        amount = money(row.amount)
        if row.status == CommissionStatus.PENDING.value:
            pending += amount
        elif row.status == CommissionStatus.CONFIRMED.value:
            confirmed += amount
        elif row.status == CommissionStatus.PAID.value:
            paid += amount
        count, total = scope_map.get(row.scope, (0, Decimal("0.00")))
        scope_map[row.scope] = (count + 1, total + amount)

    records = settleable_records(
        db, beneficiary_type=BeneficiaryType.COACH.value, beneficiary_id=coach.id
    )
    withdrawing = Decimal("0.00")
    for row in db.scalars(
        select(Payout).where(
            Payout.source == PayoutSource.COMMISSION.value,
            Payout.beneficiary_type == BeneficiaryType.COACH.value,
            Payout.beneficiary_id == coach.id,
            Payout.status.in_([PayoutStatus.REQUESTED.value, PayoutStatus.APPROVED.value]),
        )
    ).all():
        withdrawing += money(row.amount)

    return CommissionSummaryOut(
        coach_id=coach.id,
        display_name=coach.display_name,
        pending_amount=pending,
        confirmed_amount=confirmed,
        paid_amount=paid,
        total_amount=pending + confirmed + paid,
        settleable_amount=sum((money(r.amount) for r in records), Decimal("0.00")),
        settleable_count=len(records),
        withdrawing_amount=withdrawing,
        by_scope=[
            CommissionScopeRow(scope=scope, count=count, amount=total)
            for scope, (count, total) in sorted(scope_map.items())
        ],
    )


@router.get("/commission-records", response_model=PageOut[CommissionRecordOut])
def my_commission_records(
    status: str | None = None,
    scope: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("commission:self", "commission:read", "commission:manage")
    coach = _own_coach(db, ctx)
    stmt = select(CommissionRecord).where(
        CommissionRecord.beneficiary_type == BeneficiaryType.COACH.value,
        CommissionRecord.beneficiary_id == coach.id,
    )
    if status:
        stmt = stmt.where(CommissionRecord.status == status)
    if scope:
        stmt = stmt.where(CommissionRecord.scope == scope)
    if date_from is not None and date_to is not None:
        start, end = _day_bounds(date_from, date_to)
        stmt = stmt.where(CommissionRecord.created_at >= start, CommissionRecord.created_at < end)
    rows, total = paginate(
        db, stmt.order_by(CommissionRecord.id.desc()), page=page, page_size=page_size
    )
    items = [
        CommissionRecordOut(
            id=r.id,
            merchant_id=r.merchant_id,
            scope=r.scope,
            source_type=r.source_type,
            source_id=r.source_id,
            order_id=r.order_id,
            base_amount=money(r.base_amount),
            quantity=r.quantity,
            rate=r.rate,
            amount=money(r.amount),
            status=r.status,
            note=r.note,
            settled_at=r.settled_at,
            created_at=r.created_at,
        )
        for r in rows
    ]
    return PageOut(items=items, total=total, page=page, page_size=page_size)


@router.get("/payouts", response_model=PageOut[PayoutOut])
def my_payouts(
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("commission:self", "commission:read", "commission:manage")
    coach = _own_coach(db, ctx)
    stmt = select(Payout).where(
        Payout.source == PayoutSource.COMMISSION.value,
        Payout.beneficiary_type == BeneficiaryType.COACH.value,
        Payout.beneficiary_id == coach.id,
    )
    if status:
        stmt = stmt.where(Payout.status == status)
    rows, total = paginate(db, stmt.order_by(Payout.id.desc()), page=page, page_size=page_size)
    return PageOut(
        items=[payout_out(db, r) for r in rows], total=total, page=page, page_size=page_size
    )


@router.post("/payouts", response_model=PayoutOut)
def request_my_payout(
    body: PayoutRequestIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """教练本人申请提现，等待后台审核并线下打款。"""
    ctx.require_permission("commission:self", "commission:read", "commission:manage")
    coach = _own_coach(db, ctx)
    payout = create_commission_payout(
        db,
        site_id=ctx.site_id,
        beneficiary_type=BeneficiaryType.COACH.value,
        beneficiary_id=coach.id,
        beneficiary_name=coach.display_name,
        merchant_id=coach.merchant_id,
        record_ids=body.record_ids,
        note=body.note,
        requested_by_staff_id=ctx.staff.id,
    )
    db.commit()
    db.refresh(payout)
    return payout_out(db, payout)
