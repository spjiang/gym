"""活动与活动报名 API。"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import RequestContext, get_current_context
from app.core.config import get_settings
from app.core.domain.member_brief import load_member_briefs
from app.core.domain.subsystems import assert_merchant_has_system
from app.core.errors import AppError
from app.core.schemas.common import MemberBrief, OrderOut
from app.core.schemas.paging import PageOut, paginate
from app.systems.gym.models.activity import (
    Activity,
    ActivityRegistration,
    ActivityStatus,
    RegistrationStatus,
)
from app.systems.gym.services.activity_ops import (
    effective_price as activity_price,
    now_utc,
    register_activity,
    registered_counts,
)
from app.systems.platform.models.commerce import Order, OrderStatus
from app.systems.platform.models.member import Member
from app.systems.platform.models.org import Merchant
from app.systems.platform.services.audit import write_audit
from app.systems.platform.services.notifications import write_notification

router = APIRouter(tags=["activity"])

_COVER_URL_RE = re.compile(r"^/api/v1/files/[0-9a-f]{32}\.(jpg|png|webp)$")


def _normalize_cover_url(url: str | None) -> str | None:
    text = (url or "").strip() or None
    if text is None:
        return None
    if not _COVER_URL_RE.match(text):
        raise AppError("invalid_image", "活动海报地址无效，请通过系统上传", status_code=400)
    return text


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def _now() -> datetime:
    return now_utc()


def _ensure_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class ActivityIn(BaseModel):
    merchant_id: int | None = None
    name: str = Field(min_length=1, max_length=128)
    category: str | None = Field(default=None, max_length=64)
    location: str | None = Field(default=None, max_length=128)
    cover_url: str | None = Field(default=None, max_length=255)
    description: str | None = None
    starts_at: datetime
    ends_at: datetime
    register_ends_at: datetime | None = None
    capacity: int = Field(default=0, ge=0, le=100000)
    price: Decimal = Decimal("0")
    member_price: Decimal | None = None


class ActivityPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    category: str | None = Field(default=None, max_length=64)
    location: str | None = Field(default=None, max_length=128)
    cover_url: str | None = Field(default=None, max_length=255)
    description: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    register_ends_at: datetime | None = None
    capacity: int | None = Field(default=None, ge=0, le=100000)
    price: Decimal | None = None
    member_price: Decimal | None = None


class ActivityOut(ORMModel):
    id: int
    merchant_id: int
    name: str
    category: str | None
    location: str | None
    cover_url: str | None
    description: str | None
    starts_at: datetime
    ends_at: datetime
    register_ends_at: datetime | None
    capacity: int
    price: Decimal
    member_price: Decimal | None
    requires_payment: bool
    status: str
    created_at: datetime
    registered_count: int = 0
    attended_count: int = 0
    remaining_capacity: int | None = None


class RegistrationIn(BaseModel):
    activity_id: int
    member_id: int
    note: str | None = Field(default=None, max_length=255)


class RegistrationOut(ORMModel):
    id: int
    activity_id: int
    merchant_id: int
    member_id: int
    status: str
    amount: Decimal
    order_id: int | None
    checked_in_at: datetime | None
    note: str | None
    created_at: datetime
    member: MemberBrief | None = None
    activity_name: str | None = None
    activity_starts_at: datetime | None = None


class RegistrationCreateOut(BaseModel):
    registration: RegistrationOut
    order: OrderOut | None = None


class NoShowIn(BaseModel):
    note: str | None = Field(default=None, max_length=255)


def _activity_out(row: Activity, counts: tuple[int, int] | None = None) -> ActivityOut:
    registered, attended = counts or (0, 0)
    remaining = None if row.capacity <= 0 else max(row.capacity - registered, 0)
    return ActivityOut(
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
        price=row.price,
        member_price=row.member_price,
        requires_payment=row.requires_payment,
        status=row.status,
        created_at=row.created_at,
        registered_count=registered,
        attended_count=attended,
        remaining_capacity=remaining,
    )


def _validate_window(starts_at: datetime, ends_at: datetime, register_ends_at: datetime | None) -> None:
    start = _ensure_aware(starts_at)
    end = _ensure_aware(ends_at)
    if start is None or end is None or end <= start:
        raise AppError("invalid_time", "活动结束时间必须晚于开始时间", status_code=400)
    reg_end = _ensure_aware(register_ends_at)
    if reg_end is not None and reg_end > end:
        raise AppError("invalid_time", "报名截止时间不可晚于活动结束时间", status_code=400)


def _effective_price_from(price: Decimal, member_price: Decimal | None) -> Decimal:
    """会员价优先。"""
    return Decimal(member_price) if member_price is not None else Decimal(price or 0)


@router.get("/activities", response_model=PageOut[ActivityOut])
def list_activities(
    merchant_id: int | None = None,
    q: str | None = None,
    status: str | None = None,
    category: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("activity:manage", "activity:register")
    mid = ctx.resolve_merchant_id(merchant_id, required=False)
    stmt = select(Activity)
    if mid is not None:
        stmt = stmt.where(Activity.merchant_id == mid)
    else:
        stmt = stmt.where(
            Activity.merchant_id.in_(select(Merchant.id).where(Merchant.site_id == ctx.site_id))
        )
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        conds = [Activity.name.ilike(like), Activity.location.ilike(like)]
        if keyword.isdigit():
            conds.append(Activity.id == int(keyword))
        stmt = stmt.where(or_(*conds))
    if status:
        stmt = stmt.where(Activity.status == status)
    if category:
        stmt = stmt.where(Activity.category == category)
    if date_from is not None:
        stmt = stmt.where(Activity.starts_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(Activity.starts_at <= date_to)

    rows, total = paginate(db, stmt.order_by(Activity.starts_at.desc()), page=page, page_size=page_size)
    counts = registered_counts(db, {r.id for r in rows})
    return PageOut(
        items=[_activity_out(r, counts.get(r.id)) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/activities/{activity_id}", response_model=ActivityOut)
def get_activity(
    activity_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("activity:manage", "activity:register")
    activity = db.get(Activity, activity_id)
    if activity is None:
        raise AppError("not_found", "活动不存在", status_code=404)
    ctx.resolve_merchant_id(activity.merchant_id)
    counts = registered_counts(db, {activity.id})
    return _activity_out(activity, counts.get(activity.id))


@router.get("/activities/{activity_id}/share-link")
def activity_share_link(
    activity_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """会员 H5 活动详情链接，供海报二维码。"""
    ctx.require_permission("activity:manage", "activity:register")
    activity = db.get(Activity, activity_id)
    if activity is None:
        raise AppError("not_found", "活动不存在", status_code=404)
    ctx.resolve_merchant_id(activity.merchant_id)
    base = get_settings().member_web_public_url.rstrip("/")
    return {
        "activity_id": activity.id,
        "url": f"{base}/m/{activity.merchant_id}/gym/activities/{activity.id}",
    }


@router.post("/activities", response_model=ActivityOut)
def create_activity(
    body: ActivityIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("activity:manage")
    mid = ctx.resolve_merchant_id(body.merchant_id)
    merchant = db.get(Merchant, mid)
    if merchant is None or merchant.site_id != ctx.site_id:
        raise AppError("not_found", "商户不存在", status_code=404)
    assert_merchant_has_system(db, mid, "gym")
    _validate_window(body.starts_at, body.ends_at, body.register_ends_at)
    price = Decimal(body.price or 0)
    member_price = None if body.member_price is None else Decimal(body.member_price)
    if price < 0 or (member_price is not None and member_price < 0):
        raise AppError("invalid_price", "活动价格不能为负数", status_code=400)

    activity = Activity(
        merchant_id=mid,
        name=body.name.strip(),
        category=(body.category or "").strip() or None,
        location=(body.location or "").strip() or None,
        cover_url=_normalize_cover_url(body.cover_url),
        description=(body.description or "").strip() or None,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        register_ends_at=body.register_ends_at,
        capacity=body.capacity,
        price=price,
        member_price=member_price,
        requires_payment=_effective_price_from(price, member_price) > 0,
        status=ActivityStatus.DRAFT.value,
    )
    db.add(activity)
    db.flush()
    write_audit(
        db,
        action="activity.create",
        target_type="activity",
        target_id=activity.id,
        summary=f"创建活动 {activity.name}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=mid,
    )
    db.commit()
    db.refresh(activity)
    return _activity_out(activity)


@router.patch("/activities/{activity_id}", response_model=ActivityOut)
def update_activity(
    activity_id: int,
    body: ActivityPatch,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("activity:manage")
    activity = db.get(Activity, activity_id)
    if activity is None:
        raise AppError("not_found", "活动不存在", status_code=404)
    ctx.resolve_merchant_id(activity.merchant_id)
    if activity.status == ActivityStatus.CANCELLED.value:
        raise AppError("invalid_state", "已取消活动不可编辑", status_code=400)
    changed = set(body.model_fields_set)

    if "name" in changed and body.name:
        activity.name = body.name.strip()
    for field in ("category", "location", "description"):
        if field in changed:
            value = getattr(body, field)
            setattr(activity, field, (value or "").strip() or None)
    if "cover_url" in changed:
        activity.cover_url = _normalize_cover_url(body.cover_url)
    starts_at = body.starts_at if "starts_at" in changed else activity.starts_at
    ends_at = body.ends_at if "ends_at" in changed else activity.ends_at
    register_ends_at = (
        body.register_ends_at if "register_ends_at" in changed else activity.register_ends_at
    )
    _validate_window(starts_at, ends_at, register_ends_at)
    activity.starts_at = starts_at
    activity.ends_at = ends_at
    activity.register_ends_at = register_ends_at

    if "capacity" in changed and body.capacity is not None:
        counts = registered_counts(db, {activity.id}).get(activity.id, (0, 0))
        if body.capacity and body.capacity < counts[0]:
            raise AppError("invalid_capacity", f"名额不可小于已报名人数 {counts[0]}", status_code=400)
        activity.capacity = body.capacity
    if "price" in changed and body.price is not None:
        if Decimal(body.price) < 0:
            raise AppError("invalid_price", "活动价格不能为负数", status_code=400)
        activity.price = Decimal(body.price)
    if "member_price" in changed:
        if body.member_price is not None and Decimal(body.member_price) < 0:
            raise AppError("invalid_price", "会员价不能为负数", status_code=400)
        activity.member_price = None if body.member_price is None else Decimal(body.member_price)
    activity.requires_payment = activity_price(activity) > 0 > 0

    write_audit(
        db,
        action="activity.update",
        target_type="activity",
        target_id=activity.id,
        summary=f"更新活动 {activity.name}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=activity.merchant_id,
    )
    db.commit()
    db.refresh(activity)
    counts = registered_counts(db, {activity.id})
    return _activity_out(activity, counts.get(activity.id))


_STATUS_TRANSITIONS = {
    ActivityStatus.DRAFT.value: {ActivityStatus.PUBLISHED.value, ActivityStatus.CANCELLED.value},
    ActivityStatus.PUBLISHED.value: {ActivityStatus.CLOSED.value, ActivityStatus.CANCELLED.value},
    ActivityStatus.CLOSED.value: {ActivityStatus.PUBLISHED.value, ActivityStatus.CANCELLED.value},
    ActivityStatus.CANCELLED.value: set(),
}


def _change_activity_status(
    activity_id: int,
    *,
    action: str,
    target: str,
    db: Session,
    ctx: RequestContext,
) -> ActivityOut:
    """发布 / 关闭报名 / 取消活动的公共流转。"""
    ctx.require_permission("activity:manage")
    activity = db.get(Activity, activity_id)
    if activity is None:
        raise AppError("not_found", "活动不存在", status_code=404)
    ctx.resolve_merchant_id(activity.merchant_id)
    if target not in _STATUS_TRANSITIONS[activity.status]:
        raise AppError("invalid_state", "当前状态不允许该操作", status_code=400)
    if target == ActivityStatus.PUBLISHED.value:
        _validate_window(activity.starts_at, activity.ends_at, activity.register_ends_at)

    activity.status = target
    if target == ActivityStatus.CANCELLED.value:
        rows = list(
            db.scalars(
                select(ActivityRegistration).where(
                    ActivityRegistration.activity_id == activity.id,
                    ActivityRegistration.status.in_(
                        [RegistrationStatus.PENDING.value, RegistrationStatus.CONFIRMED.value]
                    ),
                )
            ).all()
        )
        for row in rows:
            row.status = RegistrationStatus.CANCELLED.value
            write_notification(
                db,
                site_id=ctx.site_id,
                merchant_id=activity.merchant_id,
                member_id=row.member_id,
                event_type="activity.cancelled",
                title="活动已取消",
                body=f"「{activity.name}」已取消，如已付款请联系前台办理退款",
            )
    write_audit(
        db,
        action=f"activity.{action}",
        target_type="activity",
        target_id=activity.id,
        summary=f"活动状态变更为 {target}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=activity.merchant_id,
    )
    db.commit()
    db.refresh(activity)
    counts = registered_counts(db, {activity.id})
    return _activity_out(activity, counts.get(activity.id))


@router.post("/activities/{activity_id}/publish", response_model=ActivityOut)
def publish_activity(
    activity_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    return _change_activity_status(
        activity_id,
        action="publish",
        target=ActivityStatus.PUBLISHED.value,
        db=db,
        ctx=ctx,
    )


@router.post("/activities/{activity_id}/close", response_model=ActivityOut)
def close_activity(
    activity_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    return _change_activity_status(
        activity_id,
        action="close",
        target=ActivityStatus.CLOSED.value,
        db=db,
        ctx=ctx,
    )


@router.post("/activities/{activity_id}/cancel", response_model=ActivityOut)
def cancel_activity(
    activity_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    return _change_activity_status(
        activity_id,
        action="cancel",
        target=ActivityStatus.CANCELLED.value,
        db=db,
        ctx=ctx,
    )


def _registration_out(
    row: ActivityRegistration,
    *,
    briefs: dict[int, MemberBrief] | None = None,
    activity: Activity | None = None,
) -> RegistrationOut:
    member = (briefs or {}).get(row.member_id)
    return RegistrationOut(
        id=row.id,
        activity_id=row.activity_id,
        merchant_id=row.merchant_id,
        member_id=row.member_id,
        status=row.status,
        amount=row.amount,
        order_id=row.order_id,
        checked_in_at=row.checked_in_at,
        note=row.note,
        created_at=row.created_at,
        member=member,
        activity_name=activity.name if activity else None,
        activity_starts_at=activity.starts_at if activity else None,
    )


@router.get("/activity-registrations", response_model=PageOut[RegistrationOut])
def list_registrations(
    merchant_id: int | None = None,
    activity_id: int | None = None,
    status: str | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("activity:manage", "activity:register")
    mid = ctx.resolve_merchant_id(merchant_id, required=False)
    stmt = select(ActivityRegistration)
    if mid is not None:
        stmt = stmt.where(ActivityRegistration.merchant_id == mid)
    else:
        stmt = stmt.where(
            ActivityRegistration.merchant_id.in_(
                select(Merchant.id).where(Merchant.site_id == ctx.site_id)
            )
        )
    if activity_id is not None:
        stmt = stmt.where(ActivityRegistration.activity_id == activity_id)
    if status:
        stmt = stmt.where(ActivityRegistration.status == status)
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        member_ids = select(Member.id).where(or_(Member.phone.ilike(like), Member.name.ilike(like)))
        activity_ids = select(Activity.id).where(Activity.name.ilike(like))
        stmt = stmt.where(
            or_(
                ActivityRegistration.member_id.in_(member_ids),
                ActivityRegistration.activity_id.in_(activity_ids),
            )
        )

    rows, total = paginate(
        db, stmt.order_by(ActivityRegistration.id.desc()), page=page, page_size=page_size
    )
    briefs = load_member_briefs(db, {r.member_id for r in rows})
    activities = {
        a.id: a
        for a in db.scalars(
            select(Activity).where(Activity.id.in_({r.activity_id for r in rows} or {-1}))
        ).all()
    }
    items = [
        _registration_out(r, briefs=briefs, activity=activities.get(r.activity_id)) for r in rows
    ]
    return PageOut(items=items, total=total, page=page, page_size=page_size)


@router.post("/activity-registrations", response_model=RegistrationCreateOut)
def create_registration(
    body: RegistrationIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """前台代报名；收费活动同时生成待支付订单。"""
    ctx.require_permission("activity:register", "activity:manage")
    activity = db.get(Activity, body.activity_id)
    if activity is None:
        raise AppError("not_found", "活动不存在", status_code=404)
    ctx.resolve_merchant_id(activity.merchant_id)
    member = db.get(Member, body.member_id)
    if member is None or member.site_id != ctx.site_id:
        raise AppError("not_found", "会员不存在", status_code=404)
    registration, order = register_activity(
        db,
        activity,
        member,
        note=body.note,
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
    )
    db.commit()
    db.refresh(registration)
    if order is not None:
        db.refresh(order)
    briefs = load_member_briefs(db, {registration.member_id})
    return RegistrationCreateOut(
        registration=_registration_out(registration, briefs=briefs, activity=activity),
        order=OrderOut.model_validate(order) if order is not None else None,
    )


@router.post("/activity-registrations/{registration_id}/cancel", response_model=RegistrationOut)
def cancel_registration(
    registration_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("activity:register", "activity:manage")
    registration = db.get(ActivityRegistration, registration_id)
    if registration is None:
        raise AppError("not_found", "报名记录不存在", status_code=404)
    ctx.resolve_merchant_id(registration.merchant_id)
    if registration.status not in {
        RegistrationStatus.PENDING.value,
        RegistrationStatus.CONFIRMED.value,
    }:
        raise AppError("invalid_state", "当前状态不可取消", status_code=400)
    if registration.order_id is not None:
        order = db.get(Order, registration.order_id)
        if order is not None and order.status == OrderStatus.PAID.value:
            raise AppError("order_paid", "报名费已收款，请先在订单中退款", status_code=400)
        if order is not None and order.status == OrderStatus.PENDING.value:
            order.status = OrderStatus.CANCELLED.value

    registration.status = RegistrationStatus.CANCELLED.value
    write_audit(
        db,
        action="activity.registration_cancel",
        target_type="activity_registration",
        target_id=registration.id,
        summary="取消报名",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=registration.merchant_id,
    )
    db.commit()
    db.refresh(registration)
    briefs = load_member_briefs(db, {registration.member_id})
    return _registration_out(
        registration, briefs=briefs, activity=db.get(Activity, registration.activity_id)
    )


@router.post("/activity-registrations/{registration_id}/checkin", response_model=RegistrationOut)
def checkin_registration(
    registration_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """活动现场签到。"""
    ctx.require_permission("activity:register", "activity:manage")
    registration = db.get(ActivityRegistration, registration_id)
    if registration is None:
        raise AppError("not_found", "报名记录不存在", status_code=404)
    ctx.resolve_merchant_id(registration.merchant_id)
    if registration.status == RegistrationStatus.ATTENDED.value:
        raise AppError("already_checked_in", "该会员已签到", status_code=400)
    if registration.status != RegistrationStatus.CONFIRMED.value:
        raise AppError("invalid_state", "仅已确认报名可签到，收费活动请先收款", status_code=400)

    registration.status = RegistrationStatus.ATTENDED.value
    registration.checked_in_at = _now()
    write_audit(
        db,
        action="activity.checkin",
        target_type="activity_registration",
        target_id=registration.id,
        summary="活动签到",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=registration.merchant_id,
    )
    db.commit()
    db.refresh(registration)
    briefs = load_member_briefs(db, {registration.member_id})
    return _registration_out(
        registration, briefs=briefs, activity=db.get(Activity, registration.activity_id)
    )


@router.post("/activity-registrations/{registration_id}/no-show", response_model=RegistrationOut)
def mark_registration_no_show(
    registration_id: int,
    body: NoShowIn | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("activity:register", "activity:manage")
    registration = db.get(ActivityRegistration, registration_id)
    if registration is None:
        raise AppError("not_found", "报名记录不存在", status_code=404)
    ctx.resolve_merchant_id(registration.merchant_id)
    if registration.status != RegistrationStatus.CONFIRMED.value:
        raise AppError("invalid_state", "仅已确认报名可标记未到", status_code=400)
    registration.status = RegistrationStatus.NO_SHOW.value
    if body is not None and body.note:
        registration.note = body.note.strip() or None
    write_audit(
        db,
        action="activity.no_show",
        target_type="activity_registration",
        target_id=registration.id,
        summary="标记活动未到",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=registration.merchant_id,
    )
    db.commit()
    db.refresh(registration)
    briefs = load_member_briefs(db, {registration.member_id})
    return _registration_out(
        registration, briefs=briefs, activity=db.get(Activity, registration.activity_id)
    )
