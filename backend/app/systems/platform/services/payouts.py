"""提现单据：教练佣金提现与会员返点提现共用状态机。

线上只登记状态：申请 → 审核通过 → 已打款（线下现金/转账），或驳回退回。
佣金提现按提成记录逐条锁定，打款后回写记录为已结算；返点提现走账户冻结与解冻。
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.systems.gym.models.commission import BeneficiaryType, CommissionRecord, CommissionStatus
from app.systems.platform.models.member import Member
from app.systems.platform.models.payout import (
    Payout,
    PayoutItem,
    PayoutMethod,
    PayoutSource,
    PayoutStatus,
)
from app.systems.platform.services.audit import write_audit
from app.systems.platform.services.promotion import money, resolve_promotion_settings
from app.systems.platform.services.rebate import (
    freeze_for_withdraw,
    get_account,
    revert_withdraw,
    settle_withdraw,
)

_ALLOWED_TRANSITIONS = {
    PayoutStatus.REQUESTED.value: {PayoutStatus.APPROVED.value, PayoutStatus.REJECTED.value},
    PayoutStatus.APPROVED.value: {PayoutStatus.PAID.value, PayoutStatus.REJECTED.value},
    PayoutStatus.PAID.value: set(),
    PayoutStatus.REJECTED.value: set(),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def settleable_records(
    db: Session, *, beneficiary_type: str, beneficiary_id: int, merchant_id: int | None = None
) -> list[CommissionRecord]:
    """可提现的提成记录：已确认且未被其他提现单占用。"""
    stmt = select(CommissionRecord).where(
        CommissionRecord.beneficiary_type == beneficiary_type,
        CommissionRecord.beneficiary_id == beneficiary_id,
        CommissionRecord.status == CommissionStatus.CONFIRMED.value,
    )
    if merchant_id is not None:
        stmt = stmt.where(CommissionRecord.merchant_id == merchant_id)
    rows = list(db.scalars(stmt.order_by(CommissionRecord.id.asc())).all())
    if not rows:
        return []
    locked = set(
        db.scalars(
            select(PayoutItem.commission_record_id).where(
                PayoutItem.commission_record_id.in_([r.id for r in rows])
            )
        ).all()
    )
    return [r for r in rows if r.id not in locked]


def create_commission_payout(
    db: Session,
    *,
    site_id: int,
    beneficiary_type: str,
    beneficiary_id: int,
    beneficiary_name: str,
    merchant_id: int | None,
    record_ids: list[int] | None,
    note: str | None,
    requested_by_staff_id: int | None,
) -> Payout:
    """按已确认提成记录发起提现申请。"""
    candidates = settleable_records(
        db,
        beneficiary_type=beneficiary_type,
        beneficiary_id=beneficiary_id,
        merchant_id=merchant_id,
    )
    if record_ids:
        wanted = set(record_ids)
        picked = [r for r in candidates if r.id in wanted]
        if len(picked) != len(wanted):
            raise AppError("invalid_records", "存在不可提现的提成记录", status_code=400)
    else:
        picked = candidates
    if not picked:
        raise AppError("no_settleable_records", "没有可提现的已确认提成", status_code=400)

    total = sum((money(r.amount) for r in picked), Decimal("0.00"))
    if total <= 0:
        raise AppError("validation_error", "提现金额必须大于 0", status_code=422)

    payout = Payout(
        site_id=site_id,
        merchant_id=merchant_id or picked[0].merchant_id,
        source=PayoutSource.COMMISSION.value,
        beneficiary_type=beneficiary_type,
        beneficiary_id=beneficiary_id,
        beneficiary_name=beneficiary_name,
        amount=total,
        status=PayoutStatus.REQUESTED.value,
        note=(note or "").strip() or None,
        requested_by_staff_id=requested_by_staff_id,
    )
    db.add(payout)
    db.flush()
    for record in picked:
        db.add(
            PayoutItem(
                payout_id=payout.id, commission_record_id=record.id, amount=money(record.amount)
            )
        )
    db.flush()
    write_audit(
        db,
        action="payout.request",
        target_type="payout",
        target_id=payout.id,
        summary=f"申请佣金提现 {total}（{len(picked)} 笔）",
        actor_staff_id=requested_by_staff_id,
        site_id=site_id,
        merchant_id=payout.merchant_id,
    )
    return payout


def create_rebate_payout(
    db: Session,
    *,
    member: Member,
    amount: Decimal,
    note: str | None,
    requested_by_staff_id: int | None = None,
    requested_by_member_id: int | None = None,
) -> Payout:
    """会员返点提现申请：冻结余额并生成单据。"""
    settings = resolve_promotion_settings(db, member.site_id)
    payout = Payout(
        site_id=member.site_id,
        merchant_id=None,
        source=PayoutSource.REBATE.value,
        beneficiary_type=BeneficiaryType.MEMBER.value,
        beneficiary_id=member.id,
        beneficiary_name=f"{member.name} {member.phone}",
        amount=money(amount),
        status=PayoutStatus.REQUESTED.value,
        note=(note or "").strip() or None,
        requested_by_staff_id=requested_by_staff_id,
        requested_by_member_id=requested_by_member_id,
    )
    db.add(payout)
    db.flush()
    freeze_for_withdraw(
        db,
        member=member,
        amount=money(amount),
        payout_id=payout.id,
        min_amount=settings.min_withdraw_amount,
        actor_staff_id=requested_by_staff_id,
        settings=settings,
    )
    write_audit(
        db,
        action="payout.request",
        target_type="payout",
        target_id=payout.id,
        summary=f"申请返点提现 {money(amount)}",
        actor_staff_id=requested_by_staff_id,
        site_id=member.site_id,
    )
    return payout


def _assert_transition(payout: Payout, target: str) -> None:
    if target not in {s.value for s in PayoutStatus}:
        raise AppError("invalid_status", "未知提现状态", status_code=400)
    if target not in _ALLOWED_TRANSITIONS[payout.status]:
        raise AppError("invalid_state", "当前状态不允许该操作", status_code=400)


def approve_payout(db: Session, payout: Payout, *, actor_staff_id: int | None) -> Payout:
    _assert_transition(payout, PayoutStatus.APPROVED.value)
    payout.status = PayoutStatus.APPROVED.value
    payout.reviewed_by_staff_id = actor_staff_id
    payout.reviewed_at = _now()
    write_audit(
        db,
        action="payout.approve",
        target_type="payout",
        target_id=payout.id,
        summary=f"审核通过提现 {money(payout.amount)}",
        actor_staff_id=actor_staff_id,
        site_id=payout.site_id,
        merchant_id=payout.merchant_id,
    )
    db.flush()
    return payout


def reject_payout(
    db: Session, payout: Payout, *, reason: str | None, actor_staff_id: int | None
) -> Payout:
    """驳回：佣金记录释放锁定，返点余额解冻。"""
    _assert_transition(payout, PayoutStatus.REJECTED.value)
    payout.status = PayoutStatus.REJECTED.value
    payout.reject_reason = (reason or "").strip() or None
    payout.reviewed_by_staff_id = actor_staff_id
    payout.reviewed_at = _now()

    if payout.source == PayoutSource.COMMISSION.value:
        for item in db.scalars(
            select(PayoutItem).where(PayoutItem.payout_id == payout.id)
        ).all():
            db.delete(item)
    else:
        member = db.get(Member, payout.beneficiary_id)
        if member is not None:
            account = get_account(db, member=member, create=False)
            if account is not None:
                revert_withdraw(
                    db,
                    account_id=account.id,
                    amount=money(payout.amount),
                    payout_id=payout.id,
                    actor_staff_id=actor_staff_id,
                    note=f"提现驳回解冻：{payout.reject_reason or '未填写原因'}",
                )
    write_audit(
        db,
        action="payout.reject",
        target_type="payout",
        target_id=payout.id,
        summary=f"驳回提现 {money(payout.amount)}：{payout.reject_reason or '未填写原因'}",
        actor_staff_id=actor_staff_id,
        site_id=payout.site_id,
        merchant_id=payout.merchant_id,
    )
    db.flush()
    return payout


def mark_payout_paid(
    db: Session,
    payout: Payout,
    *,
    method: str,
    external_ref: str | None,
    note: str | None,
    actor_staff_id: int | None,
) -> Payout:
    """登记线下打款完成，回写提成状态或返点账户。"""
    _assert_transition(payout, PayoutStatus.PAID.value)
    if method not in {m.value for m in PayoutMethod}:
        raise AppError("invalid_method", "未知打款方式", status_code=400)
    payout.status = PayoutStatus.PAID.value
    payout.method = method
    payout.external_ref = (external_ref or "").strip() or None
    if note:
        payout.note = note.strip()[:255]
    payout.paid_by_staff_id = actor_staff_id
    payout.paid_at = _now()

    if payout.source == PayoutSource.COMMISSION.value:
        items = list(db.scalars(select(PayoutItem).where(PayoutItem.payout_id == payout.id)).all())
        for item in items:
            record = db.get(CommissionRecord, item.commission_record_id)
            if record is None:
                continue
            if record.status == CommissionStatus.CONFIRMED.value:
                record.status = CommissionStatus.PAID.value
                record.settled_at = payout.paid_at
    else:
        member = db.get(Member, payout.beneficiary_id)
        if member is None:
            raise AppError("not_found", "会员不存在", status_code=404)
        account = get_account(db, member=member, create=False)
        if account is None:
            raise AppError("not_found", "返点账户不存在", status_code=404)
        settle_withdraw(
            db,
            account_id=account.id,
            amount=money(payout.amount),
            payout_id=payout.id,
            actor_staff_id=actor_staff_id,
        )
    write_audit(
        db,
        action="payout.paid",
        target_type="payout",
        target_id=payout.id,
        summary=f"登记线下打款 {money(payout.amount)} method={method}",
        actor_staff_id=actor_staff_id,
        site_id=payout.site_id,
        merchant_id=payout.merchant_id,
    )
    db.flush()
    return payout
