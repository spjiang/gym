"""会员端「我的推广」：推广码与链接、下级会员、返点余额与提现。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import MemberContext, get_current_member
from app.core.errors import AppError
from app.core.schemas.paging import PageOut, paginate
from app.systems.platform.models.commerce import Order, OrderStatus
from app.systems.platform.models.member import Member
from app.systems.platform.models.payout import Payout, PayoutSource, PayoutStatus
from app.systems.platform.models.rebate import MemberRebateLedger, RebateLedgerKind
from app.systems.platform.services.payouts import create_rebate_payout, has_open_rebate_payout
from app.systems.platform.services.promotion import (
    count_downline,
    downline_query,
    ensure_member_promoter_code,
    member_promoter_code,
    money,
    rate_of,
    resolve_promotion_settings,
    resolve_upline,
)
from app.systems.platform.services.rebate import get_account, held_rebate_amount, snapshot

router = APIRouter(prefix="/member/promotion", tags=["member-promotion"])


class MyPromotionOut(BaseModel):
    code: str | None
    link: str | None
    is_active: bool
    rebate_rate: Decimal
    downline_discount_rate: Decimal
    downline_count: int
    visit_count: int
    upline_name: str | None
    # 我作为下级可享受的折扣（来自上级配置）
    my_discount_rate: Decimal
    balance: Decimal
    frozen_amount: Decimal
    total_earned: Decimal
    total_withdrawn: Decimal
    min_withdraw_amount: Decimal
    withdraw_hold_days: int
    held_amount: Decimal
    available_balance: Decimal
    payout_in_progress: bool = False


class MyDownlineOut(BaseModel):
    name: str
    phone_masked: str
    joined_at: datetime
    paid_amount: Decimal
    rebate_amount: Decimal


class MyLedgerOut(BaseModel):
    id: int
    kind: str
    amount: Decimal
    balance_after: Decimal
    from_member_name: str | None
    note: str | None
    created_at: datetime


class WithdrawIn(BaseModel):
    amount: Decimal = Field(gt=0)
    note: str | None = Field(default=None, max_length=255)


class MyPayoutOut(BaseModel):
    id: int
    amount: Decimal
    status: str
    method: str | None
    reject_reason: str | None
    created_at: datetime
    paid_at: datetime | None


def _mask_phone(phone: str) -> str:
    if len(phone) < 7:
        return phone
    return f"{phone[:3]}****{phone[-4:]}"


def _mask_name(name: str) -> str:
    if not name:
        return name
    if len(name) == 1:
        return name
    return f"{name[0]}{'*' * (len(name) - 1)}"


@router.get("", response_model=MyPromotionOut)
def my_promotion(
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    """我的推广码、返点余额与上级折扣。"""
    member = mctx.member
    promoter = ensure_member_promoter_code(db, member)
    settings = resolve_promotion_settings(db, member.site_id)
    upline = resolve_upline(db, member)
    account = get_account(db, member=member, create=False)
    snap = snapshot(
        account,
        held_amount=held_rebate_amount(
            db, member_id=member.id, hold_days=settings.withdraw_hold_days
        ),
    )
    db.commit()

    link = None
    if promoter is not None:
        base = get_settings().member_web_public_url.rstrip("/")
        path = (promoter.landing_path or "/login").strip()
        if not path.startswith("/"):
            path = f"/{path}"
        sep = "&" if "?" in path else "?"
        link = f"{base}{path}{sep}promoter={promoter.code}"

    return MyPromotionOut(
        code=promoter.code if promoter else None,
        link=link,
        is_active=bool(promoter.is_active) if promoter else False,
        rebate_rate=rate_of(
            promoter.rebate_rate
            if promoter is not None and promoter.rebate_rate is not None
            else settings.default_rebate_rate
        ),
        downline_discount_rate=rate_of(
            promoter.downline_discount_rate
            if promoter is not None and promoter.downline_discount_rate is not None
            else settings.default_downline_discount_rate
        ),
        downline_count=count_downline(db, member=member),
        visit_count=promoter.visit_count if promoter else 0,
        upline_name=_mask_name(upline.member_name) if upline else None,
        my_discount_rate=upline.discount_rate if upline else Decimal("0"),
        balance=snap.available_balance,
        frozen_amount=snap.frozen_amount,
        total_earned=snap.total_earned,
        total_withdrawn=snap.total_withdrawn,
        min_withdraw_amount=settings.min_withdraw_amount,
        withdraw_hold_days=settings.withdraw_hold_days,
        held_amount=snap.held_amount,
        available_balance=snap.available_balance,
        payout_in_progress=has_open_rebate_payout(db, member.id),
    )


@router.get("/downline", response_model=PageOut[MyDownlineOut])
def my_downline(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    """我的一级下级（脱敏展示）。"""
    member = mctx.member
    rows, total = paginate(db, downline_query(db, member=member), page=page, page_size=page_size)
    items: list[MyDownlineOut] = []
    for row in rows:
        paid = db.scalar(
            select(func.coalesce(func.sum(Order.amount), 0)).where(
                Order.member_id == row.id, Order.status == OrderStatus.PAID.value
            )
        )
        rebate_total = Decimal("0.00")
        for ledger in db.scalars(
            select(MemberRebateLedger).where(
                MemberRebateLedger.member_id == member.id,
                MemberRebateLedger.from_member_id == row.id,
                MemberRebateLedger.kind.in_(
                    [RebateLedgerKind.EARN.value, RebateLedgerKind.REVERSE.value]
                ),
            )
        ).all():
            rebate_total += money(ledger.amount)
        items.append(
            MyDownlineOut(
                name=_mask_name(row.name),
                phone_masked=_mask_phone(row.phone),
                joined_at=row.created_at,
                paid_amount=money(paid or 0),
                rebate_amount=rebate_total,
            )
        )
    return PageOut(items=items, total=total, page=page, page_size=page_size)


@router.get("/ledgers", response_model=PageOut[MyLedgerOut])
def my_ledgers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    """我的返点流水。"""
    stmt = select(MemberRebateLedger).where(MemberRebateLedger.member_id == mctx.member.id)
    rows, total = paginate(
        db, stmt.order_by(MemberRebateLedger.id.desc()), page=page, page_size=page_size
    )
    names = {
        m.id: m.name
        for m in db.scalars(
            select(Member).where(
                Member.id.in_({r.from_member_id for r in rows if r.from_member_id} or {-1})
            )
        ).all()
    }
    items = [
        MyLedgerOut(
            id=r.id,
            kind=r.kind,
            amount=money(r.amount),
            balance_after=money(r.balance_after),
            from_member_name=(
                _mask_name(names.get(r.from_member_id, "")) if r.from_member_id else None
            ),
            note=r.note,
            created_at=r.created_at,
        )
        for r in rows
    ]
    return PageOut(items=items, total=total, page=page, page_size=page_size)


@router.get("/withdrawals", response_model=PageOut[MyPayoutOut])
def my_withdrawals(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    stmt = select(Payout).where(
        Payout.source == PayoutSource.REBATE.value,
        Payout.beneficiary_id == mctx.member.id,
    )
    rows, total = paginate(db, stmt.order_by(Payout.id.desc()), page=page, page_size=page_size)
    items = [
        MyPayoutOut(
            id=r.id,
            amount=money(r.amount),
            status=r.status,
            method=r.method,
            reject_reason=r.reject_reason,
            created_at=r.created_at,
            paid_at=r.paid_at,
        )
        for r in rows
    ]
    return PageOut(items=items, total=total, page=page, page_size=page_size)


@router.post("/withdrawals", response_model=MyPayoutOut)
def request_withdraw(
    body: WithdrawIn,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    """申请返点提现，线下打款后由运营登记完成。"""
    from app.systems.platform.services.payouts import has_open_rebate_payout

    member = mctx.member
    if has_open_rebate_payout(db, member.id):
        raise AppError("payout_in_progress", "已有提现在处理中，请等待完成", status_code=400)
    payout = create_rebate_payout(
        db,
        member=member,
        amount=body.amount,
        note=body.note,
        requested_by_member_id=member.id,
    )
    db.commit()
    db.refresh(payout)
    return MyPayoutOut(
        id=payout.id,
        amount=money(payout.amount),
        status=payout.status,
        method=payout.method,
        reject_reason=payout.reject_reason,
        created_at=payout.created_at,
        paid_at=payout.paid_at,
    )
