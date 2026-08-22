"""员工自助：查看本人销售/教练提成、提现申请与进度。"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import false, or_, select
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
from app.systems.gym.services.coach_member import coach_promotion_code, reassign_coach_commission_to_member
from app.systems.gym.services.sales_member import reassign_sales_commission_to_member
from app.systems.gym.services.self_commission import (
    SelfCommissionIdentity,
    debt_amount,
    resolve_self_commission_identity,
    self_record_clause,
    settleable_records,
    withdrawing_amount,
)
from app.systems.platform.models.member import Member
from app.systems.platform.models.payout import Payout, PayoutSource, PayoutStatus
from app.systems.platform.api.payouts import PayoutOut, payout_out
from app.systems.platform.services.payouts import create_commission_payout
from app.systems.platform.services.promotion import money

router = APIRouter(prefix="/my", tags=["self-commission"])


class CoachProfileSlice(BaseModel):
    coach_id: int
    merchant_id: int
    member_id: int | None
    promotion_code: str | None = None
    display_name: str
    title: str | None
    hourly_rate: Decimal | None
    pt_commission_rate: Decimal | None
    is_active: bool


class SalesProfileSlice(BaseModel):
    sales_rep_id: int
    merchant_id: int
    member_id: int
    promotion_code: str | None = None
    display_name: str
    is_active: bool


class CommissionProfileOut(BaseModel):
    display_name: str
    roles: list[str]
    coach: CoachProfileSlice | None = None
    sales_rep: SalesProfileSlice | None = None


class CoachProfileOut(CoachProfileSlice):
    """兼容旧前端/测试。"""


class CommissionRecordOut(BaseModel):
    id: int
    merchant_id: int
    scope: str
    category: str
    source_type: str
    source_id: int
    order_id: int | None
    coach_id: int | None = None
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
    display_name: str
    roles: list[str]
    coach_id: int | None = None
    pending_amount: Decimal
    confirmed_amount: Decimal
    paid_amount: Decimal
    total_amount: Decimal
    settleable_amount: Decimal
    settleable_count: int
    withdrawing_amount: Decimal
    debt_amount: Decimal = Decimal("0.00")
    settle_hold_days: int = 0
    by_scope: list[CommissionScopeRow]


class PayoutRequestIn(BaseModel):
    record_ids: list[int] | None = None
    note: str | None = Field(default=None, max_length=255)


def _resolve_identity(db: Session, ctx: RequestContext) -> SelfCommissionIdentity:
    return resolve_self_commission_identity(db, ctx.staff.id)


def _coach_slice(db: Session, coach: Coach) -> CoachProfileSlice:
    return CoachProfileSlice(
        coach_id=coach.id,
        merchant_id=coach.merchant_id,
        member_id=coach.member_id,
        promotion_code=coach_promotion_code(db, coach),
        display_name=coach.display_name,
        title=coach.title,
        hourly_rate=coach.hourly_rate,
        pt_commission_rate=coach.pt_commission_rate,
        is_active=coach.is_active,
    )


def _sales_slice(db: Session, identity: SelfCommissionIdentity) -> SalesProfileSlice:
    rep = identity.sales_rep
    assert rep is not None
    promo = None
    member = db.get(Member, rep.member_id)
    if member is not None:
        from app.systems.platform.services.promotion import member_promoter_code

        row = member_promoter_code(db, member)
        promo = row.code if row is not None else None
    return SalesProfileSlice(
        sales_rep_id=rep.id,
        merchant_id=rep.merchant_id,
        member_id=rep.member_id,
        promotion_code=promo,
        display_name=rep.display_name,
        is_active=rep.is_active,
    )


def _migrate_pending_beneficiary(db: Session, identity: SelfCommissionIdentity) -> None:
    """提现前把仍挂在 staff/coach 档案上的未结算记录迁到绑定会员。"""
    if identity.coach is not None and identity.coach.member_id is not None:
        member = db.get(Member, identity.coach.member_id)
        if member is not None:
            reassign_coach_commission_to_member(db, coach=identity.coach, member=member)
    if identity.sales_rep is not None and identity.sales_rep.member_id is not None:
        member = db.get(Member, identity.sales_rep.member_id)
        if member is not None:
            reassign_sales_commission_to_member(db, sales_rep=identity.sales_rep, member=member)


def _day_bounds(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    start = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
    end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
    return start, end


@router.get("/commission-profile", response_model=CommissionProfileOut)
def my_commission_profile(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("commission:self", "commission:read", "commission:manage")
    identity = _resolve_identity(db, ctx)
    return CommissionProfileOut(
        display_name=identity.display_name,
        roles=identity.roles,
        coach=_coach_slice(db, identity.coach) if identity.coach is not None else None,
        sales_rep=_sales_slice(db, identity) if identity.sales_rep is not None else None,
    )


@router.get("/coach-profile", response_model=CoachProfileOut)
def my_coach_profile(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """兼容旧接口：仅教练档案时可用。"""
    ctx.require_permission("commission:self", "commission:read", "commission:manage")
    identity = _resolve_identity(db, ctx)
    if identity.coach is None:
        raise AppError("not_found", "当前账号未绑定教练档案", status_code=404)
    return _coach_slice(db, identity.coach)


@router.get("/commission-summary", response_model=CommissionSummaryOut)
def my_commission_summary(
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """本人佣金汇总与可提现额度（销售开单 + 教练课时）。"""
    ctx.require_permission("commission:self", "commission:read", "commission:manage")
    identity = _resolve_identity(db, ctx)
    stmt = select(CommissionRecord).where(
        self_record_clause(identity),
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

    records = settleable_records(db, identity)
    from app.systems.gym.services.commission_policy import settle_hold_days, site_id_of_merchant

    site_id = site_id_of_merchant(db, identity.merchant_id or 0)
    hold_days = settle_hold_days(db, site_id)

    return CommissionSummaryOut(
        display_name=identity.display_name,
        roles=identity.roles,
        coach_id=identity.coach.id if identity.coach is not None else None,
        pending_amount=pending,
        confirmed_amount=confirmed,
        paid_amount=paid,
        total_amount=pending + confirmed + paid,
        settleable_amount=sum((money(r.amount) for r in records), Decimal("0.00")),
        settleable_count=len(records),
        withdrawing_amount=withdrawing_amount(db, identity),
        debt_amount=debt_amount(db, identity),
        settle_hold_days=hold_days,
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
    identity = _resolve_identity(db, ctx)
    stmt = select(CommissionRecord).where(self_record_clause(identity))
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
            category=r.category,
            source_type=r.source_type,
            source_id=r.source_id,
            order_id=r.order_id,
            coach_id=r.coach_id,
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
    identity = _resolve_identity(db, ctx)
    clauses = []
    for btype, bid, _name in identity.beneficiaries():
        clauses.append((Payout.beneficiary_type == btype) & (Payout.beneficiary_id == bid))
    if identity.coach is not None:
        clauses.append(
            (Payout.beneficiary_type == BeneficiaryType.COACH.value)
            & (Payout.beneficiary_id == identity.coach.id)
        )
    stmt = select(Payout).where(
        Payout.source == PayoutSource.COMMISSION.value,
        or_(*clauses) if clauses else false(),
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
    """本人申请提现，等待后台审核并线下打款。"""
    ctx.require_permission("commission:self")
    identity = _resolve_identity(db, ctx)
    _migrate_pending_beneficiary(db, identity)

    candidates = settleable_records(db, identity)
    record_ids = body.record_ids
    if record_ids:
        wanted = set(record_ids)
        picked = [r for r in candidates if r.id in wanted]
        if len(picked) != len(wanted):
            raise AppError("invalid_records", "存在不可提现的提成记录", status_code=400)
        candidates = picked

    if not candidates:
        raise AppError("no_settleable_records", "没有可提现的已确认提成", status_code=400)

    grouped: dict[tuple[str, int], list[CommissionRecord]] = {}
    for row in candidates:
        key = (row.beneficiary_type, row.beneficiary_id)
        grouped.setdefault(key, []).append(row)

    payout: Payout | None = None
    created_ids: list[int] = []
    for (btype, bid), rows in grouped.items():
        name = rows[0].beneficiary_name or identity.display_name
        payout = create_commission_payout(
            db,
            site_id=ctx.site_id,
            beneficiary_type=btype,
            beneficiary_id=bid,
            beneficiary_name=name,
            merchant_id=identity.merchant_id or rows[0].merchant_id,
            record_ids=[r.id for r in rows],
            note=body.note,
            requested_by_staff_id=ctx.staff.id,
        )
        created_ids.append(payout.id)
    assert payout is not None
    db.commit()
    db.refresh(payout)
    out = payout_out(db, payout)
    if len(created_ids) > 1:
        out.note = f"{out.note or ''}（共 {len(created_ids)} 张提现单）".strip()
    return out
