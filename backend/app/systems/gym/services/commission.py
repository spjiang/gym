"""业务分成计提引擎。

规则命中：同商户同场景按 priority 升序取首条生效规则。
幂等保证：提成记录对 (场景, 来源类型, 来源 id, 受益人) 唯一，重复计提只更新未结算记录。
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.systems.gym.models.commission import (
    ORDER_SCOPES,
    BeneficiaryType,
    CommissionBasis,
    CommissionBeneficiary,
    CommissionRecord,
    CommissionRule,
    CommissionScope,
    CommissionStatus,
)
from app.systems.gym.models.course import Coach
from app.systems.platform.models.commerce import Order, OrderStatus
from app.systems.platform.models.identity import StaffUser
from app.systems.platform.models.member import Member
from app.systems.platform.models.promoter import PromoterCode
from app.systems.platform.services.promotion import resolve_upline
from app.systems.platform.services.rebate import accrue_order_rebate, has_prior_earn

_CENT = Decimal("0.01")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _quantize(value: Decimal) -> Decimal:
    return Decimal(value).quantize(_CENT, rounding=ROUND_HALF_UP)


def find_rule(
    db: Session, *, merchant_id: int, scope: str, at: datetime | None = None
) -> CommissionRule | None:
    """取商户在指定场景下的首条生效规则。"""
    moment = _ensure_aware(at) or _now()
    rows = list(
        db.scalars(
            select(CommissionRule)
            .where(
                CommissionRule.merchant_id == merchant_id,
                CommissionRule.scope == scope,
                CommissionRule.is_active.is_(True),
            )
            .order_by(CommissionRule.priority.asc(), CommissionRule.id.asc())
        ).all()
    )
    for rule in rows:
        starts = _ensure_aware(rule.effective_from)
        ends = _ensure_aware(rule.effective_to)
        if starts is not None and moment < starts:
            continue
        if ends is not None and moment >= ends:
            continue
        return rule
    return None


def compute_amount(rule: CommissionRule, *, base_amount: Decimal, quantity: int = 1) -> Decimal:
    """按规则计算提成金额；不满足门槛返回 0。"""
    base = Decimal(base_amount or 0)
    if rule.min_base_amount is not None and base < Decimal(rule.min_base_amount):
        return Decimal("0")

    if rule.basis == CommissionBasis.PERCENT.value:
        amount = base * Decimal(rule.rate or 0)
    elif rule.basis == CommissionBasis.FIXED.value:
        amount = Decimal(rule.unit_amount or 0)
    elif rule.basis in {CommissionBasis.PER_HEAD.value, CommissionBasis.PER_SESSION.value}:
        amount = Decimal(rule.unit_amount or 0) * Decimal(max(quantity, 0))
    else:
        raise AppError("invalid_rule", f"未知计提方式: {rule.basis}", status_code=400)

    if amount < 0:
        amount = Decimal("0")
    if rule.max_amount is not None and amount > Decimal(rule.max_amount):
        amount = Decimal(rule.max_amount)
    return _quantize(amount)


def validate_rule_config(
    *,
    scope: str,
    beneficiary: str,
    basis: str,
    rate: Decimal | None,
    unit_amount: Decimal | None,
) -> None:
    """校验规则配置的场景/受益方/计提方式组合是否成立。"""
    if scope not in {s.value for s in CommissionScope}:
        raise AppError("invalid_scope", "未知计提场景", status_code=400)
    if beneficiary not in {b.value for b in CommissionBeneficiary}:
        raise AppError("invalid_beneficiary", "未知受益方", status_code=400)
    if basis not in {b.value for b in CommissionBasis}:
        raise AppError("invalid_basis", "未知计提方式", status_code=400)

    expected = {
        CommissionScope.MEMBERSHIP_SALE.value: CommissionBeneficiary.SELLER.value,
        CommissionScope.PT_SALE.value: CommissionBeneficiary.SELLER.value,
        CommissionScope.RETAIL_SALE.value: CommissionBeneficiary.SELLER.value,
        CommissionScope.ACTIVITY_SALE.value: CommissionBeneficiary.SELLER.value,
        CommissionScope.GROUP_SESSION.value: CommissionBeneficiary.COACH.value,
        CommissionScope.PT_SESSION.value: CommissionBeneficiary.COACH.value,
        CommissionScope.REFERRAL.value: CommissionBeneficiary.REFERRER.value,
    }[scope]
    if beneficiary != expected:
        raise AppError("invalid_beneficiary", "该场景的受益方不匹配", status_code=400)

    if basis == CommissionBasis.PERCENT.value:
        if rate is None or Decimal(rate) <= 0:
            raise AppError("invalid_rate", "百分比计提必须填写大于 0 的比例", status_code=400)
        if Decimal(rate) > 1:
            raise AppError("invalid_rate", "比例需以小数表示，最大 1（100%）", status_code=400)
    else:
        if unit_amount is None or Decimal(unit_amount) <= 0:
            raise AppError("invalid_unit_amount", "固定/按量计提必须填写单位金额", status_code=400)

    session_basis = {CommissionBasis.PER_HEAD.value, CommissionBasis.PER_SESSION.value}
    if scope in ORDER_SCOPES and basis in session_basis:
        raise AppError("invalid_basis", "销售类场景仅支持百分比或固定金额", status_code=400)
    if scope == CommissionScope.GROUP_SESSION.value and basis == CommissionBasis.PERCENT.value:
        raise AppError("invalid_basis", "团课提成请按人头或固定金额配置", status_code=400)


def _beneficiary_name(db: Session, beneficiary_type: str, beneficiary_id: int) -> str | None:
    if beneficiary_type == BeneficiaryType.STAFF.value:
        staff = db.get(StaffUser, beneficiary_id)
        return staff.display_name if staff else None
    if beneficiary_type == BeneficiaryType.COACH.value:
        coach = db.get(Coach, beneficiary_id)
        return coach.display_name if coach else None
    member = db.get(Member, beneficiary_id)
    return member.name if member else None


def _upsert_record(
    db: Session,
    *,
    merchant_id: int,
    rule: CommissionRule,
    scope: str,
    source_type: str,
    source_id: int,
    beneficiary_type: str,
    beneficiary_id: int,
    base_amount: Decimal,
    quantity: int | None,
    amount: Decimal,
    order_id: int | None = None,
    member_id: int | None = None,
    note: str | None = None,
) -> CommissionRecord | None:
    """写入或刷新提成记录；已确认/已结算的记录不再改动。"""
    name = _beneficiary_name(db, beneficiary_type, beneficiary_id)
    if name is None:
        return None

    existing = db.scalar(
        select(CommissionRecord).where(
            CommissionRecord.scope == scope,
            CommissionRecord.source_type == source_type,
            CommissionRecord.source_id == source_id,
            CommissionRecord.beneficiary_type == beneficiary_type,
            CommissionRecord.beneficiary_id == beneficiary_id,
        )
    )
    if existing is not None:
        if existing.status != CommissionStatus.PENDING.value:
            return existing
        existing.rule_id = rule.id
        existing.base_amount = _quantize(Decimal(base_amount or 0))
        existing.quantity = quantity
        existing.rate = rule.rate
        existing.amount = amount
        existing.beneficiary_name = name
        existing.note = note
        db.flush()
        return existing

    record = CommissionRecord(
        merchant_id=merchant_id,
        rule_id=rule.id,
        scope=scope,
        source_type=source_type,
        source_id=source_id,
        order_id=order_id,
        member_id=member_id,
        beneficiary_type=beneficiary_type,
        beneficiary_id=beneficiary_id,
        beneficiary_name=name,
        base_amount=_quantize(Decimal(base_amount or 0)),
        quantity=quantity,
        rate=rule.rate,
        amount=amount,
        status=CommissionStatus.PENDING.value,
        note=note,
    )
    db.add(record)
    db.flush()
    return record


def _referrer_of(db: Session, member: Member) -> tuple[str, int] | None:
    """解析会员的推荐人；优先推广位主体，其次推荐会员，最后推荐员工。"""
    if member.referral_code:
        promoter = db.scalar(
            select(PromoterCode).where(PromoterCode.code == member.referral_code)
        )
        if promoter is not None:
            if promoter.subject_member_id is not None:
                return BeneficiaryType.MEMBER.value, promoter.subject_member_id
            if promoter.subject_staff_id is not None:
                return BeneficiaryType.STAFF.value, promoter.subject_staff_id
    if member.referrer_member_id is not None:
        return BeneficiaryType.MEMBER.value, member.referrer_member_id
    if member.referrer_staff_id is not None:
        return BeneficiaryType.STAFF.value, member.referrer_staff_id
    return None


def _referral_rule(db: Session, member: Member, merchant_id: int, at: datetime) -> CommissionRule | None:
    """推广位可单独指定推广规则，未指定时回落商户默认推荐规则。"""
    if member.referral_code:
        promoter = db.scalar(
            select(PromoterCode).where(PromoterCode.code == member.referral_code)
        )
        if promoter is not None and promoter.commission_rule_id is not None:
            rule = db.get(CommissionRule, promoter.commission_rule_id)
            if rule is not None and rule.is_active and rule.scope == CommissionScope.REFERRAL.value:
                return rule
    return find_rule(db, merchant_id=merchant_id, scope=CommissionScope.REFERRAL.value, at=at)


def accrue_order_commissions(db: Session, order: Order) -> list[CommissionRecord]:
    """订单收款后计提销售提成与推荐提成。"""
    if order.status != OrderStatus.PAID.value:
        return []
    scope = next((s for s, order_type in ORDER_SCOPES.items() if order_type == order.order_type), None)
    created: list[CommissionRecord] = []
    at = _ensure_aware(order.created_at) or _now()
    base = Decimal(order.amount or 0)

    if scope is not None and order.seller_staff_id is not None:
        rule = find_rule(db, merchant_id=order.merchant_id, scope=scope, at=at)
        if rule is not None:
            amount = compute_amount(rule, base_amount=base)
            if amount > 0:
                record = _upsert_record(
                    db,
                    merchant_id=order.merchant_id,
                    rule=rule,
                    scope=scope,
                    source_type="order",
                    source_id=order.id,
                    beneficiary_type=BeneficiaryType.STAFF.value,
                    beneficiary_id=order.seller_staff_id,
                    base_amount=base,
                    quantity=1,
                    amount=amount,
                    order_id=order.id,
                    member_id=order.member_id,
                    note=f"{order.title} 销售提成",
                )
                if record is not None:
                    created.append(record)

    if order.member_id is not None:
        member = db.get(Member, order.member_id)
        if member is not None:
            _accrue_referral(db, order, member, base=base, at=at, created=created)
    return created


def _accrue_referral(
    db: Session,
    order: Order,
    member: Member,
    *,
    base: Decimal,
    at: datetime,
    created: list[CommissionRecord],
) -> None:
    """推荐收益分流：上级会员进返点账户，推荐员工进提成记录。"""
    rule = _referral_rule(db, member, order.merchant_id, at)
    upline = resolve_upline(db, member)
    if upline is not None:
        fallback: Decimal | None = None
        if upline.rebate_rate <= 0 and rule is not None:
            first_order_blocked = rule.first_order_only and has_prior_earn(
                db, from_member_id=member.id, exclude_order_id=order.id
            )
            if not first_order_blocked:
                fallback = compute_amount(rule, base_amount=base)
        accrue_order_rebate(db, order, upline=upline, fallback_amount=fallback)
        return

    referrer = _referrer_of(db, member)
    if referrer is None or referrer[0] != BeneficiaryType.STAFF.value or rule is None:
        return
    if rule.first_order_only and _has_prior_referral(db, member.id, order.id):
        return
    amount = compute_amount(rule, base_amount=base)
    if amount <= 0:
        return
    record = _upsert_record(
        db,
        merchant_id=order.merchant_id,
        rule=rule,
        scope=CommissionScope.REFERRAL.value,
        source_type="order",
        source_id=order.id,
        beneficiary_type=referrer[0],
        beneficiary_id=referrer[1],
        base_amount=base,
        quantity=1,
        amount=amount,
        order_id=order.id,
        member_id=order.member_id,
        note=f"推荐 {member.name} 消费提成",
    )
    if record is not None:
        created.append(record)


def _has_prior_referral(db: Session, member_id: int, order_id: int) -> bool:
    """判断该会员是否已产生过推荐提成（仅首单计提场景使用）。"""
    row = db.scalar(
        select(CommissionRecord.id)
        .where(
            CommissionRecord.scope == CommissionScope.REFERRAL.value,
            CommissionRecord.member_id == member_id,
            CommissionRecord.status != CommissionStatus.VOID.value,
            CommissionRecord.source_id != order_id,
        )
        .limit(1)
    )
    return row is not None


def accrue_group_session_commission(
    db: Session, *, merchant_id: int, session_id: int, coach_id: int, attended_count: int, at: datetime
) -> CommissionRecord | None:
    """团课按出席人数计提教练提成；签到变动时重算未结算记录。"""
    rule = find_rule(
        db, merchant_id=merchant_id, scope=CommissionScope.GROUP_SESSION.value, at=at
    )
    if rule is None:
        return None
    amount = compute_amount(rule, base_amount=Decimal("0"), quantity=attended_count)
    if amount <= 0:
        return None
    return _upsert_record(
        db,
        merchant_id=merchant_id,
        rule=rule,
        scope=CommissionScope.GROUP_SESSION.value,
        source_type="group_session",
        source_id=session_id,
        beneficiary_type=BeneficiaryType.COACH.value,
        beneficiary_id=coach_id,
        base_amount=Decimal("0"),
        quantity=attended_count,
        amount=amount,
        note=f"团课出席 {attended_count} 人",
    )


def accrue_pt_session_commission(
    db: Session,
    *,
    merchant_id: int,
    appointment_id: int,
    coach_id: int,
    member_id: int,
    base_amount: Decimal,
    at: datetime,
) -> CommissionRecord | None:
    """私教课完成后计提教练课时提成：教练个人比例优先，商户规则兜底。"""
    coach = db.get(Coach, coach_id)
    personal_rate = None if coach is None else coach.pt_commission_rate
    if personal_rate is not None and Decimal(personal_rate) > 0:
        rate = Decimal(personal_rate)
        amount = _quantize(Decimal(base_amount or 0) * rate)
        if amount <= 0:
            return None
        return _upsert_personal_record(
            db,
            merchant_id=merchant_id,
            appointment_id=appointment_id,
            coach_id=coach_id,
            member_id=member_id,
            base_amount=Decimal(base_amount or 0),
            rate=rate,
            amount=amount,
        )

    rule = find_rule(db, merchant_id=merchant_id, scope=CommissionScope.PT_SESSION.value, at=at)
    if rule is None:
        return None
    amount = compute_amount(rule, base_amount=base_amount, quantity=1)
    if amount <= 0:
        return None
    return _upsert_record(
        db,
        merchant_id=merchant_id,
        rule=rule,
        scope=CommissionScope.PT_SESSION.value,
        source_type="pt_appointment",
        source_id=appointment_id,
        beneficiary_type=BeneficiaryType.COACH.value,
        beneficiary_id=coach_id,
        base_amount=base_amount,
        quantity=1,
        amount=amount,
        member_id=member_id,
        note="私教课时提成",
    )


def _upsert_personal_record(
    db: Session,
    *,
    merchant_id: int,
    appointment_id: int,
    coach_id: int,
    member_id: int,
    base_amount: Decimal,
    rate: Decimal,
    amount: Decimal,
) -> CommissionRecord | None:
    """按教练个人比例写提成记录（无规则 id）。"""
    name = _beneficiary_name(db, BeneficiaryType.COACH.value, coach_id)
    if name is None:
        return None
    note = f"私教课时提成（教练个人比例 {rate}）"
    existing = db.scalar(
        select(CommissionRecord).where(
            CommissionRecord.scope == CommissionScope.PT_SESSION.value,
            CommissionRecord.source_type == "pt_appointment",
            CommissionRecord.source_id == appointment_id,
            CommissionRecord.beneficiary_type == BeneficiaryType.COACH.value,
            CommissionRecord.beneficiary_id == coach_id,
        )
    )
    if existing is not None:
        if existing.status != CommissionStatus.PENDING.value:
            return existing
        existing.rule_id = None
        existing.base_amount = _quantize(base_amount)
        existing.quantity = 1
        existing.rate = rate
        existing.amount = amount
        existing.beneficiary_name = name
        existing.note = note
        db.flush()
        return existing
    record = CommissionRecord(
        merchant_id=merchant_id,
        rule_id=None,
        scope=CommissionScope.PT_SESSION.value,
        source_type="pt_appointment",
        source_id=appointment_id,
        member_id=member_id,
        beneficiary_type=BeneficiaryType.COACH.value,
        beneficiary_id=coach_id,
        beneficiary_name=name,
        base_amount=_quantize(base_amount),
        quantity=1,
        rate=rate,
        amount=amount,
        status=CommissionStatus.PENDING.value,
        note=note,
    )
    db.add(record)
    db.flush()
    return record


def void_records_for_order(db: Session, order_id: int) -> int:
    """订单全额退款时作废提成；已打款记录一并标记，需人工扣回。"""
    rows = list(
        db.scalars(
            select(CommissionRecord).where(
                CommissionRecord.order_id == order_id,
                CommissionRecord.status.in_(
                    [
                        CommissionStatus.PENDING.value,
                        CommissionStatus.CONFIRMED.value,
                        CommissionStatus.PAID.value,
                    ]
                ),
            )
        ).all()
    )
    for row in rows:
        paid = row.status == CommissionStatus.PAID.value
        row.status = CommissionStatus.VOID.value
        suffix = "（订单退款自动作废，已打款需人工扣回）" if paid else "（订单退款自动作废）"
        row.note = (row.note or "") + suffix
    db.flush()
    return len(rows)


def scale_records_for_partial_refund(
    db: Session,
    order: Order,
    *,
    refund_amount: Decimal,
) -> int:
    """部分退按剩余实付比例下调未结算提成。"""
    paid_after = _quantize(Decimal(order.amount or 0) - Decimal(order.refunded_amount or 0))
    paid_before = paid_after + _quantize(refund_amount)
    if paid_before <= 0:
        return 0
    rows = list(
        db.scalars(
            select(CommissionRecord).where(
                CommissionRecord.order_id == order.id,
                CommissionRecord.status.in_(
                    [CommissionStatus.PENDING.value, CommissionStatus.CONFIRMED.value]
                ),
            )
        ).all()
    )
    changed = 0
    for row in rows:
        new_amount = _quantize(Decimal(row.amount or 0) * paid_after / paid_before)
        row.base_amount = _quantize(Decimal(row.base_amount or 0) * paid_after / paid_before)
        if new_amount <= 0:
            row.amount = Decimal("0.00")
            row.status = CommissionStatus.VOID.value
            row.note = (row.note or "") + "（部分退款后提成为零，已作废）"
        else:
            row.amount = new_amount
            row.note = (row.note or "") + "（部分退款按比例下调）"
        changed += 1
    db.flush()
    return changed


_ALLOWED_TRANSITIONS = {
    CommissionStatus.PENDING.value: {CommissionStatus.CONFIRMED.value, CommissionStatus.VOID.value},
    CommissionStatus.CONFIRMED.value: {CommissionStatus.PAID.value, CommissionStatus.VOID.value},
    CommissionStatus.PAID.value: set(),
    CommissionStatus.VOID.value: set(),
}


def change_record_status(db: Session, record: CommissionRecord, status: str) -> CommissionRecord:
    """按待确认 → 已确认 → 已结算流转；任意非终态可作废。"""
    if status not in {s.value for s in CommissionStatus}:
        raise AppError("invalid_status", "未知提成状态", status_code=400)
    if status == record.status:
        return record
    if status not in _ALLOWED_TRANSITIONS[record.status]:
        raise AppError("invalid_state", "当前状态不允许该操作", status_code=400)
    record.status = status
    record.settled_at = _now() if status == CommissionStatus.PAID.value else None
    db.flush()
    return record
