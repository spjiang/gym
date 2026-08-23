"""分成政策：结算冷却与已打款退款欠额。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.systems.gym.models.commission import (
    ClawbackLedgerKind,
    CommissionClawbackLedger,
    CommissionDebtAccount,
    CommissionRecord,
    CommissionStatus,
    SiteCommissionSettings,
)
from app.systems.platform.models.org import Merchant
from app.systems.platform.services.promotion import money

_CENT = Decimal("0.01")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _quantize(value: Decimal) -> Decimal:
    return Decimal(value).quantize(_CENT, rounding=ROUND_HALF_UP)


def _ensure_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def site_id_of_merchant(db: Session, merchant_id: int) -> int:
    merchant = db.get(Merchant, merchant_id)
    if merchant is None:
        raise AppError("not_found", "商户不存在", status_code=404)
    return merchant.site_id


def get_or_create_settings(db: Session, site_id: int) -> SiteCommissionSettings:
    row = db.scalar(select(SiteCommissionSettings).where(SiteCommissionSettings.site_id == site_id))
    if row is None:
        row = SiteCommissionSettings(site_id=site_id, settle_hold_days=0)
        db.add(row)
        db.flush()
    return row


def settle_hold_days(db: Session, site_id: int) -> int:
    row = get_or_create_settings(db, site_id)
    return max(0, int(row.settle_hold_days or 0))


def record_hold_until(record: CommissionRecord, hold_days: int) -> datetime | None:
    if hold_days <= 0:
        return None
    created = _ensure_aware(record.created_at) or _now()
    return created + timedelta(days=hold_days)


def record_ready_to_settle(record: CommissionRecord, hold_days: int, *, now: datetime | None = None) -> bool:
    until = record_hold_until(record, hold_days)
    if until is None:
        return True
    return (_ensure_aware(now) or _now()) >= until


def assert_record_ready_to_settle(db: Session, record: CommissionRecord) -> None:
    site_id = site_id_of_merchant(db, record.merchant_id)
    days = settle_hold_days(db, site_id)
    if record_ready_to_settle(record, days):
        return
    until = record_hold_until(record, days)
    raise AppError(
        "commission_hold",
        f"提成需满 {days} 天才能结算（可结算时间 {until.strftime('%Y-%m-%d %H:%M') if until else ''}）",
        status_code=400,
    )


def get_or_create_debt_account(
    db: Session,
    *,
    site_id: int,
    beneficiary_type: str,
    beneficiary_id: int,
    beneficiary_name: str,
) -> CommissionDebtAccount:
    row = db.scalar(
        select(CommissionDebtAccount).where(
            CommissionDebtAccount.site_id == site_id,
            CommissionDebtAccount.beneficiary_type == beneficiary_type,
            CommissionDebtAccount.beneficiary_id == beneficiary_id,
        )
    )
    if row is None:
        row = CommissionDebtAccount(
            site_id=site_id,
            beneficiary_type=beneficiary_type,
            beneficiary_id=beneficiary_id,
            beneficiary_name=beneficiary_name or "",
            debt_amount=Decimal("0.00"),
        )
        db.add(row)
        db.flush()
    elif beneficiary_name and row.beneficiary_name != beneficiary_name:
        row.beneficiary_name = beneficiary_name
    return row


def debt_of(
    db: Session, *, site_id: int, beneficiary_type: str, beneficiary_id: int
) -> Decimal:
    row = db.scalar(
        select(CommissionDebtAccount).where(
            CommissionDebtAccount.site_id == site_id,
            CommissionDebtAccount.beneficiary_type == beneficiary_type,
            CommissionDebtAccount.beneficiary_id == beneficiary_id,
        )
    )
    if row is None:
        return Decimal("0.00")
    return money(row.debt_amount)


def _recalc_debt(db: Session, account: CommissionDebtAccount) -> Decimal:
    clawbacks = sum(
        (
            money(r.amount)
            for r in db.scalars(
                select(CommissionClawbackLedger).where(
                    CommissionClawbackLedger.account_id == account.id,
                    CommissionClawbackLedger.kind == ClawbackLedgerKind.CLAWBACK.value,
                )
            ).all()
        ),
        Decimal("0.00"),
    )
    credited = sum(
        (
            money(r.amount)
            for r in db.scalars(
                select(CommissionClawbackLedger).where(
                    CommissionClawbackLedger.account_id == account.id,
                    CommissionClawbackLedger.kind.in_(
                        [ClawbackLedgerKind.OFFSET.value, ClawbackLedgerKind.RECOVER.value]
                    ),
                )
            ).all()
        ),
        Decimal("0.00"),
    )
    account.debt_amount = _quantize(max(Decimal("0.00"), clawbacks - credited))
    db.flush()
    return money(account.debt_amount)


def _write_ledger(
    db: Session,
    *,
    account: CommissionDebtAccount,
    kind: str,
    amount: Decimal,
    source_type: str,
    source_id: int,
    commission_record_id: int | None,
    order_id: int | None,
    note: str | None,
    actor_staff_id: int | None = None,
) -> CommissionClawbackLedger:
    conds = [
        CommissionClawbackLedger.kind == kind,
        CommissionClawbackLedger.source_type == source_type,
        CommissionClawbackLedger.source_id == source_id,
    ]
    if commission_record_id is None:
        conds.append(CommissionClawbackLedger.commission_record_id.is_(None))
    else:
        conds.append(CommissionClawbackLedger.commission_record_id == commission_record_id)
    existing = db.scalar(select(CommissionClawbackLedger).where(*conds))
    if existing is not None:
        return existing
    row = CommissionClawbackLedger(
        site_id=account.site_id,
        account_id=account.id,
        kind=kind,
        amount=_quantize(amount),
        source_type=source_type,
        source_id=source_id,
        commission_record_id=commission_record_id,
        order_id=order_id,
        note=note,
        actor_staff_id=actor_staff_id,
    )
    db.add(row)
    db.flush()
    return row


def _clawed_for_record(db: Session, record_id: int) -> Decimal:
    rows = list(
        db.scalars(
            select(CommissionClawbackLedger).where(
                CommissionClawbackLedger.commission_record_id == record_id,
                CommissionClawbackLedger.kind == ClawbackLedgerKind.CLAWBACK.value,
            )
        ).all()
    )
    return sum((money(r.amount) for r in rows), Decimal("0.00"))


def clawback_paid_record(
    db: Session,
    record: CommissionRecord,
    *,
    refund_id: int,
    amount: Decimal,
) -> Decimal:
    """已打款提成挂账；不超过该记录剩余可追回额。"""
    take = _quantize(max(Decimal("0.00"), money(amount)))
    if take <= 0 or record.status != CommissionStatus.PAID.value:
        return Decimal("0.00")
    remaining = money(record.amount) - _clawed_for_record(db, record.id)
    if remaining <= 0:
        return Decimal("0.00")
    take = min(take, remaining)
    site_id = site_id_of_merchant(db, record.merchant_id)
    account = get_or_create_debt_account(
        db,
        site_id=site_id,
        beneficiary_type=record.beneficiary_type,
        beneficiary_id=record.beneficiary_id,
        beneficiary_name=record.beneficiary_name,
    )
    written = _write_ledger(
        db,
        account=account,
        kind=ClawbackLedgerKind.CLAWBACK.value,
        amount=take,
        source_type="refund",
        source_id=refund_id,
        commission_record_id=record.id,
        order_id=record.order_id,
        note=f"订单退款追回已打款提成 record={record.id}",
    )
    _recalc_debt(db, account)
    return money(written.amount)


def apply_debt_offset(
    db: Session,
    *,
    site_id: int,
    beneficiary_type: str,
    beneficiary_id: int,
    beneficiary_name: str,
    amount: Decimal,
    source_type: str,
    source_id: int,
    commission_record_id: int | None = None,
    note: str | None = None,
) -> Decimal:
    """从欠额中抵扣，返回实际抵扣额（同一来源幂等）。"""
    take = _quantize(max(Decimal("0.00"), money(amount)))
    account = get_or_create_debt_account(
        db,
        site_id=site_id,
        beneficiary_type=beneficiary_type,
        beneficiary_id=beneficiary_id,
        beneficiary_name=beneficiary_name,
    )
    conds = [
        CommissionClawbackLedger.kind == ClawbackLedgerKind.OFFSET.value,
        CommissionClawbackLedger.source_type == source_type,
        CommissionClawbackLedger.source_id == source_id,
    ]
    if commission_record_id is None:
        conds.append(CommissionClawbackLedger.commission_record_id.is_(None))
    else:
        conds.append(CommissionClawbackLedger.commission_record_id == commission_record_id)
    existing = db.scalar(select(CommissionClawbackLedger).where(*conds))
    if existing is not None:
        return money(existing.amount)
    if take <= 0:
        return Decimal("0.00")
    available = money(account.debt_amount)
    if available <= 0:
        return Decimal("0.00")
    applied = min(take, available)
    _write_ledger(
        db,
        account=account,
        kind=ClawbackLedgerKind.OFFSET.value,
        amount=applied,
        source_type=source_type,
        source_id=source_id,
        commission_record_id=commission_record_id,
        order_id=None,
        note=note or "结算抵扣提成欠额",
    )
    _recalc_debt(db, account)
    return applied


def restore_debt_offset(
    db: Session,
    *,
    source_type: str,
    source_id: int,
) -> None:
    """提现驳回：删除对应抵扣流水并重算欠额。"""
    rows = list(
        db.scalars(
            select(CommissionClawbackLedger).where(
                CommissionClawbackLedger.kind == ClawbackLedgerKind.OFFSET.value,
                CommissionClawbackLedger.source_type == source_type,
                CommissionClawbackLedger.source_id == source_id,
            )
        ).all()
    )
    if not rows:
        return
    account_ids = {row.account_id for row in rows}
    for row in rows:
        db.delete(row)
    db.flush()
    for account_id in account_ids:
        account = db.get(CommissionDebtAccount, account_id)
        if account is not None:
            _recalc_debt(db, account)


def recover_debt_cash(
    db: Session,
    *,
    site_id: int,
    beneficiary_type: str,
    beneficiary_id: int,
    amount: Decimal,
    actor_staff_id: int | None,
    note: str | None,
) -> Decimal:
    """运营登记现金追回。"""
    take = _quantize(max(Decimal("0.00"), money(amount)))
    if take <= 0:
        raise AppError("validation_error", "追回金额必须大于 0", status_code=422)
    account = get_or_create_debt_account(
        db,
        site_id=site_id,
        beneficiary_type=beneficiary_type,
        beneficiary_id=beneficiary_id,
        beneficiary_name="",
    )
    available = money(account.debt_amount)
    if take > available:
        raise AppError("invalid_amount", f"追回金额不能超过欠额 ¥{available}", status_code=400)
    source_id = int(_now().timestamp() * 1000)
    _write_ledger(
        db,
        account=account,
        kind=ClawbackLedgerKind.RECOVER.value,
        amount=take,
        source_type="manual",
        source_id=source_id,
        commission_record_id=None,
        order_id=None,
        note=(note or "").strip() or "登记现金追回",
        actor_staff_id=actor_staff_id,
    )
    _recalc_debt(db, account)
    return take
