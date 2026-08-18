"""订单统一定价入口。

定价顺序固定为：标价/活动价 → 下级会员推广折扣 → 优惠券 → 实付。
所有建单入口都必须经此函数写价，保证折扣与返点基数口径一致。
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.systems.gym.services.coupon import attach_coupon_to_order, preview_coupon_discount
from app.systems.platform.models.commerce import Order
from app.systems.platform.services.promotion import money, quote_downline_discount


@dataclass(frozen=True)
class PriceQuote:
    original_amount: Decimal
    promotion_discount_amount: Decimal
    promotion_rate: Decimal
    coupon_discount_amount: Decimal
    payable: Decimal
    promoter_code: str | None


def quote_price(
    db: Session,
    *,
    member_id: int | None,
    merchant_id: int,
    order_type: str,
    original_amount: Decimal,
    member_coupon_id: int | None = None,
) -> PriceQuote:
    """预览实付：推广折扣后再叠加优惠券。"""
    original = money(original_amount)
    promo = quote_downline_discount(db, member_id=member_id, original_amount=original)
    payable = promo.payable
    coupon_discount = Decimal("0.00")
    if member_coupon_id is not None:
        if member_id is None:
            raise AppError("coupon_member_required", "用券须指定会员", status_code=400)
        payable, coupon_discount = preview_coupon_discount(
            db,
            member_coupon_id=member_coupon_id,
            merchant_id=merchant_id,
            member_id=member_id,
            order_type=order_type,
            original_amount=payable,
        )
        payable = money(payable)
        coupon_discount = money(coupon_discount)
    return PriceQuote(
        original_amount=original,
        promotion_discount_amount=promo.discount_amount,
        promotion_rate=promo.rate,
        coupon_discount_amount=coupon_discount,
        payable=payable,
        promoter_code=promo.promoter_code,
    )


def price_order(
    db: Session,
    *,
    order: Order,
    original_amount: Decimal,
    member_coupon_id: int | None = None,
) -> Decimal:
    """写入订单原价、推广折扣与实付金额，返回实付。

    调用前订单需已 flush（绑定优惠券需要 order.id）。
    """
    quote = quote_price(
        db,
        member_id=order.member_id,
        merchant_id=order.merchant_id,
        order_type=order.order_type,
        original_amount=original_amount,
        member_coupon_id=None,
    )
    order.original_amount = quote.original_amount
    order.promotion_discount_amount = quote.promotion_discount_amount
    order.promoter_code = quote.promoter_code
    payable = quote.payable

    if member_coupon_id is not None:
        payable = attach_coupon_to_order(
            db,
            order=order,
            member_coupon_id=member_coupon_id,
            original_amount=payable,
            member_id=order.member_id,
        )
    order.amount = money(payable)
    return order.amount
