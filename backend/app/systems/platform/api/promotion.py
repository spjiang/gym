"""综合运营平台：会员推广配置、上下级关系与返点账户。"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.member_web_url import build_promoter_link
from app.core.db import get_db
from app.core.deps import RequestContext, get_current_context
from app.core.errors import AppError
from app.core.merchant_scope import assert_member_in_scope
from app.core.schemas.paging import PageOut, paginate
from app.systems.platform.models.commerce import Order, OrderStatus
from app.systems.platform.models.member import Member, MerchantMember
from app.systems.platform.models.promoter import PromoterCode
from app.systems.platform.models.rebate import MemberRebateLedger, RebateLedgerKind
from app.systems.platform.services.audit import write_audit
from app.systems.platform.services.promotion import (
    count_downline,
    downline_query,
    ensure_member_promoter_code,
    get_or_create_settings_row,
    member_promoter_code,
    money,
    rate_of,
    resolve_promotion_settings,
    resolve_upline,
    validate_discount_rate,
    validate_rebate_rate,
)
from app.systems.platform.services.rebate import (
    adjust_balance,
    get_account,
    held_rebate_amount,
    snapshot,
)

router = APIRouter(tags=["promotion"])


class PromotionSettingsIn(BaseModel):
    auto_create_member_code: bool | None = None
    default_rebate_rate: Decimal | None = None
    default_downline_discount_rate: Decimal | None = None
    min_withdraw_amount: Decimal | None = Field(default=None, ge=0)
    withdraw_hold_days: int | None = Field(default=None, ge=0, le=365)
    remark: str | None = Field(default=None, max_length=255)


class PromotionSettingsOut(BaseModel):
    site_id: int
    auto_create_member_code: bool
    default_rebate_rate: Decimal
    default_downline_discount_rate: Decimal
    min_withdraw_amount: Decimal
    withdraw_hold_days: int
    configured: bool


class MemberPromotionPatch(BaseModel):
    rebate_rate: Decimal | None = None
    downline_discount_rate: Decimal | None = None
    is_active: bool | None = None
    landing_path: str | None = Field(default=None, max_length=128)


class RebateAccountOut(BaseModel):
    balance: Decimal
    frozen_amount: Decimal
    debt_amount: Decimal
    total_earned: Decimal
    total_withdrawn: Decimal
    held_amount: Decimal = Decimal("0.00")
    available_balance: Decimal = Decimal("0.00")


class MemberPromotionOut(BaseModel):
    member_id: int
    member_name: str
    code: str | None
    name: str | None
    is_active: bool
    landing_path: str | None
    # 生效值（推广位未配置时取场地默认）
    rebate_rate: Decimal
    downline_discount_rate: Decimal
    rebate_rate_override: Decimal | None
    downline_discount_rate_override: Decimal | None
    link: str | None
    visit_count: int
    downline_count: int
    upline_member_id: int | None
    upline_member_name: str | None
    account: RebateAccountOut


class DownlineOut(BaseModel):
    member_id: int
    name: str
    phone: str
    joined_at: datetime
    order_count: int
    paid_amount: Decimal
    rebate_amount: Decimal


class RebateLedgerOut(BaseModel):
    id: int
    member_id: int
    member_name: str | None
    kind: str
    amount: Decimal
    balance_after: Decimal
    merchant_id: int | None
    order_id: int | None
    from_member_id: int | None
    from_member_name: str | None
    base_amount: Decimal | None
    rate: Decimal | None
    note: str | None
    created_at: datetime


class RebateAdjustIn(BaseModel):
    amount: Decimal
    note: str = Field(min_length=1, max_length=255)


_member_in_scope = assert_member_in_scope


def _promoter_link(promoter: PromoterCode | None) -> str | None:
    if promoter is None:
        return None
    return build_promoter_link(
        code=promoter.code,
        landing_path=promoter.landing_path,
        merchant_id=promoter.merchant_id,
    )


def _day_bounds(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    start = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
    end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
    return start, end


def _account_out(snap) -> RebateAccountOut:
    return RebateAccountOut(
        balance=snap.balance,
        frozen_amount=snap.frozen_amount,
        debt_amount=snap.debt_amount,
        total_earned=snap.total_earned,
        total_withdrawn=snap.total_withdrawn,
        held_amount=snap.held_amount,
        available_balance=snap.available_balance,
    )


def _settings_out(settings) -> PromotionSettingsOut:
    return PromotionSettingsOut(
        site_id=settings.site_id,
        auto_create_member_code=settings.auto_create_member_code,
        default_rebate_rate=settings.default_rebate_rate,
        default_downline_discount_rate=settings.default_downline_discount_rate,
        min_withdraw_amount=settings.min_withdraw_amount,
        withdraw_hold_days=settings.withdraw_hold_days,
        configured=settings.configured,
    )


def _member_snap(db: Session, member: Member):
    settings = resolve_promotion_settings(db, member.site_id)
    account = get_account(db, member=member, create=False)
    return snapshot(
        account,
        held_amount=held_rebate_amount(
            db, member_id=member.id, hold_days=settings.withdraw_hold_days
        ),
    )


def _member_promotion_out(db: Session, member: Member) -> MemberPromotionOut:
    promoter = member_promoter_code(db, member)
    settings = resolve_promotion_settings(db, member.site_id)
    upline = resolve_upline(db, member)
    snap = _member_snap(db, member)
    return MemberPromotionOut(
        member_id=member.id,
        member_name=member.name,
        code=promoter.code if promoter else None,
        name=promoter.name if promoter else None,
        is_active=bool(promoter.is_active) if promoter else False,
        landing_path=promoter.landing_path if promoter else None,
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
        rebate_rate_override=(
            rate_of(promoter.rebate_rate)
            if promoter is not None and promoter.rebate_rate is not None
            else None
        ),
        downline_discount_rate_override=(
            rate_of(promoter.downline_discount_rate)
            if promoter is not None and promoter.downline_discount_rate is not None
            else None
        ),
        link=_promoter_link(promoter),
        visit_count=promoter.visit_count if promoter else 0,
        downline_count=count_downline(db, member=member),
        upline_member_id=upline.member_id if upline else None,
        upline_member_name=upline.member_name if upline else None,
        account=_account_out(snap),
    )


@router.get("/promotion-settings", response_model=PromotionSettingsOut)
def get_promotion_settings(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """场地级推广默认配置。"""
    ctx.require_permission("promoter:read", "promoter:manage")
    settings = resolve_promotion_settings(db, ctx.site_id)
    return _settings_out(settings)


@router.put("/promotion-settings", response_model=PromotionSettingsOut)
def update_promotion_settings(
    body: PromotionSettingsIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("promoter:manage")
    row = get_or_create_settings_row(db, ctx.site_id)
    changed = set(body.model_fields_set)
    if "auto_create_member_code" in changed and body.auto_create_member_code is not None:
        row.auto_create_member_code = bool(body.auto_create_member_code)
    if "default_rebate_rate" in changed:
        row.default_rebate_rate = validate_rebate_rate(body.default_rebate_rate) or Decimal("0")
    if "default_downline_discount_rate" in changed:
        row.default_downline_discount_rate = validate_discount_rate(
            body.default_downline_discount_rate
        ) or Decimal("0")
    if "min_withdraw_amount" in changed and body.min_withdraw_amount is not None:
        row.min_withdraw_amount = money(body.min_withdraw_amount)
    if "withdraw_hold_days" in changed and body.withdraw_hold_days is not None:
        row.withdraw_hold_days = int(body.withdraw_hold_days)
    if "remark" in changed:
        row.remark = (body.remark or "").strip() or None
    write_audit(
        db,
        action="promotion.settings_update",
        target_type="site_promotion_settings",
        target_id=row.id,
        summary=(
            f"推广默认配置：返点 {row.default_rebate_rate}，"
            f"下级折扣 {row.default_downline_discount_rate}，"
            f"提现冷却 {row.withdraw_hold_days} 天"
        ),
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
    )
    db.commit()
    settings = resolve_promotion_settings(db, ctx.site_id)
    return _settings_out(settings)


@router.get("/member-promotions", response_model=PageOut[MemberPromotionOut])
def list_member_promotions(
    q: str | None = None,
    has_downline: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """会员推广一览：人人一码、生效比例与返点账户。"""
    ctx.require_permission("promoter:read", "promoter:manage")
    stmt = select(Member).where(Member.site_id == ctx.site_id)
    if not ctx.is_site_wide:
        mid = ctx.resolve_merchant_id()
        member_ids = select(MerchantMember.member_id).where(MerchantMember.merchant_id == mid)
        stmt = stmt.where(Member.id.in_(member_ids))
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(Member.phone.ilike(like), Member.name.ilike(like), Member.referral_code.ilike(like)))
    if has_downline is True:
        downline_ids = select(Member.referrer_member_id).where(Member.referrer_member_id.is_not(None))
        stmt = stmt.where(Member.id.in_(downline_ids))
    elif has_downline is False:
        downline_ids = select(Member.referrer_member_id).where(Member.referrer_member_id.is_not(None))
        stmt = stmt.where(Member.id.not_in(downline_ids))

    rows, total = paginate(db, stmt.order_by(Member.id.desc()), page=page, page_size=page_size)
    return PageOut(
        items=[_member_promotion_out(db, m) for m in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/members/{member_id}/promotion", response_model=MemberPromotionOut)
def get_member_promotion(
    member_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """会员推广信息：推广码、链接、生效比例与返点账户。无码时当场补发。"""
    ctx.require_permission("promoter:read", "promoter:manage")
    member = _member_in_scope(db, ctx, member_id)
    # 运营打开「推广」即视为要看码和二维码；历史会员建档时可能还没有推广位
    ensure_member_promoter_code(db, member, force=True)
    db.commit()
    db.refresh(member)
    return _member_promotion_out(db, member)


@router.patch("/members/{member_id}/promotion", response_model=MemberPromotionOut)
def update_member_promotion(
    member_id: int,
    body: MemberPromotionPatch,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """配置会员推广码的返点比例与下级折扣；无码时自动补码。"""
    ctx.require_permission("promoter:manage")
    member = _member_in_scope(db, ctx, member_id)
    promoter = member_promoter_code(db, member)
    if promoter is None:
        # 手工配置视为显式开通，忽略场地自动建码开关
        get_or_create_settings_row(db, ctx.site_id)
        promoter = ensure_member_promoter_code(db, member, force=True)
    if promoter is None:
        raise AppError("promoter_disabled", "无法为该会员发放推广码", status_code=400)

    changed = set(body.model_fields_set)
    if "rebate_rate" in changed:
        promoter.rebate_rate = validate_rebate_rate(body.rebate_rate)
    if "downline_discount_rate" in changed:
        promoter.downline_discount_rate = validate_discount_rate(body.downline_discount_rate)
    if "is_active" in changed and body.is_active is not None:
        promoter.is_active = bool(body.is_active)
    if "landing_path" in changed:
        promoter.landing_path = (body.landing_path or "").strip() or None

    write_audit(
        db,
        action="promotion.member_config",
        target_type="promoter_code",
        target_id=promoter.id,
        summary=(
            f"配置会员推广 {member.name}：返点 {promoter.rebate_rate}，"
            f"下级折扣 {promoter.downline_discount_rate}，启用 {promoter.is_active}"
        ),
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
    )
    db.commit()
    db.refresh(member)
    return _member_promotion_out(db, member)


@router.get("/members/{member_id}/downline", response_model=PageOut[DownlineOut])
def list_member_downline(
    member_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """会员一级下级列表与各自贡献。"""
    ctx.require_permission("promoter:read", "promoter:manage")
    member = _member_in_scope(db, ctx, member_id)
    rows, total = paginate(db, downline_query(db, member=member), page=page, page_size=page_size)
    items: list[DownlineOut] = []
    for row in rows:
        order_row = db.execute(
            select(func.count(Order.id), func.coalesce(func.sum(Order.amount), 0)).where(
                Order.member_id == row.id, Order.status == OrderStatus.PAID.value
            )
        ).one()
        rebate_total = Decimal("0.00")
        for ledger in db.scalars(
            select(MemberRebateLedger).where(
                MemberRebateLedger.from_member_id == row.id,
                MemberRebateLedger.member_id == member.id,
                MemberRebateLedger.kind.in_(
                    [RebateLedgerKind.EARN.value, RebateLedgerKind.REVERSE.value]
                ),
            )
        ).all():
            rebate_total += money(ledger.amount)
        items.append(
            DownlineOut(
                member_id=row.id,
                name=row.name,
                phone=row.phone,
                joined_at=row.created_at,
                order_count=int(order_row[0] or 0),
                paid_amount=money(order_row[1] or 0),
                rebate_amount=rebate_total,
            )
        )
    return PageOut(items=items, total=total, page=page, page_size=page_size)


@router.get("/rebate-ledgers", response_model=PageOut[RebateLedgerOut])
def list_rebate_ledgers(
    member_id: int | None = None,
    from_member_id: int | None = None,
    kind: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """返点流水。"""
    ctx.require_permission("promoter:read", "promoter:manage")
    stmt = select(MemberRebateLedger).where(MemberRebateLedger.site_id == ctx.site_id)
    if not ctx.is_site_wide:
        mid = ctx.resolve_merchant_id()
        stmt = stmt.where(MemberRebateLedger.merchant_id == mid)
    if member_id is not None:
        stmt = stmt.where(MemberRebateLedger.member_id == member_id)
    if from_member_id is not None:
        stmt = stmt.where(MemberRebateLedger.from_member_id == from_member_id)
    if kind:
        if kind not in {k.value for k in RebateLedgerKind}:
            raise AppError("invalid_kind", "未知流水类型", status_code=400)
        stmt = stmt.where(MemberRebateLedger.kind == kind)
    if date_from is not None and date_to is not None:
        start, end = _day_bounds(date_from, date_to)
        stmt = stmt.where(
            MemberRebateLedger.created_at >= start, MemberRebateLedger.created_at < end
        )

    rows, total = paginate(
        db, stmt.order_by(MemberRebateLedger.id.desc()), page=page, page_size=page_size
    )
    member_ids = {r.member_id for r in rows} | {
        r.from_member_id for r in rows if r.from_member_id is not None
    }
    names = {
        m.id: m.name
        for m in db.scalars(select(Member).where(Member.id.in_(member_ids or {-1}))).all()
    }
    items = [
        RebateLedgerOut(
            id=r.id,
            member_id=r.member_id,
            member_name=names.get(r.member_id),
            kind=r.kind,
            amount=money(r.amount),
            balance_after=money(r.balance_after),
            merchant_id=r.merchant_id,
            order_id=r.order_id,
            from_member_id=r.from_member_id,
            from_member_name=names.get(r.from_member_id) if r.from_member_id else None,
            base_amount=None if r.base_amount is None else money(r.base_amount),
            rate=r.rate,
            note=r.note,
            created_at=r.created_at,
        )
        for r in rows
    ]
    return PageOut(items=items, total=total, page=page, page_size=page_size)


@router.post("/members/{member_id}/rebate-adjust", response_model=RebateAccountOut)
def adjust_member_rebate(
    member_id: int,
    body: RebateAdjustIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """人工调整会员返点余额（补发或扣减）。"""
    ctx.require_permission("promoter:manage")
    member = _member_in_scope(db, ctx, member_id)
    adjust_balance(
        db,
        member=member,
        amount=body.amount,
        note=body.note.strip(),
        actor_staff_id=ctx.staff.id,
    )
    write_audit(
        db,
        action="rebate.adjust",
        target_type="member",
        target_id=member.id,
        summary=f"调整返点余额 {money(body.amount)}：{body.note.strip()}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
    )
    db.commit()
    return _account_out(_member_snap(db, member))
