"""活动报名：前台代报与会员自助共用。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.systems.gym.models.activity import (
    OCCUPYING_REGISTRATION_STATUS,
    Activity,
    ActivityRegistration,
    ActivityStatus,
    RegistrationStatus,
)
from app.systems.platform.models.commerce import Order, OrderStatus
from app.systems.platform.models.member import Member, MerchantMember
from app.systems.platform.services.audit import write_audit
from app.systems.platform.services.notifications import write_notification
from app.systems.gym.services.coupon import detach_coupon_link_for_order
from app.systems.platform.services.order_pricing import price_order

PENDING_HOLD_MINUTES = 30


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def ensure_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def registered_counts(db: Session, activity_ids: set[int]) -> dict[int, tuple[int, int]]:
    """返回 {活动 id: (占位报名数, 已签到数)}。"""
    if not activity_ids:
        return {}
    rows = db.execute(
        select(
            ActivityRegistration.activity_id,
            ActivityRegistration.status,
            func.count().label("cnt"),
        )
        .where(ActivityRegistration.activity_id.in_(activity_ids))
        .group_by(ActivityRegistration.activity_id, ActivityRegistration.status)
    ).all()
    out: dict[int, tuple[int, int]] = {}
    for activity_id, status, cnt in rows:
        registered, attended = out.get(activity_id, (0, 0))
        if status in OCCUPYING_REGISTRATION_STATUS:
            registered += int(cnt)
        if status == RegistrationStatus.ATTENDED.value:
            attended += int(cnt)
        out[activity_id] = (registered, attended)
    return out


def effective_price(activity: Activity) -> Decimal:
    if activity.member_price is not None:
        return Decimal(activity.member_price)
    return Decimal(activity.price or 0)


def occupying_registration(
    db: Session, activity_id: int, member_id: int
) -> ActivityRegistration | None:
    row = db.scalar(
        select(ActivityRegistration).where(
            ActivityRegistration.activity_id == activity_id,
            ActivityRegistration.member_id == member_id,
        )
    )
    if row is None:
        return None
    if row.status in OCCUPYING_REGISTRATION_STATUS:
        return row
    return None


def assert_open_for_register(activity: Activity, *, now: datetime | None = None) -> None:
    if activity.status != ActivityStatus.PUBLISHED.value:
        raise AppError("activity_not_open", "活动未在报名中", status_code=400)
    current = now or now_utc()
    reg_end = ensure_aware(activity.register_ends_at) or ensure_aware(activity.starts_at)
    if reg_end is not None and current > reg_end:
        raise AppError("register_closed", "报名已截止", status_code=400)


def can_register(activity: Activity, *, registered: int, now: datetime | None = None) -> bool:
    try:
        assert_open_for_register(activity, now=now)
    except AppError:
        return False
    if activity.capacity and registered >= activity.capacity:
        return False
    return True


def release_stale_pending_registrations(db: Session, activity_id: int) -> int:
    """释放超时未支付的占坑报名，避免收费活动名额被长期占用。"""
    cutoff = now_utc() - timedelta(minutes=PENDING_HOLD_MINUTES)
    rows = list(
        db.scalars(
            select(ActivityRegistration).where(
                ActivityRegistration.activity_id == activity_id,
                ActivityRegistration.status == RegistrationStatus.PENDING.value,
            )
        ).all()
    )
    released = 0
    for row in rows:
        order = db.get(Order, row.order_id) if row.order_id else None
        if order is None or order.status != OrderStatus.PENDING.value:
            continue
        created = ensure_aware(order.created_at) or ensure_aware(row.created_at)
        if created is None or created >= cutoff:
            continue
        order.status = OrderStatus.CANCELLED.value
        detach_coupon_link_for_order(db, order)
        row.status = RegistrationStatus.CANCELLED.value
        released += 1
    if released:
        db.flush()
    return released


def register_activity(
    db: Session,
    activity: Activity,
    member: Member,
    *,
    note: str | None = None,
    actor_staff_id: int | None = None,
    site_id: int,
    link_merchant: bool = True,
) -> tuple[ActivityRegistration, Order | None]:
    """报名活动。收费则生成待支付订单，免费直接确认。"""
    locked = db.get(Activity, activity.id, with_for_update=True)
    if locked is None:
        raise AppError("not_found", "活动不存在", status_code=404)
    activity = locked
    release_stale_pending_registrations(db, activity.id)
    assert_open_for_register(activity)
    mid = activity.merchant_id
    if member.site_id != site_id:
        raise AppError("not_found", "会员不存在", status_code=404)

    if link_merchant:
        link = db.scalar(
            select(MerchantMember).where(
                MerchantMember.member_id == member.id, MerchantMember.merchant_id == mid
            )
        )
        if link is None:
            db.add(MerchantMember(member_id=member.id, merchant_id=mid))
            db.flush()

    existing = db.scalar(
        select(ActivityRegistration).where(
            ActivityRegistration.activity_id == activity.id,
            ActivityRegistration.member_id == member.id,
        )
    )
    if existing is not None and existing.status in OCCUPYING_REGISTRATION_STATUS:
        raise AppError("already_registered", "该会员已报名此活动", status_code=409)

    counts = registered_counts(db, {activity.id}).get(activity.id, (0, 0))
    if activity.capacity and counts[0] >= activity.capacity:
        raise AppError("activity_full", "活动名额已满", status_code=409)

    price = effective_price(activity)
    if existing is not None:
        registration = existing
        registration.status = RegistrationStatus.PENDING.value
        registration.amount = price
        registration.order_id = None
        registration.checked_in_at = None
        registration.note = (note or "").strip() or None
    else:
        registration = ActivityRegistration(
            activity_id=activity.id,
            merchant_id=mid,
            member_id=member.id,
            status=RegistrationStatus.PENDING.value,
            amount=price,
            note=(note or "").strip() or None,
        )
        db.add(registration)
    db.flush()

    order: Order | None = None
    if price > 0:
        order = Order(
            site_id=site_id,
            merchant_id=mid,
            member_id=member.id,
            order_type="activity",
            title=f"活动报名-{activity.name}",
            amount=price,
            status=OrderStatus.PENDING.value,
            seller_staff_id=actor_staff_id,
        )
        db.add(order)
        db.flush()
        registration.amount = price_order(db, order=order, original_amount=price)
        registration.order_id = order.id
    else:
        registration.status = RegistrationStatus.CONFIRMED.value
        write_notification(
            db,
            site_id=site_id,
            merchant_id=mid,
            member_id=member.id,
            event_type="activity.registered",
            title="活动报名成功",
            body=f"「{activity.name}」报名已确认",
        )

    write_audit(
        db,
        action="activity.register",
        target_type="activity_registration",
        target_id=registration.id,
        summary=f"报名活动 {activity.name} member={member.id} 金额 ¥{price}",
        actor_staff_id=actor_staff_id,
        site_id=site_id,
        merchant_id=mid,
    )
    return registration, order
