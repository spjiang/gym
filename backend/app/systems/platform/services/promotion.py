"""统一推广方案：会员一人一码、一级上下级关联与下级消费折扣。

关联口径：会员只认自己注册时绑定的那一个推广码（或人工设置的推荐会员），
计算返点与折扣时不向上递归，因此永远只有一级关系。
"""

from __future__ import annotations

import secrets
import string
from dataclasses import dataclass
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.systems.platform.models.member import Member
from app.systems.platform.models.promoter import PromoterChannel, PromoterCode, PromoterSubjectType
from app.systems.platform.models.rebate import SitePromotionSettings

_CENT = Decimal("0.01")
_RATE = Decimal("0.0001")
MIN_PAYABLE = Decimal("0.01")
# 折扣与返点比例上限，避免误配成负毛利
MAX_DISCOUNT_RATE = Decimal("0.9")
MAX_REBATE_RATE = Decimal("1")

_CODE_ALPHABET = (
    (string.ascii_uppercase + string.digits)
    .replace("O", "")
    .replace("I", "")
    .replace("0", "")
    .replace("1", "")
)


@dataclass(frozen=True)
class EffectivePromotionSettings:
    """场地推广默认值；无配置行时给出零默认。"""

    site_id: int
    auto_create_member_code: bool
    default_rebate_rate: Decimal
    default_downline_discount_rate: Decimal
    min_withdraw_amount: Decimal
    withdraw_hold_days: int
    configured: bool


@dataclass(frozen=True)
class UplineInfo:
    """会员的一级上级及其生效比例。"""

    member_id: int
    member_name: str
    promoter: PromoterCode | None
    rebate_rate: Decimal
    discount_rate: Decimal
    rate_source: str  # promoter | site_default | none


@dataclass(frozen=True)
class DiscountQuote:
    """下级折扣报价。"""

    original_amount: Decimal
    discount_amount: Decimal
    payable: Decimal
    rate: Decimal
    promoter_code: str | None
    upline_member_id: int | None


def money(value: Decimal | int | float | str | None) -> Decimal:
    return Decimal(str(value or 0)).quantize(_CENT, rounding=ROUND_HALF_UP)


def rate_of(value: Decimal | int | float | str | None) -> Decimal:
    return Decimal(str(value or 0)).quantize(_RATE, rounding=ROUND_HALF_UP)


def resolve_promotion_settings(db: Session, site_id: int) -> EffectivePromotionSettings:
    """读取场地推广默认值；未配置时返回零默认，不写库。"""
    row = db.scalar(
        select(SitePromotionSettings).where(SitePromotionSettings.site_id == site_id)
    )
    if row is None:
        return EffectivePromotionSettings(
            site_id=site_id,
            auto_create_member_code=True,
            default_rebate_rate=Decimal("0"),
            default_downline_discount_rate=Decimal("0"),
            min_withdraw_amount=Decimal("1.00"),
            withdraw_hold_days=0,
            configured=False,
        )
    return EffectivePromotionSettings(
        site_id=site_id,
        auto_create_member_code=bool(row.auto_create_member_code),
        default_rebate_rate=rate_of(row.default_rebate_rate),
        default_downline_discount_rate=rate_of(row.default_downline_discount_rate),
        min_withdraw_amount=money(row.min_withdraw_amount),
        withdraw_hold_days=max(0, int(row.withdraw_hold_days or 0)),
        configured=True,
    )


def get_or_create_settings_row(db: Session, site_id: int) -> SitePromotionSettings:
    """取配置行用于写入；不存在则按默认值建行。"""
    row = db.scalar(
        select(SitePromotionSettings).where(SitePromotionSettings.site_id == site_id)
    )
    if row is None:
        row = SitePromotionSettings(site_id=site_id)
        db.add(row)
        db.flush()
    return row


def validate_rebate_rate(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    rate = rate_of(value)
    if rate < 0 or rate > MAX_REBATE_RATE:
        raise AppError("invalid_rate", "返点比例需在 0~1 之间", status_code=400)
    return rate


def validate_discount_rate(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    rate = rate_of(value)
    if rate < 0 or rate > MAX_DISCOUNT_RATE:
        raise AppError("invalid_rate", "下级折扣比例需在 0~0.9 之间", status_code=400)
    return rate


def generate_promoter_code(db: Session) -> str:
    """生成 8 位大写推广码，去除易混字符。"""
    for _ in range(20):
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))
        if db.scalar(select(PromoterCode.id).where(PromoterCode.code == code)) is None:
            return code
    raise AppError("code_exhausted", "推广码生成失败，请重试", status_code=500)


