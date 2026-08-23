"""商户/会员与场地、子系统的归属校验。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import RequestContext
from app.core.errors import AppError
from app.systems.platform.models.member import Member, MerchantMember
from app.systems.platform.models.org import Merchant, MerchantSubsystem


def assert_merchant_in_site(db: Session, ctx: RequestContext, merchant_id: int) -> Merchant:
    """校验商户属于当前场地。"""
    merchant = db.get(Merchant, merchant_id)
    if merchant is None or merchant.site_id != ctx.site_id:
        raise AppError("not_found", "商户不存在", status_code=404)
    return merchant


def gym_merchant_ids(db: Session, site_id: int) -> list[int]:
    """当前场地已开通健身子系统的商户 id。"""
    return list(
        db.scalars(
            select(Merchant.id)
            .join(MerchantSubsystem, MerchantSubsystem.merchant_id == Merchant.id)
            .where(Merchant.site_id == site_id, MerchantSubsystem.system_code == "gym")
        ).all()
    )


def assert_member_in_scope(db: Session, ctx: RequestContext, member_id: int) -> Member:
    """场地级账号可操作全场会员；商户账号仅可操作挂靠会员。"""
    member = db.get(Member, member_id)
    if member is None or member.site_id != ctx.site_id:
        raise AppError("not_found", "会员不存在", status_code=404)
    if not ctx.is_site_wide:
        mid = ctx.resolve_merchant_id()
        linked = db.scalar(
            select(MerchantMember.id).where(
                MerchantMember.member_id == member.id,
                MerchantMember.merchant_id == mid,
            )
        )
        if linked is None:
            raise AppError("forbidden", "无权操作该会员", status_code=403)
    return member
