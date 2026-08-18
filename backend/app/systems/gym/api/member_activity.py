"""会员端活动：浏览已发布活动并自助报名。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import MemberContext, get_current_member
from app.core.errors import AppError
from app.core.schemas.common import OrderOut
from app.systems.gym.models.activity import Activity, ActivityRegistration, ActivityStatus, RegistrationStatus
from app.systems.gym.services.activity_ops import (
    can_register,
    effective_price,
    now_utc,
    occupying_registration,
    register_activity,
    registered_counts,
)
from app.systems.platform.models.commerce import Order, OrderStatus
from app.systems.platform.services.audit import write_audit

router = APIRouter(prefix="/member", tags=["member-activity"])


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MemberActivityOut(BaseModel):
    id: int
    merchant_id: int
    name: str
    category: str | None = None
    location: str | None = None
    cover_url: str | None = None
    description: str | None = None
    starts_at: datetime
    ends_at: datetime
    register_ends_at: datetime | None = None
    capacity: int
    price: Decimal
    member_price: Decimal | None = None
    requires_payment: bool
    status: str
    registered_count: int = 0
    remaining_capacity: int | None = None
    already_registered: bool = False
    my_registration_id: int | None = None
    my_registration_status: str | None = None
    my_order_id: int | None = None
    can_register: bool = False


class MemberRegistrationOut(ORMModel):
    id: int
    activity_id: int
    merchant_id: int
    status: str
    amount: Decimal
    order_id: int | None = None
    created_at: datetime
    activity_name: str | None = None
    activity_starts_at: datetime | None = None
    location: str | None = None
    category: str | None = None


class MemberRegisterIn(BaseModel):
    merchant_id: int
    activity_id: int


class MemberRegisterOut(BaseModel):
    registration: MemberRegistrationOut
    order: OrderOut | None = None


def _activity_card(
    row: Activity,
    *,
    registered: int,
    mine: ActivityRegistration | None,
    now: datetime,
) -> MemberActivityOut:
    remaining = None if row.capacity <= 0 else max(row.capacity - registered, 0)
    occupying = mine is not None and mine.status in {
        RegistrationStatus.PENDING.value,
        RegistrationStatus.CONFIRMED.value,
        RegistrationStatus.ATTENDED.value,
        RegistrationStatus.NO_SHOW.value,
    }
    return MemberActivityOut(
        id=row.id,
        merchant_id=row.merchant_id,
        name=row.name,
        category=row.category,
        location=row.location,
        cover_url=row.cover_url,
        description=row.description,
        starts_at=row.starts_at,
        ends_at=row.ends_at,
        register_ends_at=row.register_ends_at,
        capacity=row.capacity,
        price=effective_price(row),
        member_price=row.member_price,
        requires_payment=row.requires_payment,
        status=row.status,
        registered_count=registered,
        remaining_capacity=remaining,
        already_registered=occupying,
        my_registration_id=mine.id if mine else None,
        my_registration_status=mine.status if mine else None,
        my_order_id=mine.order_id if mine else None,
        can_register=can_register(row, registered=registered, now=now) and not occupying,
    )


def _registration_out(row: ActivityRegistration, activity: Activity | None) -> MemberRegistrationOut:
    return MemberRegistrationOut(
        id=row.id,
        activity_id=row.activity_id,
        merchant_id=row.merchant_id,
        status=row.status,
        amount=row.amount,
        order_id=row.order_id,
        created_at=row.created_at,
        activity_name=activity.name if activity else None,
        activity_starts_at=activity.starts_at if activity else None,
        location=activity.location if activity else None,
        category=activity.category if activity else None,
    )


def list_published_activities(
    db: Session,
    *,
    merchant_id: int,
    member_id: int,
    limit: int | None = None,
) -> list[MemberActivityOut]:
    now = now_utc()
    stmt = (
        select(Activity)
        .where(
            Activity.merchant_id == merchant_id,
            Activity.status == ActivityStatus.PUBLISHED.value,
            Activity.ends_at >= now,
        )
        .order_by(Activity.starts_at.asc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    rows = list(db.scalars(stmt).all())
    counts = registered_counts(db, {r.id for r in rows})
    mines = {
        r.activity_id: r
        for r in db.scalars(
            select(ActivityRegistration).where(
                ActivityRegistration.member_id == member_id,
                ActivityRegistration.activity_id.in_({row.id for row in rows} or {-1}),
            )
        ).all()
    }
    return [
        _activity_card(row, registered=counts.get(row.id, (0, 0))[0], mine=mines.get(row.id), now=now)
        for row in rows
    ]


@router.get("/activities", response_model=list[MemberActivityOut])
def list_member_activities(
    merchant_id: int,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    mctx.require_merchant(db, merchant_id)
    return list_published_activities(db, merchant_id=merchant_id, member_id=mctx.member.id)


@router.get("/activities/{activity_id}", response_model=MemberActivityOut)
def get_member_activity(
    activity_id: int,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    activity = db.get(Activity, activity_id)
    if activity is None:
        raise AppError("not_found", "活动不存在", status_code=404)
    mctx.require_merchant(db, activity.merchant_id)
    if activity.status != ActivityStatus.PUBLISHED.value:
        raise AppError("not_found", "活动不存在或未开放报名", status_code=404)
    counts = registered_counts(db, {activity.id}).get(activity.id, (0, 0))
    mine = occupying_registration(db, activity.id, mctx.member.id)
    if mine is None:
        mine = db.scalar(
            select(ActivityRegistration).where(
                ActivityRegistration.activity_id == activity.id,
                ActivityRegistration.member_id == mctx.member.id,
            )
        )
    return _activity_card(activity, registered=counts[0], mine=mine, now=now_utc())


@router.get("/activity-registrations", response_model=list[MemberRegistrationOut])
def list_my_activity_registrations(
    merchant_id: int,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    mctx.require_merchant(db, merchant_id)
    rows = list(
        db.scalars(
            select(ActivityRegistration)
            .where(
                ActivityRegistration.merchant_id == merchant_id,
                ActivityRegistration.member_id == mctx.member.id,
            )
            .order_by(ActivityRegistration.id.desc())
        ).all()
    )
    activities = {
        a.id: a
        for a in db.scalars(
            select(Activity).where(Activity.id.in_({r.activity_id for r in rows} or {-1}))
        ).all()
    }
    return [_registration_out(r, activities.get(r.activity_id)) for r in rows]


@router.post("/activity-registrations", response_model=MemberRegisterOut)
def create_my_activity_registration(
    body: MemberRegisterIn,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    mctx.require_merchant(db, body.merchant_id)
    activity = db.get(Activity, body.activity_id)
    if activity is None or activity.merchant_id != body.merchant_id:
        raise AppError("not_found", "活动不存在", status_code=404)
    registration, order = register_activity(
        db,
        activity,
        mctx.member,
        actor_staff_id=None,
        site_id=mctx.site_id,
        link_merchant=False,
    )
    db.commit()
    db.refresh(registration)
    if order is not None:
        db.refresh(order)
    return MemberRegisterOut(
        registration=_registration_out(registration, activity),
        order=OrderOut.model_validate(order) if order is not None else None,
    )


@router.post("/activity-registrations/{registration_id}/cancel", response_model=MemberRegistrationOut)
def cancel_my_activity_registration(
    registration_id: int,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    registration = db.get(ActivityRegistration, registration_id)
    if registration is None or registration.member_id != mctx.member.id:
        raise AppError("not_found", "报名记录不存在", status_code=404)
    if registration.status not in {RegistrationStatus.PENDING.value, RegistrationStatus.CONFIRMED.value}:
        raise AppError("invalid_state", "当前状态不可取消", status_code=400)
    if registration.order_id is not None:
        order = db.get(Order, registration.order_id)
        if order is not None and order.status == OrderStatus.PAID.value:
            raise AppError("order_paid", "报名费已支付，请联系前台退款", status_code=400)
        if order is not None and order.status == OrderStatus.PENDING.value:
            order.status = OrderStatus.CANCELLED.value
    registration.status = RegistrationStatus.CANCELLED.value
    write_audit(
        db,
        action="activity.registration_cancel",
        target_type="activity_registration",
        target_id=registration.id,
        summary="会员取消报名",
        site_id=mctx.site_id,
        merchant_id=registration.merchant_id,
    )
    db.commit()
    db.refresh(registration)
    return _registration_out(registration, db.get(Activity, registration.activity_id))