def member_promoter_code(db: Session, member: Member) -> PromoterCode | None:
    """会员自己的推广位（一人一码）。"""
    return db.scalar(
        select(PromoterCode).where(
            PromoterCode.site_id == member.site_id,
            PromoterCode.subject_type == PromoterSubjectType.MEMBER.value,
            PromoterCode.subject_member_id == member.id,
        )
    )


def ensure_member_promoter_code(
    db: Session, member: Member, *, force: bool = False
) -> PromoterCode | None:
    """为会员补齐个人推广位；已存在则返回。

    force=True 表示运营显式打开该会员推广配置，忽略场地「自动建码」开关。
    """
    existing = member_promoter_code(db, member)
    if existing is not None:
        return existing
    settings = resolve_promotion_settings(db, member.site_id)
    if not force and not settings.auto_create_member_code:
        return None
    promoter = PromoterCode(
        site_id=member.site_id,
        # 会员推广位为场地级：下级在任意商户消费都返点给上级
        merchant_id=None,
        code=generate_promoter_code(db),
        name=f"{member.name}的推广码",
        subject_type=PromoterSubjectType.MEMBER.value,
        subject_member_id=member.id,
        channel=PromoterChannel.MEMBER_SHARE.value,
        is_active=True,
    )
    db.add(promoter)
    db.flush()
    return promoter


def resolve_upline(db: Session, member: Member) -> UplineInfo | None:
    """解析会员的一级上级会员及生效比例；员工推荐不在此列。"""
    upline_id: int | None = None
    promoter: PromoterCode | None = None
    if member.referral_code:
        promoter = db.scalar(
            select(PromoterCode).where(PromoterCode.code == member.referral_code)
        )
        if promoter is not None and promoter.subject_member_id is not None:
            upline_id = promoter.subject_member_id
        else:
            promoter = None
    if upline_id is None:
        upline_id = member.referrer_member_id
        promoter = None
    if upline_id is None or upline_id == member.id:
        return None

    upline = db.get(Member, upline_id)
    if upline is None or upline.site_id != member.site_id:
        return None

    settings = resolve_promotion_settings(db, member.site_id)
    rebate = None if promoter is None else promoter.rebate_rate
    discount = None if promoter is None else promoter.downline_discount_rate
    source = "none"
    if rebate is not None or discount is not None:
        source = "promoter"
    elif settings.configured:
        source = "site_default"
    return UplineInfo(
        member_id=upline.id,
        member_name=upline.name,
        promoter=promoter,
        rebate_rate=rate_of(rebate if rebate is not None else settings.default_rebate_rate),
        discount_rate=rate_of(
            discount if discount is not None else settings.default_downline_discount_rate
        ),
        rate_source=source,
    )


def quote_downline_discount(
    db: Session, *, member_id: int | None, original_amount: Decimal
) -> DiscountQuote:
    """按上级推广位配置计算下级折扣；无上级或比例为 0 时零折扣。"""
    original = money(original_amount)
    empty = DiscountQuote(
        original_amount=original,
        discount_amount=Decimal("0.00"),
        payable=original,
        rate=Decimal("0"),
        promoter_code=None,
        upline_member_id=None,
    )
    if member_id is None or original <= 0:
        return empty
    member = db.get(Member, member_id)
    if member is None:
        return empty
    upline = resolve_upline(db, member)
    if upline is None:
        return empty
    if upline.promoter is not None and not upline.promoter.is_active:
        return empty
    rate = rate_of(upline.discount_rate)
    if rate <= 0:
        return empty

    # 折扣向下取整到分，避免让商家多让利
    discount = (original * rate).quantize(_CENT, rounding=ROUND_DOWN)
    payable = original - discount
    if payable < MIN_PAYABLE:
        payable = MIN_PAYABLE
        discount = original - payable
    if discount <= 0:
        return empty
    return DiscountQuote(
        original_amount=original,
        discount_amount=discount,
        payable=payable,
        rate=rate,
        promoter_code=upline.promoter.code if upline.promoter is not None else None,
        upline_member_id=upline.member_id,
    )


def downline_query(db: Session, *, member: Member):
    """会员一级下级列表查询语句。"""
    promoter = member_promoter_code(db, member)
    conditions = [Member.referrer_member_id == member.id]
    if promoter is not None:
        conditions.append(Member.referral_code == promoter.code)
    return (
        select(Member)
        .where(Member.site_id == member.site_id, Member.id != member.id, or_(*conditions))
        .order_by(Member.id.desc())
    )


def count_downline(db: Session, *, member: Member) -> int:
    """会员的一级下级人数。"""
    return len(list(db.scalars(downline_query(db, member=member)).all()))
