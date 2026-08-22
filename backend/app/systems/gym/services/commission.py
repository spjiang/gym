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
    ALLOWED_BENEFICIARIES_BY_SCOPE,
    ORDER_SCOPES,
    SCOPE_CATEGORY,
    BeneficiaryType,
    CommissionBasis,
    CommissionBeneficiary,
    CommissionCategory,
    CommissionRecord,
    CommissionRule,
    CommissionScope,
    CommissionStatus,
)
from app.systems.gym.models.course import Coach
from app.systems.gym.services.coach_member import require_coach_member
from app.systems.gym.services.sales_member import sales_member_beneficiary, sales_rep_from_staff
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
        if _rule_effective_at(rule, moment):
            return rule
    return None


def _rule_effective_at(rule: CommissionRule, moment: datetime) -> bool:
    starts = _ensure_aware(rule.effective_from)
    ends = _ensure_aware(rule.effective_to)
    if starts is not None and moment < starts:
        return False
    if ends is not None and moment >= ends:
        return False
    return True


def resolve_rule_by_id(
    db: Session,
    rule_id: int | None,
    *,
    merchant_id: int,
    scope: str,
    at: datetime | None = None,
) -> CommissionRule | None:
    """按档案绑定的规则 id 解析；场景或有效期不符则返回 None。"""
    if rule_id is None:
        return None
    rule = db.get(CommissionRule, rule_id)
    if rule is None:
        return None
    moment = _ensure_aware(at) or _now()
    if (
        rule.merchant_id != merchant_id
        or rule.scope != scope
        or not rule.is_active
        or not _rule_effective_at(rule, moment)
    ):
        return None
    return rule


def validate_profile_commission_rule(
    db: Session,
    *,
    rule_id: int | None,
    merchant_id: int,
    allowed_scopes: set[str],
    beneficiary: str | None = None,
) -> None:
    """校验档案绑定的提成规则。"""
    if rule_id is None:
        return
    rule = db.get(CommissionRule, rule_id)
    if rule is None:
        raise AppError("invalid_rule", "提成规则不存在", status_code=400)
    if rule.merchant_id != merchant_id:
        raise AppError("invalid_rule", "提成规则不属于当前商户", status_code=400)
    if rule.scope not in allowed_scopes:
        raise AppError("invalid_rule", "提成规则场景不匹配", status_code=400)
    if beneficiary is not None and rule.beneficiary != beneficiary:
        raise AppError("invalid_rule", "提成规则受益方不匹配", status_code=400)


def resolve_sale_rule_for_order(
    db: Session, order: Order, *, scope: str, at: datetime | None = None
) -> CommissionRule | None:
    """销售档案绑定规则优先，否则回落商户默认规则。"""
    if order.seller_staff_id is not None:
        rep = sales_rep_from_staff(db, order.seller_staff_id)
        if rep is not None and rep.commission_rule_id is not None:
            bound = resolve_rule_by_id(
                db,
                rep.commission_rule_id,
                merchant_id=order.merchant_id,
                scope=scope,
                at=at,
            )
            if bound is not None:
                return bound
    return find_rule(db, merchant_id=order.merchant_id, scope=scope, at=at)


def resolve_group_rule_for_coach(
    db: Session, coach: Coach, *, at: datetime | None = None
) -> CommissionRule | None:
    bound = resolve_rule_by_id(
        db,
        coach.group_commission_rule_id,
        merchant_id=coach.merchant_id,
        scope=CommissionScope.GROUP_SESSION.value,
        at=at,
    )
    if bound is not None:
        return bound
    return find_rule(
        db,
        merchant_id=coach.merchant_id,
        scope=CommissionScope.GROUP_SESSION.value,
        at=at,
    )


def resolve_pt_rule_for_coach(
    db: Session, coach: Coach, *, at: datetime | None = None
) -> CommissionRule | None:
    bound = resolve_rule_by_id(
        db,
        coach.pt_commission_rule_id,
        merchant_id=coach.merchant_id,
        scope=CommissionScope.PT_SESSION.value,
        at=at,
    )
    if bound is not None:
        return bound
    return find_rule(
        db,
        merchant_id=coach.merchant_id,
        scope=CommissionScope.PT_SESSION.value,
        at=at,
    )


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

    allowed = ALLOWED_BENEFICIARIES_BY_SCOPE.get(scope)
    if allowed is None or beneficiary not in allowed:
        raise AppError("invalid_beneficiary", "该场景不支持此受益方", status_code=400)

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


