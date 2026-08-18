"""会员推广返点入账、退款冲回与提现资金操作。

口径：按订单实付金额 × 上级推广位返点比例入账；退款按退款占比冲回。
余额只用于线下提现，账户不参与消费抵扣。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.systems.platform.models.commerce import Order, OrderStatus
from app.systems.platform.models.member import Member
from app.systems.platform.models.rebate import (
    MemberRebateAccount,
    MemberRebateLedger,
    RebateLedgerKind,
)
from app.systems.platform.services.promotion import (
    EffectivePromotionSettings,
    UplineInfo,
    money,
    resolve_promotion_settings,
    resolve_upline,
)

_CENT = Decimal("0.01")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _quantize(value: Decimal) -> Decimal:
    return Decimal(value).quantize(_CENT, rounding=ROUND_HALF_UP)


@dataclass
class RebateSnapshot:
    balance: Decimal
    frozen_amount: Decimal
    debt_amount: Decimal
    total_earned: Decimal
    total_withdrawn: Decimal
    held_amount: Decimal
    available_balance: Decimal


def get_account(db: Session, *, member: Member, create: bool = True) -> MemberRebateAccount | None:
    account = db.scalar(
        select(MemberRebateAccount).where(MemberRebateAccount.member_id == member.id)
    )
    if account is None and create:
        account = MemberRebateAccount(site_id=member.site_id, member_id=member.id)
        db.add(account)
        db.flush()
    return account


def lock_account(db: Session, account_id: int) -> MemberRebateAccount:
    account = db.scalar(
        select(MemberRebateAccount).where(MemberRebateAccount.id == account_id).with_for_update()
    )
    if account is None:
        raise AppError("not_found", "返点账户不存在", status_code=404)
    return account


def snapshot(account: MemberRebateAccount | None, *, held_amount: Decimal | None = None) -> RebateSnapshot:
    zero = Decimal("0.00")
    held = money(held_amount or 0)
    if account is None:
        return RebateSnapshot(zero, zero, zero, zero, zero, held, zero)
    balance = money(account.balance)
    available = max(zero, balance - held)
    return RebateSnapshot(
        balance=balance,
        frozen_amount=money(account.frozen_amount),
        debt_amount=money(account.debt_amount),
        total_earned=money(account.total_earned),
        total_withdrawn=money(account.total_withdrawn),
        held_amount=held,
        available_balance=available,
    )


def held_rebate_amount(db: Session, *, member_id: int, hold_days: int) -> Decimal:
    """未满冷却期的净返点（入账+冲回）。满期或未配置冷却时为 0。"""
    if hold_days <= 0:
        return Decimal("0.00")
    cutoff = _now() - timedelta(days=hold_days)
    rows = db.scalars(
        select(MemberRebateLedger).where(
            MemberRebateLedger.member_id == member_id,
            MemberRebateLedger.kind.in_(
                [RebateLedgerKind.EARN.value, RebateLedgerKind.REVERSE.value]
            ),
            MemberRebateLedger.created_at > cutoff,
        )
    ).all()
    net = Decimal("0.00")
    for row in rows:
        net += money(row.amount)
    return max(Decimal("0.00"), money(net))


def available_withdraw_amount(
    db: Session,
    member: Member,
    settings: EffectivePromotionSettings | None = None,
) -> Decimal:
    """当前可申请提现的金额：账户余额减去未满冷却期的返点。"""
    resolved = settings or resolve_promotion_settings(db, member.site_id)
    account = get_account(db, member=member, create=False)
    snap = snapshot(
        account,
        held_amount=held_rebate_amount(
            db, member_id=member.id, hold_days=resolved.withdraw_hold_days
        ),
    )
    return snap.available_balance


def _existing_ledger(
    db: Session, *, kind: str, source_type: str, source_id: int
) -> MemberRebateLedger | None:
    return db.scalar(
        select(MemberRebateLedger).where(
            MemberRebateLedger.kind == kind,
            MemberRebateLedger.source_type == source_type,
            MemberRebateLedger.source_id == source_id,
        )
    )


def _write_ledger(
    db: Session,
    *,
    account: MemberRebateAccount,
    kind: str,
    amount: Decimal,
    source_type: str | None,
    source_id: int | None,
    merchant_id: int | None = None,
    order_id: int | None = None,
    from_member_id: int | None = None,
    base_amount: Decimal | None = None,
    rate: Decimal | None = None,
    note: str | None = None,
    actor_staff_id: int | None = None,
) -> MemberRebateLedger:
    ledger = MemberRebateLedger(
        site_id=account.site_id,
        account_id=account.id,
        member_id=account.member_id,
        merchant_id=merchant_id,
        kind=kind,
        amount=_quantize(amount),
        balance_after=money(account.balance),
        source_type=source_type,
        source_id=source_id,
        order_id=order_id,
        from_member_id=from_member_id,
        base_amount=None if base_amount is None else money(base_amount),
        rate=rate,
        note=note,
        actor_staff_id=actor_staff_id,
    )
    db.add(ledger)
    db.flush()
    return ledger


def accrue_order_rebate(
    db: Session,
    order: Order,
    *,
    upline: UplineInfo,
    fallback_amount: Decimal | None = None,
) -> MemberRebateLedger | None:
    """下级消费入账上级返点；同一订单只入一次。

    fallback_amount 用于推广位未显式配置比例时，沿用商户推荐提成规则算出的金额。
    """
    if order.status != OrderStatus.PAID.value or order.member_id is None:
        return None
    if upline.promoter is not None and not upline.promoter.is_active:
        return None
    existing = _existing_ledger(
        db, kind=RebateLedgerKind.EARN.value, source_type="order", source_id=order.id
    )
    if existing is not None:
        return existing

    base = money(order.amount)
    rate = upline.rebate_rate
    if rate > 0:
        amount = _quantize(base * rate)
    elif fallback_amount is not None:
        amount = _quantize(fallback_amount)
    else:
        return None
    if amount <= 0:
        return None

    upline_member = db.get(Member, upline.member_id)
    if upline_member is None:
        return None
    account = get_account(db, member=upline_member)
    assert account is not None
    account = lock_account(db, account.id)

    # 先抵扣历史欠额（退款冲回时余额不足留下的挂账）
    credited = amount
    if money(account.debt_amount) > 0:
        offset = min(money(account.debt_amount), amount)
        account.debt_amount = money(account.debt_amount) - offset
        credited = amount - offset
    account.balance = money(account.balance) + credited
    account.total_earned = money(account.total_earned) + amount
    return _write_ledger(
        db,
        account=account,
        kind=RebateLedgerKind.EARN.value,
        amount=amount,
        source_type="order",
        source_id=order.id,
        merchant_id=order.merchant_id,
        order_id=order.id,
        from_member_id=order.member_id,
        base_amount=base,
        rate=rate if rate > 0 else None,
        note=f"下级消费返点 order={order.id}",
    )


def reverse_order_rebate(
    db: Session,
    order: Order,
    *,
    refund_id: int,
    refund_amount: Decimal,
) -> MemberRebateLedger | None:
    """按退款占比冲回已入账返点；余额不足记为欠额待后续返点抵扣。"""
    earn = _existing_ledger(
        db, kind=RebateLedgerKind.EARN.value, source_type="order", source_id=order.id
    )
    if earn is None:
        return None
    existing = _existing_ledger(
        db, kind=RebateLedgerKind.REVERSE.value, source_type="refund", source_id=refund_id
    )
    if existing is not None:
        return existing

    order_amount = money(order.amount)
    if order_amount <= 0:
        return None
    earned = money(earn.amount)
    ratio = min(Decimal("1"), money(refund_amount) / order_amount)
    reversed_before = sum(
        (
            money(row.amount)
            for row in db.scalars(
                select(MemberRebateLedger).where(
                    MemberRebateLedger.account_id == earn.account_id,
                    MemberRebateLedger.kind == RebateLedgerKind.REVERSE.value,
                    MemberRebateLedger.order_id == order.id,
                )
            ).all()
        ),
        Decimal("0.00"),
    )
    # 已冲回金额为负数，取绝对值后计算剩余可冲回额度
    remaining = earned + reversed_before
    amount = min(_quantize(earned * ratio), remaining)
    if amount <= 0:
        return None

    account = lock_account(db, earn.account_id)
    deducted = min(money(account.balance), amount)
    account.balance = money(account.balance) - deducted
    shortfall = amount - deducted
    if shortfall > 0:
        account.debt_amount = money(account.debt_amount) + shortfall
    account.total_earned = money(account.total_earned) - amount
    return _write_ledger(
        db,
        account=account,
        kind=RebateLedgerKind.REVERSE.value,
        amount=-amount,
        source_type="refund",
        source_id=refund_id,
        merchant_id=order.merchant_id,
        order_id=order.id,
        from_member_id=order.member_id,
        base_amount=money(refund_amount),
        rate=earn.rate,
        note=f"下级退款冲回 order={order.id}",
    )


def freeze_for_withdraw(
    db: Session,
    *,
    member: Member,
    amount: Decimal,
    payout_id: int,
    min_amount: Decimal,
    actor_staff_id: int | None = None,
    settings: EffectivePromotionSettings | None = None,
) -> MemberRebateLedger:
    """提现申请冻结余额。"""
    amount = money(amount)
    if amount <= 0:
        raise AppError("validation_error", "提现金额不合法", status_code=422)
    if amount < money(min_amount):
        raise AppError("amount_too_small", f"单笔提现不得低于 {money(min_amount)}", status_code=400)
    resolved = settings or resolve_promotion_settings(db, member.site_id)
    available = available_withdraw_amount(db, member, resolved)
    if amount > available:
        if resolved.withdraw_hold_days > 0:
            raise AppError(
                "rebate_hold",
                (
                    f"返点满 {resolved.withdraw_hold_days} 天后才可提现，"
                    f"当前可提现 ¥{available}"
                ),
                status_code=400,
            )
        raise AppError("insufficient_balance", "可提现余额不足", status_code=400)
    account = get_account(db, member=member)
    assert account is not None
    account = lock_account(db, account.id)
    if money(account.balance) < amount:
        raise AppError("insufficient_balance", "可提现余额不足", status_code=400)
    account.balance = money(account.balance) - amount
    account.frozen_amount = money(account.frozen_amount) + amount
    return _write_ledger(
        db,
        account=account,
        kind=RebateLedgerKind.WITHDRAW_FREEZE.value,
        amount=-amount,
        source_type="payout",
        source_id=payout_id,
        note="提现申请冻结",
        actor_staff_id=actor_staff_id,
    )


def settle_withdraw(
    db: Session,
    *,
    account_id: int,
    amount: Decimal,
    payout_id: int,
    actor_staff_id: int | None = None,
) -> MemberRebateLedger:
    """线下打款完成：解冻并计入累计提现。"""
    amount = money(amount)
    account = lock_account(db, account_id)
    account.frozen_amount = max(Decimal("0.00"), money(account.frozen_amount) - amount)
    account.total_withdrawn = money(account.total_withdrawn) + amount
    return _write_ledger(
        db,
        account=account,
        kind=RebateLedgerKind.WITHDRAW_PAID.value,
        amount=Decimal("0.00"),
        source_type="payout",
        source_id=payout_id,
        note=f"线下打款 {amount}",
        actor_staff_id=actor_staff_id,
    )


def revert_withdraw(
    db: Session,
    *,
    account_id: int,
    amount: Decimal,
    payout_id: int,
    actor_staff_id: int | None = None,
    note: str | None = None,
) -> MemberRebateLedger:
    """提现被驳回：解冻回可提现余额。"""
    amount = money(amount)
    account = lock_account(db, account_id)
    account.frozen_amount = max(Decimal("0.00"), money(account.frozen_amount) - amount)
    account.balance = money(account.balance) + amount
    return _write_ledger(
        db,
        account=account,
        kind=RebateLedgerKind.WITHDRAW_REVERT.value,
        amount=amount,
        source_type="payout",
        source_id=payout_id,
        note=note or "提现驳回解冻",
        actor_staff_id=actor_staff_id,
    )


def adjust_balance(
    db: Session,
    *,
    member: Member,
    amount: Decimal,
    note: str,
    actor_staff_id: int | None = None,
) -> MemberRebateLedger:
    """人工调整返点余额，正数补发、负数扣减。"""
    amount = _quantize(Decimal(amount))
    if amount == 0:
        raise AppError("validation_error", "调整金额不能为 0", status_code=422)
    account = get_account(db, member=member)
    assert account is not None
    account = lock_account(db, account.id)
    if amount < 0 and money(account.balance) + amount < 0:
        raise AppError("insufficient_balance", "可用余额不足", status_code=400)
    account.balance = money(account.balance) + amount
    if amount > 0:
        account.total_earned = money(account.total_earned) + amount
    return _write_ledger(
        db,
        account=account,
        kind=RebateLedgerKind.ADJUST.value,
        amount=amount,
        source_type=None,
        source_id=None,
        note=note,
        actor_staff_id=actor_staff_id,
    )


def has_prior_earn(db: Session, *, from_member_id: int, exclude_order_id: int) -> bool:
    """该会员此前是否已给上级带来过返点（仅首单计提规则使用）。"""
    row = db.scalar(
        select(MemberRebateLedger.id)
        .where(
            MemberRebateLedger.kind == RebateLedgerKind.EARN.value,
            MemberRebateLedger.from_member_id == from_member_id,
            MemberRebateLedger.order_id != exclude_order_id,
        )
        .limit(1)
    )
    return row is not None


def rebate_earned_for_members(
    db: Session, *, member_ids: list[int], since: datetime | None = None, until: datetime | None = None
) -> Decimal:
    """统计由指定下级会员产生的返点净额（入账 - 冲回）。"""
    if not member_ids:
        return Decimal("0.00")
    stmt = select(MemberRebateLedger).where(
        MemberRebateLedger.from_member_id.in_(member_ids),
        MemberRebateLedger.kind.in_(
            [RebateLedgerKind.EARN.value, RebateLedgerKind.REVERSE.value]
        ),
    )
    if since is not None:
        stmt = stmt.where(MemberRebateLedger.created_at >= since)
    if until is not None:
        stmt = stmt.where(MemberRebateLedger.created_at < until)
    total = Decimal("0.00")
    for row in db.scalars(stmt).all():
        total += money(row.amount)
    return total
