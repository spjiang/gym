"""本人提成：销售与教练统一解析受益人与记录范围。"""

from __future__ import annotations

from dataclasses import dataclass

from decimal import Decimal

from sqlalchemy import false, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import ColumnElement

from app.core.errors import AppError
from app.systems.gym.models.commission import (
    BeneficiaryType,
    CommissionCategory,
    CommissionRecord,
    CommissionStatus,
)
from app.systems.gym.models.course import Coach
from app.systems.gym.models.sales import SalesRep
from app.systems.gym.services.sales_member import sales_rep_from_staff
from app.systems.platform.models.payout import Payout, PayoutItem, PayoutSource, PayoutStatus
from app.systems.platform.services.promotion import money


@dataclass
class SelfCommissionIdentity:
    """登录员工对应的销售/教练身份。"""

    staff_id: int
    coach: Coach | None
    sales_rep: SalesRep | None
    display_name: str
    merchant_id: int | None

    @property
    def roles(self) -> list[str]:
        tags: list[str] = []
        if self.sales_rep is not None:
            tags.append("sales")
        if self.coach is not None:
            tags.append("coach")
        return tags

    def beneficiaries(self) -> list[tuple[str, int, str]]:
        """提现/欠额查询用的受益人列表（去重）。"""
        seen: set[tuple[str, int]] = set()
        rows: list[tuple[str, int, str]] = []
        if self.coach is not None:
            if self.coach.member_id is not None:
                key = (BeneficiaryType.MEMBER.value, self.coach.member_id)
            else:
                key = (BeneficiaryType.COACH.value, self.coach.id)
            if key not in seen:
                seen.add(key)
                rows.append((key[0], key[1], self.coach.display_name))
        if self.sales_rep is not None and self.sales_rep.member_id is not None:
            key = (BeneficiaryType.MEMBER.value, self.sales_rep.member_id)
            if key not in seen:
                seen.add(key)
                rows.append((key[0], key[1], self.sales_rep.display_name))
        return rows


def resolve_self_commission_identity(db: Session, staff_id: int) -> SelfCommissionIdentity:
    coaches = list(db.scalars(select(Coach).where(Coach.staff_user_id == staff_id)).all())
    if len(coaches) > 1:
        raise AppError(
            "coach_staff_ambiguous",
            "当前员工绑定了多个教练档案，请先在教练档案中解除多余绑定",
            status_code=400,
        )
    coach = coaches[0] if coaches else None
    sales_rep = sales_rep_from_staff(db, staff_id)
    if coach is None and sales_rep is None:
        raise AppError("not_found", "当前账号未绑定销售或教练档案", status_code=404)

    display_name = coach.display_name if coach is not None else sales_rep.display_name  # type: ignore[union-attr]
    merchant_id = coach.merchant_id if coach is not None else sales_rep.merchant_id  # type: ignore[union-attr]
    if coach is not None and sales_rep is not None:
        display_name = f"{sales_rep.display_name} / {coach.display_name}"

    return SelfCommissionIdentity(
        staff_id=staff_id,
        coach=coach,
        sales_rep=sales_rep,
        display_name=display_name,
        merchant_id=merchant_id,
    )


def _coach_record_clause(coach: Coach) -> ColumnElement[bool]:
    clauses: list[ColumnElement[bool]] = [
        (CommissionRecord.beneficiary_type == BeneficiaryType.COACH.value)
        & (CommissionRecord.beneficiary_id == coach.id),
        CommissionRecord.coach_id == coach.id,
    ]
    if coach.member_id is not None:
        clauses.append(
            (CommissionRecord.beneficiary_type == BeneficiaryType.MEMBER.value)
            & (CommissionRecord.beneficiary_id == coach.member_id)
            & (
                (CommissionRecord.coach_id == coach.id)
                | (
                    CommissionRecord.coach_id.is_(None)
                    & (CommissionRecord.category == CommissionCategory.SESSION.value)
                )
            )
        )
    return or_(*clauses)


def _sales_record_clause(sales_rep: SalesRep) -> ColumnElement[bool]:
    if sales_rep.member_id is None:
        return false()
    clauses: list[ColumnElement[bool]] = [
        (CommissionRecord.beneficiary_type == BeneficiaryType.MEMBER.value)
        & (CommissionRecord.beneficiary_id == sales_rep.member_id)
        & (CommissionRecord.category == CommissionCategory.SALE.value),
        (CommissionRecord.beneficiary_type == BeneficiaryType.STAFF.value)
        & (CommissionRecord.beneficiary_id == sales_rep.staff_user_id),
    ]
    return or_(*clauses)


def self_record_clause(identity: SelfCommissionIdentity) -> ColumnElement[bool]:
    """本人可见提成：销售开单 + 教练课时（并集）。"""
    clauses: list[ColumnElement[bool]] = []
    if identity.sales_rep is not None:
        clauses.append(_sales_record_clause(identity.sales_rep))
    if identity.coach is not None:
        clauses.append(_coach_record_clause(identity.coach))
    if not clauses:
        return false()
    return or_(*clauses)


def settleable_records(db: Session, identity: SelfCommissionIdentity) -> list[CommissionRecord]:
    """可提现记录：已确认、冷却期满且未被提现单占用。"""
    rows = list(
        db.scalars(
            select(CommissionRecord)
            .where(
                self_record_clause(identity),
                CommissionRecord.status == CommissionStatus.CONFIRMED.value,
            )
            .order_by(CommissionRecord.id.asc())
        ).all()
    )
    if not rows:
        return []
    from app.systems.gym.services.commission_policy import record_ready_to_settle, settle_hold_days, site_id_of_merchant

    site_id = site_id_of_merchant(db, identity.merchant_id or rows[0].merchant_id)
    days = settle_hold_days(db, site_id)
    rows = [r for r in rows if record_ready_to_settle(r, days)]
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


def withdrawing_amount(db: Session, identity: SelfCommissionIdentity) -> Decimal:
    total = money("0")
    for btype, bid, _name in identity.beneficiaries():
        for row in db.scalars(
            select(Payout).where(
                Payout.source == PayoutSource.COMMISSION.value,
                Payout.beneficiary_type == btype,
                Payout.beneficiary_id == bid,
                Payout.status.in_([PayoutStatus.REQUESTED.value, PayoutStatus.APPROVED.value]),
            )
        ).all():
            total += money(row.amount)
    # 兼容历史以 coach 档案为抬头的提现单
    if identity.coach is not None:
        for row in db.scalars(
            select(Payout).where(
                Payout.source == PayoutSource.COMMISSION.value,
                Payout.beneficiary_type == BeneficiaryType.COACH.value,
                Payout.beneficiary_id == identity.coach.id,
                Payout.status.in_([PayoutStatus.REQUESTED.value, PayoutStatus.APPROVED.value]),
            )
        ).all():
            total += money(row.amount)
    return total


def debt_amount(db: Session, identity: SelfCommissionIdentity) -> Decimal:
    from app.systems.gym.services.commission_policy import debt_of, site_id_of_merchant

    if identity.merchant_id is None:
        return money("0")
    site_id = site_id_of_merchant(db, identity.merchant_id)
    total = money("0")
    for btype, bid, _name in identity.beneficiaries():
        total += debt_of(db, site_id=site_id, beneficiary_type=btype, beneficiary_id=bid)
    return total
