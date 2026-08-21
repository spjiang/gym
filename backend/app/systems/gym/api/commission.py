"""分成规则、提成记录与业绩汇总 API。"""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import RequestContext, get_current_context
from app.core.domain.subsystems import assert_merchant_has_system
from app.core.errors import AppError
from app.core.schemas.paging import PageOut, paginate
from app.systems.gym.models.commission import (
    CommissionRecord,
    CommissionRule,
    CommissionStatus,
)
from app.systems.gym.services.commission import change_record_status, validate_rule_config
from app.systems.platform.models.commerce import Order, OrderStatus
from app.systems.platform.models.identity import StaffUser
from app.systems.platform.models.org import Merchant
from app.systems.platform.services.audit import write_audit

router = APIRouter(tags=["commission"])


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RuleIn(BaseModel):
    merchant_id: int | None = None
    name: str = Field(min_length=1, max_length=128)
    scope: str
    beneficiary: str
    basis: str
    rate: Decimal | None = None
    unit_amount: Decimal | None = None
    min_base_amount: Decimal | None = None
    max_amount: Decimal | None = None
    first_order_only: bool = False
    priority: int = Field(default=100, ge=1, le=9999)
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    is_active: bool = True
    remark: str | None = Field(default=None, max_length=255)


class RuleOut(ORMModel):
    id: int
    merchant_id: int
    name: str
    scope: str
    beneficiary: str
    basis: str
    rate: Decimal | None
    unit_amount: Decimal | None
    min_base_amount: Decimal | None
    max_amount: Decimal | None
    first_order_only: bool
    priority: int
    effective_from: datetime | None
    effective_to: datetime | None
    is_active: bool
    remark: str | None
    created_at: datetime


class RecordOut(ORMModel):
    id: int
    merchant_id: int
    rule_id: int | None
    rule_name: str | None = None
    scope: str
    category: str
    source_type: str
    source_id: int
    order_id: int | None
    member_id: int | None
    coach_id: int | None = None
    beneficiary_type: str
    beneficiary_id: int
    beneficiary_name: str
    base_amount: Decimal
    quantity: int | None
    rate: Decimal | None
    amount: Decimal
    status: str
    note: str | None
    settled_at: datetime | None
    created_at: datetime


class RecordStatusIn(BaseModel):
    status: str


class RecordBatchIn(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=200)
    status: str


class RecordBatchOut(BaseModel):
    updated: int
    skipped: int


class BeneficiarySummaryRow(BaseModel):
    beneficiary_type: str
    beneficiary_id: int
    beneficiary_name: str
    record_count: int
    pending_amount: Decimal
    confirmed_amount: Decimal
    paid_amount: Decimal
    total_amount: Decimal


class ScopeSummaryRow(BaseModel):
    scope: str
    record_count: int
    total_amount: Decimal


class SellerPerformanceRow(BaseModel):
    staff_id: int
    staff_name: str
    order_count: int
    sales_amount: Decimal
    commission_amount: Decimal


class CommissionSummaryOut(BaseModel):
    date_from: date
    date_to: date
    total_amount: Decimal
    pending_amount: Decimal
    confirmed_amount: Decimal
    paid_amount: Decimal
    by_scope: list[ScopeSummaryRow]
    by_beneficiary: list[BeneficiarySummaryRow]
    sellers: list[SellerPerformanceRow]


