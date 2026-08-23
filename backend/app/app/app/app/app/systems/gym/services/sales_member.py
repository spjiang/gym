"""销售与会员主档关联：销售提成统一走会员受益人。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.systems.gym.models.commission import (
    BeneficiaryType,
    CommissionRecord,
    CommissionStatus,
)
from app.systems.gym.models.sales import SalesRep
from app.systems.platform.models.member import Member, MerchantMember
from app.systems.platform.services.promotion import ensure_member_promoter_code


def _ensure_merchant_link(db: Session, *, member_id: int, merchant_id: int) -> None:
    exists = db.scalar(
        select(MerchantMember.id).where(
            MerchantMember.member_id == member_id,
            MerchantMember.merchant_id == merchant_id,
        )
    )
    if exists is None:
        db.add(MerchantMember(member_id=member_id, merchant_id=merchant_id))
        db.flush()


def reassign_sales_commission_to_member(db: Session, *, sales_rep: SalesRep, member: Member) -> None:
    """未结算的销售提成从 staff 受益人迁到绑定会员。"""
    name = f"{member.name} {member.phone}"
    rows = list(
        db.scalars(
            select(CommissionRecord).where(
                CommissionRecord.beneficiary_type == BeneficiaryType.STAFF.value,
                CommissionRecord.beneficiary_id == sales_rep.staff_user_id,
                CommissionRecord.status.in_(
                    [CommissionStatus.PENDING.value, CommissionStatus.CONFIRMED.value]
                ),
            )
        ).all()
    )
    for row in rows:
        row.beneficiary_type = BeneficiaryType.MEMBER.value
        row.beneficiary_id = member.id
        row.beneficiary_name = name
    if rows:
        db.flush()


def link_sales_member(
    db: Session,
    *,
    sales_rep: SalesRep,
    site_id: int,
    merchant_id: int,
    member_id: int,
) -> Member:
    """绑定已有会员主档。"""
    member = db.get(Member, member_id)
    if member is None or member.site_id != site_id:
        raise AppError("invalid_member", "会员不存在", status_code=400)

    other = db.scalar(
        select(SalesRep.id).where(SalesRep.member_id == member.id, SalesRep.id != sales_rep.id)
    )
    if other is not None:
        raise AppError("member_in_use", "该会员已绑定其他销售档案", status_code=400)

    sales_rep.member_id = member.id
    _ensure_merchant_link(db, member_id=member.id, merchant_id=merchant_id)
    ensure_member_promoter_code(db, member, force=True)
    reassign_sales_commission_to_member(db, sales_rep=sales_rep, member=member)
    db.flush()
    return member


def sales_rep_from_staff(db: Session, staff_user_id: int) -> SalesRep | None:
    return db.scalar(
        select(SalesRep).where(
            SalesRep.staff_user_id == staff_user_id,
            SalesRep.is_active.is_(True),
        )
    )


def require_sales_member(db: Session, sales_rep: SalesRep) -> Member:
    member = db.get(Member, sales_rep.member_id)
    if member is None:
        raise AppError("invalid_member", "销售关联会员不存在", status_code=400)
    return member


def sales_member_beneficiary(db: Session, staff_user_id: int) -> tuple[str, int] | None:
    """开单员工 → 销售绑定会员；档案或会员异常时跳过销售提成。"""
    rep = sales_rep_from_staff(db, staff_user_id)
    if rep is None:
        return None
    member = db.get(Member, rep.member_id)
    if member is None:
        return None
    return BeneficiaryType.MEMBER.value, member.id