def _coach_member_beneficiary(db: Session, coach: Coach) -> tuple[str, int] | None:
    """课时提成默认归属：教练绑定会员。"""
    try:
        member = require_coach_member(db, coach)
    except AppError:
        return None
    return BeneficiaryType.MEMBER.value, member.id


def _resolve_session_beneficiary(
    db: Session, rule: CommissionRule, coach: Coach
) -> tuple[str, int] | None:
    """按规则受益方解析团课/私教课时提成的实际归属。"""
    role = rule.beneficiary
    if role == CommissionBeneficiary.COACH.value:
        return _coach_member_beneficiary(db, coach)
    if role == CommissionBeneficiary.SELLER.value and coach.staff_user_id is not None:
        return sales_member_beneficiary(db, coach.staff_user_id)
    return None


def _resolve_order_sale_beneficiary(
    db: Session, rule: CommissionRule, order: Order, member: Member | None
) -> tuple[str, int] | None:
    """按规则受益方解析销售类提成的实际归属。"""
    role = rule.beneficiary
    if role == CommissionBeneficiary.SELLER.value:
        if order.seller_staff_id is None:
            return None
        return sales_member_beneficiary(db, order.seller_staff_id)
    if role == CommissionBeneficiary.COACH.value:
        if order.seller_staff_id is None:
            return None
        coach = _coach_from_staff(db, order.seller_staff_id)
        if coach is None:
            return None
        return _coach_member_beneficiary(db, coach)
    return None


def _coach_from_staff(db: Session, staff_id: int) -> Coach | None:
    return db.scalar(select(Coach).where(Coach.staff_user_id == staff_id))


def _beneficiary_name(db: Session, beneficiary_type: str, beneficiary_id: int) -> str | None:
    if beneficiary_type == BeneficiaryType.STAFF.value:
        staff = db.get(StaffUser, beneficiary_id)
        return staff.display_name if staff else None
    if beneficiary_type == BeneficiaryType.COACH.value:
        coach = db.get(Coach, beneficiary_id)
        return coach.display_name if coach else None
    member = db.get(Member, beneficiary_id)
    if member is None:
        return None
    return f"{member.name} {member.phone}"