def _day_bounds(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    start = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
    end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
    return start, end


def _merchant_scope(ctx: RequestContext, db: Session, merchant_id: int | None) -> list[int] | None:
    """返回可见商户 id 列表；None 表示全场地（超管未指定商户）。"""
    mid = ctx.resolve_merchant_id(merchant_id, required=False)
    if mid is not None:
        return [mid]
    return list(db.scalars(select(Merchant.id).where(Merchant.site_id == ctx.site_id)).all())


@router.get("/commission-rules", response_model=PageOut[RuleOut])
def list_rules(
    merchant_id: int | None = None,
    scope: str | None = None,
    is_active: bool | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("commission:read", "commission:manage")
    mids = _merchant_scope(ctx, db, merchant_id)
    stmt = select(CommissionRule).where(CommissionRule.merchant_id.in_(mids or [-1]))
    if scope:
        stmt = stmt.where(CommissionRule.scope == scope)
    if is_active is not None:
        stmt = stmt.where(CommissionRule.is_active.is_(is_active))
    keyword = (q or "").strip()
    if keyword:
        stmt = stmt.where(CommissionRule.name.ilike(f"%{keyword}%"))
    rows, total = paginate(
        db,
        stmt.order_by(CommissionRule.priority.asc(), CommissionRule.id.desc()),
        page=page,
        page_size=page_size,
    )
    return PageOut(items=list(rows), total=total, page=page, page_size=page_size)


def _validate_effective_range(effective_from: datetime | None, effective_to: datetime | None) -> None:
    if effective_from is not None and effective_to is not None and effective_to <= effective_from:
        raise AppError("invalid_time", "失效时间必须晚于生效时间", status_code=400)


@router.post("/commission-rules", response_model=RuleOut)
def create_rule(
    body: RuleIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("commission:manage")
    mid = ctx.resolve_merchant_id(body.merchant_id)
    merchant = db.get(Merchant, mid)
    if merchant is None or merchant.site_id != ctx.site_id:
        raise AppError("not_found", "商户不存在", status_code=404)
    assert_merchant_has_system(db, mid, "gym")
    validate_rule_config(
        scope=body.scope,
        beneficiary=body.beneficiary,
        basis=body.basis,
        rate=body.rate,
        unit_amount=body.unit_amount,
    )
    _validate_effective_range(body.effective_from, body.effective_to)

    rule = CommissionRule(
        merchant_id=mid,
        name=body.name.strip(),
        scope=body.scope,
        beneficiary=body.beneficiary,
        basis=body.basis,
        rate=body.rate,
        unit_amount=body.unit_amount,
        min_base_amount=body.min_base_amount,
        max_amount=body.max_amount,
        first_order_only=body.first_order_only,
        priority=body.priority,
        effective_from=body.effective_from,
        effective_to=body.effective_to,
        is_active=body.is_active,
        remark=(body.remark or "").strip() or None,
    )
    db.add(rule)
    db.flush()
    write_audit(
        db,
        action="commission_rule.create",
        target_type="commission_rule",
        target_id=rule.id,
        summary=f"创建分成规则 {rule.name}（{rule.scope}）",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=mid,
    )
    db.commit()
    db.refresh(rule)
    return rule


@router.patch("/commission-rules/{rule_id}", response_model=RuleOut)
def update_rule(
    rule_id: int,
    body: RuleIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("commission:manage")
    rule = db.get(CommissionRule, rule_id)
    if rule is None:
        raise AppError("not_found", "分成规则不存在", status_code=404)
    mid = ctx.resolve_merchant_id(body.merchant_id or rule.merchant_id)
    if rule.merchant_id != mid:
        raise AppError("forbidden", "禁止跨商户修改", status_code=403)
    validate_rule_config(
        scope=body.scope,
        beneficiary=body.beneficiary,
        basis=body.basis,
        rate=body.rate,
        unit_amount=body.unit_amount,
    )
    _validate_effective_range(body.effective_from, body.effective_to)

    rule.name = body.name.strip()
    rule.scope = body.scope
    rule.beneficiary = body.beneficiary
    rule.basis = body.basis
    rule.rate = body.rate
    rule.unit_amount = body.unit_amount
    rule.min_base_amount = body.min_base_amount
    rule.max_amount = body.max_amount
    rule.first_order_only = body.first_order_only
    rule.priority = body.priority
    rule.effective_from = body.effective_from
    rule.effective_to = body.effective_to
    rule.is_active = body.is_active
    rule.remark = (body.remark or "").strip() or None
    write_audit(
        db,
        action="commission_rule.update",
        target_type="commission_rule",
        target_id=rule.id,
        summary=f"更新分成规则 {rule.name}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=mid,
    )
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/commission-rules/{rule_id}")
def delete_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """已产生提成记录的规则只停用不删除，保留对账链路。"""
    ctx.require_permission("commission:manage")
    rule = db.get(CommissionRule, rule_id)
    if rule is None:
        raise AppError("not_found", "分成规则不存在", status_code=404)
    ctx.resolve_merchant_id(rule.merchant_id)
    used = db.scalar(select(CommissionRecord.id).where(CommissionRecord.rule_id == rule.id).limit(1))
    if used is not None:
        rule.is_active = False
        db.commit()
        return {"ok": True, "deactivated": True}
    db.delete(rule)
    write_audit(
        db,
        action="commission_rule.delete",
        target_type="commission_rule",
        target_id=rule_id,
        summary=f"删除分成规则 {rule.name}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=rule.merchant_id,
    )
    db.commit()
    return {"ok": True, "deactivated": False}


def _record_out(row: CommissionRecord, rule_names: dict[int, str]) -> RecordOut:
    return RecordOut(
        id=row.id,
        merchant_id=row.merchant_id,
        rule_id=row.rule_id,
        rule_name=rule_names.get(row.rule_id) if row.rule_id else None,
        scope=row.scope,
        category=row.category,
        source_type=row.source_type,
        source_id=row.source_id,
        order_id=row.order_id,
        member_id=row.member_id,
        coach_id=row.coach_id,
        beneficiary_type=row.beneficiary_type,
        beneficiary_id=row.beneficiary_id,
        beneficiary_name=row.beneficiary_name,
        base_amount=row.base_amount,
        quantity=row.quantity,
        rate=row.rate,
        amount=row.amount,
        status=row.status,
        note=row.note,
        settled_at=row.settled_at,
        created_at=row.created_at,
    )


@router.get("/commission-records", response_model=PageOut[RecordOut])
def list_records(
    merchant_id: int | None = None,
    scope: str | None = None,
    category: str | None = None,
    status: str | None = None,
    beneficiary_type: str | None = None,
    beneficiary_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("commission:read", "commission:manage")
    mids = _merchant_scope(ctx, db, merchant_id)
    stmt = select(CommissionRecord).where(CommissionRecord.merchant_id.in_(mids or [-1]))
    if scope:
        stmt = stmt.where(CommissionRecord.scope == scope)
    if category:
        stmt = stmt.where(CommissionRecord.category == category)
    if status:
        stmt = stmt.where(CommissionRecord.status == status)
    if beneficiary_type:
        stmt = stmt.where(CommissionRecord.beneficiary_type == beneficiary_type)
    if beneficiary_id is not None:
        stmt = stmt.where(CommissionRecord.beneficiary_id == beneficiary_id)
    if date_from is not None and date_to is not None:
        start, end = _day_bounds(date_from, date_to)
        stmt = stmt.where(CommissionRecord.created_at >= start, CommissionRecord.created_at < end)
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        conds = [CommissionRecord.beneficiary_name.ilike(like), CommissionRecord.note.ilike(like)]
        if keyword.isdigit():
            conds.append(CommissionRecord.order_id == int(keyword))
        stmt = stmt.where(or_(*conds))

    rows, total = paginate(
        db, stmt.order_by(CommissionRecord.id.desc()), page=page, page_size=page_size
    )
    rule_ids = {r.rule_id for r in rows if r.rule_id}
    rule_names = {
        r.id: r.name
        for r in db.scalars(select(CommissionRule).where(CommissionRule.id.in_(rule_ids or {-1}))).all()
    }
    return PageOut(
        items=[_record_out(r, rule_names) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/commission-records/{record_id}/status", response_model=RecordOut)
def update_record_status(
    record_id: int,
    body: RecordStatusIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """确认 / 结算 / 作废单条提成。"""
    ctx.require_permission("commission:manage")
    record = db.get(CommissionRecord, record_id)
    if record is None:
        raise AppError("not_found", "提成记录不存在", status_code=404)
    ctx.resolve_merchant_id(record.merchant_id)
    change_record_status(db, record, body.status)
    write_audit(
        db,
        action="commission_record.status",
        target_type="commission_record",
        target_id=record.id,
        summary=f"提成记录状态改为 {record.status}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=record.merchant_id,
    )
    db.commit()
    db.refresh(record)
    rule_names = {}
    if record.rule_id:
        rule = db.get(CommissionRule, record.rule_id)
        if rule is not None:
            rule_names[rule.id] = rule.name
    return _record_out(record, rule_names)


@router.post("/commission-records/batch-status", response_model=RecordBatchOut)
def batch_update_record_status(
    body: RecordBatchIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """批量确认或结算提成；状态不允许的记录自动跳过。"""
    ctx.require_permission("commission:manage")
    rows = list(
        db.scalars(select(CommissionRecord).where(CommissionRecord.id.in_(set(body.ids)))).all()
    )
    updated = 0
    skipped = 0
    for row in rows:
        ctx.resolve_merchant_id(row.merchant_id)
        try:
            change_record_status(db, row, body.status)
            updated += 1
        except AppError:
            skipped += 1
    skipped += len(set(body.ids)) - len(rows)
    write_audit(
        db,
        action="commission_record.batch_status",
        target_type="commission_record",
        target_id=0,
        summary=f"批量改为 {body.status}：成功 {updated}，跳过 {skipped}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=None if ctx.is_site_admin else ctx.merchant_id,
    )
    db.commit()
    return RecordBatchOut(updated=updated, skipped=skipped)


@router.get("/commission-summary", response_model=CommissionSummaryOut)
def commission_summary(
    date_from: date,
    date_to: date,
    merchant_id: int | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """业绩分成看板：按场景、受益人与销售员汇总。"""
    ctx.require_permission("commission:read", "commission:manage", "report:read")
    if date_to < date_from:
        raise AppError("invalid_range", "结束日期不能早于开始日期", status_code=400)
    mids = _merchant_scope(ctx, db, merchant_id) or [-1]
    start, end = _day_bounds(date_from, date_to)

    records = list(
        db.scalars(
            select(CommissionRecord).where(
                CommissionRecord.merchant_id.in_(mids),
                CommissionRecord.created_at >= start,
                CommissionRecord.created_at < end,
                CommissionRecord.status != CommissionStatus.VOID.value,
            )
        ).all()
    )

    total = Decimal("0")
    pending = Decimal("0")
    confirmed = Decimal("0")
    paid = Decimal("0")
    scope_map: dict[str, tuple[int, Decimal]] = {}
    beneficiary_map: dict[tuple[str, int], dict] = {}
    for row in records:
        amount = Decimal(row.amount or 0)
        total += amount
        if row.status == CommissionStatus.PENDING.value:
            pending += amount
        elif row.status == CommissionStatus.CONFIRMED.value:
            confirmed += amount
        elif row.status == CommissionStatus.PAID.value:
            paid += amount

        cnt, acc = scope_map.get(row.scope, (0, Decimal("0")))
        scope_map[row.scope] = (cnt + 1, acc + amount)

        key = (row.beneficiary_type, row.beneficiary_id)
        entry = beneficiary_map.setdefault(
            key,
            {
                "name": row.beneficiary_name,
                "count": 0,
                "pending": Decimal("0"),
                "confirmed": Decimal("0"),
                "paid": Decimal("0"),
                "total": Decimal("0"),
            },
        )
        entry["name"] = row.beneficiary_name
        entry["count"] += 1
        entry["total"] += amount
        if row.status == CommissionStatus.PENDING.value:
            entry["pending"] += amount
        elif row.status == CommissionStatus.CONFIRMED.value:
            entry["confirmed"] += amount
        elif row.status == CommissionStatus.PAID.value:
            entry["paid"] += amount

    seller_rows = db.execute(
        select(
            Order.seller_staff_id,
            func.count(Order.id),
            func.coalesce(func.sum(Order.amount), 0),
        )
        .where(
            Order.merchant_id.in_(mids),
            Order.seller_staff_id.is_not(None),
            Order.status == OrderStatus.PAID.value,
            Order.created_at >= start,
            Order.created_at < end,
        )
        .group_by(Order.seller_staff_id)
    ).all()
    staff_ids = {int(r[0]) for r in seller_rows}
    staff_names = {
        s.id: s.display_name
        for s in db.scalars(select(StaffUser).where(StaffUser.id.in_(staff_ids or {-1}))).all()
    }
    seller_commission: dict[int, Decimal] = {}
    for row in records:
        if row.beneficiary_type == "staff":
            seller_commission[row.beneficiary_id] = seller_commission.get(
                row.beneficiary_id, Decimal("0")
            ) + Decimal(row.amount or 0)

    sellers = [
        SellerPerformanceRow(
            staff_id=int(staff_id),
            staff_name=staff_names.get(int(staff_id), f"#{staff_id}"),
            order_count=int(order_count),
            sales_amount=Decimal(sales_amount or 0),
            commission_amount=seller_commission.get(int(staff_id), Decimal("0")),
        )
        for staff_id, order_count, sales_amount in seller_rows
    ]
    sellers.sort(key=lambda x: x.sales_amount, reverse=True)

    return CommissionSummaryOut(
        date_from=date_from,
        date_to=date_to,
        total_amount=total,
        pending_amount=pending,
        confirmed_amount=confirmed,
        paid_amount=paid,
        by_scope=[
            ScopeSummaryRow(scope=scope, record_count=cnt, total_amount=amount)
            for scope, (cnt, amount) in sorted(scope_map.items())
        ],
        by_beneficiary=sorted(
            [
                BeneficiarySummaryRow(
                    beneficiary_type=key[0],
                    beneficiary_id=key[1],
                    beneficiary_name=entry["name"],
                    record_count=entry["count"],
                    pending_amount=entry["pending"],
                    confirmed_amount=entry["confirmed"],
                    paid_amount=entry["paid"],
                    total_amount=entry["total"],
                )
                for key, entry in beneficiary_map.items()
            ],
            key=lambda x: x.total_amount,
            reverse=True,
        ),
        sellers=sellers,
    )


