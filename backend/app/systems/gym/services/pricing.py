"""活动价计算。"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def effective_price(
    list_price: Decimal,
    promo_price: Decimal | None,
    promo_starts_at: datetime | None,
    promo_ends_at: datetime | None,
    *,
    now: datetime | None = None,
) -> Decimal:
    """活动窗内且活动价为正时返回活动价，否则原价。"""
    if promo_price is None or promo_price <= 0:
        return list_price
    if promo_starts_at is None or promo_ends_at is None:
        return list_price
    current = now or datetime.now(timezone.utc)
    start = _aware(promo_starts_at)
    end = _aware(promo_ends_at)
    assert start is not None and end is not None
    if start <= current <= end:
        return promo_price
    return list_price