def _upsert_record(
    db: Session,
    *,
    merchant_id: int,
    rule: CommissionRule | None,
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
    coach_id: int | None = None,
    rate: Decimal | None = None,
    note: str | None = None,
) -> CommissionRecord | None:
    """写入或刷新提成记录；已确认/已结算的记录不再改动。

    课时类同来源只保留一条有效记录：历史若仍挂 coach 受益人，会迁到当前会员，避免重复计提。
    """
    name = _beneficiary_name(db, beneficiary_type, beneficiary_id)
    if name is None:
        return None
    category = SCOPE_CATEGORY.get(scope, CommissionCategory.SALE.value)
    rule_id = rule.id if rule is not None else None
    record_rate = rate if rate is not None else (rule.rate if rule is not None else None)

    existing = db.scalar(
        select(CommissionRecord).where(
            CommissionRecord.scope == scope,
            CommissionRecord.source_type == source_type,
            CommissionRecord.source_id == source_id,
            CommissionRecord.beneficiary_type == beneficiary_type,
            CommissionRecord.beneficiary_id == beneficiary_id,
        )
    )
    # 课时提成：同来源只允许一条有效记录，避免历史 coach 受益人与现会员受益人双记
    if existing is None and scope in {
        CommissionScope.GROUP_SESSION.value,
        CommissionScope.PT_SESSION.value,
    }:
        siblings = list(
            db.scalars(
                select(CommissionRecord).where(
                    CommissionRecord.scope == scope,
                    CommissionRecord.source_type == source_type,
                    CommissionRecord.source_id == source_id,
                    CommissionRecord.status != CommissionStatus.VOID.value,
                )
            ).all()
        )
        if siblings:
            existing = next(
                (r for r in siblings if r.beneficiary_type == beneficiary_type and r.beneficiary_id == beneficiary_id),
                None,
            )
            if existing is None:
                existing = next(
                    (r for r in siblings if r.status == CommissionStatus.PENDING.value),
                    siblings[0],
                )
            for row in siblings:
                if existing is not None and row.id != existing.id and row.status == CommissionStatus.PENDING.value:
                    row.status = CommissionStatus.VOID.value
                    row.note = (row.note or "") + "（同场次受益人归一，作废重复）"

    if existing is not None:
        if existing.status != CommissionStatus.PENDING.value:
            return existing
        existing.rule_id = rule_id
        existing.category = category
        existing.coach_id = coach_id
        existing.base_amount = _quantize(Decimal(base_amount or 0))
        existing.quantity = quantity
        existing.rate = record_rate
        existing.amount = amount
        existing.beneficiary_type = beneficiary_type
        existing.beneficiary_id = beneficiary_id
        existing.beneficiary_name = name
        existing.note = note
        existing.member_id = member_id
        existing.order_id = order_id
        db.flush()
        return existing

    record = CommissionRecord(
        merchant_id=merchant_id,
        rule_id=rule_id,
        scope=scope,
        category=category,
        source_type=source_type,
        source_id=source_id,
        order_id=order_id,
        member_id=member_id,
        coach_id=coach_id,
        beneficiary_type=beneficiary_type,
        beneficiary_id=beneficiary_id,
        beneficiary_name=name,
        base_amount=_quantize(Decimal(base_amount or 0)),
        quantity=quantity,
        rate=record_rate,
        amount=amount,
        status=CommissionStatus.PENDING.value,
        note=note,
    )
    db.add(record)
    db.flush()
    return record


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

    if scope is not None:
        rule = resolve_sale_rule_for_order(db, order, scope=scope, at=at)
        if rule is not None:
            member = db.get(Member, order.member_id) if order.member_id is not None else None
            resolved = _resolve_order_sale_beneficiary(db, rule, order, member)
            if resolved is not None:
                amount = compute_amount(rule, base_amount=base)
                if amount > 0:
                    record = _upsert_record(
                        db,
                        merchant_id=order.merchant_id,
                        rule=rule,
                        scope=scope,
                        source_type="order",
                        source_id=order.id,
                        beneficiary_type=resolved[0],
                        beneficiary_id=resolved[1],
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
    """推荐收益：仅会员上级走返点；推荐成交规则在上级返点为 0 时作 fallback 金额。"""
    rule = _referral_rule(db, member, order.merchant_id, at)
    upline = resolve_upline(db, member)
    if upline is None:
        return
    fallback: Decimal | None = None
    if upline.rebate_rate <= 0 and rule is not None:
        first_order_blocked = rule.first_order_only and has_prior_earn(
            db, from_member_id=member.id, exclude_order_id=order.id
        )
        if not first_order_blocked:
            fallback = compute_amount(rule, base_amount=base)
    accrue_order_rebate(db, order, upline=upline, fallback_amount=fallback)


def accrue_group_session_commission(
    db: Session, *, merchant_id: int, session_id: int, coach_id: int, attended_count: int, at: datetime
) -> CommissionRecord | None:
    """团课按出席人数计提；收益归属教练绑定会员。"""
    coach = db.get(Coach, coach_id)
    if coach is None:
        return None
    rule = resolve_group_rule_for_coach(db, coach, at=at)
    if rule is None:
        return None
    resolved = _resolve_session_beneficiary(db, rule, coach)
    if resolved is None:
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
        beneficiary_type=resolved[0],
        beneficiary_id=resolved[1],
        base_amount=Decimal("0"),
        quantity=attended_count,
        amount=amount,
        coach_id=coach.id,
        note=f"团课出席 {attended_count} 人 · 教练 {coach.display_name}",
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
    """私教课完成后计提：教练个人比例优先，商户规则兜底；收益归属教练绑定会员。"""
    coach = db.get(Coach, coach_id)
    if coach is None:
        return None
    beneficiary = require_coach_member(db, coach)
    personal_rate = coach.pt_commission_rate
    if personal_rate is not None and Decimal(personal_rate) > 0:
        rate = Decimal(personal_rate)
        amount = _quantize(Decimal(base_amount or 0) * rate)
        if amount <= 0:
            return None
        return _upsert_record(
            db,
            merchant_id=merchant_id,
            rule=None,
            scope=CommissionScope.PT_SESSION.value,
            source_type="pt_appointment",
            source_id=appointment_id,
            beneficiary_type=BeneficiaryType.MEMBER.value,
            beneficiary_id=beneficiary.id,
            base_amount=Decimal(base_amount or 0),
            quantity=1,
            amount=amount,
            member_id=member_id,
            coach_id=coach.id,
            rate=rate,
            note=f"私教课时提成（教练个人比例 {rate}）· 教练 {coach.display_name}",
        )

    rule = resolve_pt_rule_for_coach(db, coach, at=at)
    if rule is None:
        return None
    resolved = _resolve_session_beneficiary(db, rule, coach)
    if resolved is None:
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
        beneficiary_type=resolved[0],
        beneficiary_id=resolved[1],
        base_amount=base_amount,
        quantity=1,
        amount=amount,
        member_id=member_id,
        coach_id=coach.id,
        note=f"私教课时提成 · 教练 {coach.display_name}",
    )


