"""教练与会员主档关联：推广与课时收益统一走会员机制。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.systems.gym.models.commission import (
    BeneficiaryType,
    CommissionRecord,
    CommissionStatus,
)
from app.systems.gym.models.course import Coach
from app.systems.platform.models.member import Member, MerchantMember
from app.systems.platform.services.promotion import ensure_member_promoter_code, member_promoter_code


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


def reassign_coach_commission_to_member(db: Session, *, coach: Coach, member: Member) -> None:
    """把仍挂在教练档案上的未结算提成迁到绑定会员，避免「我的佣金」漏看与双轨提现。"""
    name = f"{member.name} {member.phone}"
    rows = list(
        db.scalars(
            select(CommissionRecord).where(
                CommissionRecord.beneficiary_type == BeneficiaryType.COACH.value,
                CommissionRecord.beneficiary_id == coach.id,
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
        row.coach_id = coach.id
    if rows:
        db.flush()


def link_coach_member(
    db: Session,
    *,
    coach: Coach,
    site_id: int,
    merchant_id: int,
    member_id: int,
) -> Member:
    """强制绑定已有会员主档，并确保有推广码。"""
    member = db.get(Member, member_id)
    if member is None or member.site_id != site_id:
        raise AppError("invalid_member", "会员不存在", status_code=400)

    other = db.scalar(
        select(Coach.id).where(Coach.member_id == member.id, Coach.id != coach.id)
    )
    if other is not None:
        raise AppError("member_in_use", "该会员已绑定其他教练", status_code=400)

    coach.member_id = member.id
    _ensure_merchant_link(db, member_id=member.id, merchant_id=merchant_id)
    ensure_member_promoter_code(db, member, force=True)
    reassign_coach_commission_to_member(db, coach=coach, member=member)
    db.flush()
    return member


def require_coach_member(db: Session, coach: Coach) -> Member:
    """课时提成入账前校验教练已绑定会员。"""
    if coach.member_id is None:
        raise AppError(
            "coach_member_required",
            f"教练 {coach.display_name} 未关联会员，无法计提课时提成",
            status_code=400,
        )
    member = db.get(Member, coach.member_id)
    if member is None:
        raise AppError("invalid_member", "教练关联会员不存在", status_code=400)
    return member


def coach_promotion_code(db: Session, coach: Coach) -> str | None:
    if coach.member_id is None:
        return None
    member = db.get(Member, coach.member_id)
    if member is None:
        return None
    promoter = member_promoter_code(db, member)
    if promoter is None:
        promoter = ensure_member_promoter_code(db, member, force=True)
    return promoter.code if promoter is not None else None