def void_records_for_order(
    db: Session, order_id: int, *, refund_id: int | None = None, refund_amount: Decimal | None = None
) -> int:
    """订单全额退款：未打款作废；已打款记欠额，记录保持已结算。"""
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
    from app.systems.gym.services.commission_policy import clawback_paid_record

    changed = 0
    for row in rows:
        if row.status == CommissionStatus.PAID.value:
            if refund_id is not None:
                clawback_paid_record(
                    db, row, refund_id=refund_id, amount=Decimal(row.amount or 0)
                )
            else:
                suffix = "（订单退款自动作废，已打款需人工扣回）"
                row.status = CommissionStatus.VOID.value
                row.note = (row.note or "") + suffix
            changed += 1
            continue
        row.status = CommissionStatus.VOID.value
        row.note = (row.note or "") + "（订单退款自动作废）"
        changed += 1
    db.flush()
    return changed


def scale_records_for_partial_refund(
    db: Session,
    order: Order,
    *,
    refund_amount: Decimal,
    refund_id: int | None = None,
) -> int:
    """部分退：未结算按比例下调；已打款按比例记欠额。"""
    paid_after = _quantize(Decimal(order.amount or 0) - Decimal(order.refunded_amount or 0))
    paid_before = paid_after + _quantize(refund_amount)
    if paid_before <= 0:
        return 0
    ratio = _quantize(refund_amount) / paid_before
    from app.systems.gym.services.commission_policy import clawback_paid_record

    open_rows = list(
        db.scalars(
            select(CommissionRecord).where(
                CommissionRecord.order_id == order.id,
                CommissionRecord.status.in_(
                    [CommissionStatus.PENDING.value, CommissionStatus.CONFIRMED.value]
                ),
            )
        ).all()
    )
    paid_rows = list(
        db.scalars(
            select(CommissionRecord).where(
                CommissionRecord.order_id == order.id,
                CommissionRecord.status == CommissionStatus.PAID.value,
            )
        ).all()
    )
    changed = 0
    for row in open_rows:
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
    if refund_id is not None:
        for row in paid_rows:
            claw = _quantize(Decimal(row.amount or 0) * ratio)
            if claw > 0:
                clawback_paid_record(db, row, refund_id=refund_id, amount=claw)
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
    """按待确认 → 已确认 → 已结算流转；任意非终态可作废。结算时校验冷却并抵扣欠额。"""
    from app.systems.platform.services.payouts import record_locked_by_open_payout

    if status not in {s.value for s in CommissionStatus}:
        raise AppError("invalid_status", "未知提成状态", status_code=400)
    if status == record.status:
        return record
    if status not in _ALLOWED_TRANSITIONS[record.status]:
        raise AppError("invalid_state", "当前状态不允许该操作", status_code=400)
    if status == CommissionStatus.PAID.value and record_locked_by_open_payout(db, record.id):
        raise AppError(
            "record_locked",
            "该提成已纳入提现申请，请通过提现流程结算",
            status_code=400,
        )
    if status == CommissionStatus.PAID.value:
        from app.systems.gym.services.commission_policy import (
            apply_debt_offset,
            assert_record_ready_to_settle,
            site_id_of_merchant,
        )

        assert_record_ready_to_settle(db, record)
        site_id = site_id_of_merchant(db, record.merchant_id)
        applied = apply_debt_offset(
            db,
            site_id=site_id,
            beneficiary_type=record.beneficiary_type,
            beneficiary_id=record.beneficiary_id,
            beneficiary_name=record.beneficiary_name,
            amount=Decimal(record.amount or 0),
            source_type="commission_record",
            source_id=record.id,
            commission_record_id=record.id,
            note=f"结算提成 record={record.id} 抵扣欠额",
        )
        if applied > 0:
            record.note = (record.note or "") + f"（结算抵扣欠额 ¥{applied}）"
    record.status = status
    record.settled_at = _now() if status == CommissionStatus.PAID.value else None
    db.flush()
    return record
