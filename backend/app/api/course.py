"""教练、私教课包、团课 API。"""

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import ROLE_COACH, RequestContext, get_current_context
from app.domain.subsystems import assert_merchant_has_system
from app.errors import AppError
from app.models.commerce import Order, OrderStatus
from app.models.course import (
    Coach,
    GroupBooking,
    GroupCourse,
    GroupSession,
    GroupSessionStatus,
    PtOrderLink,
    PtPackage,
    PtPackageProduct,
    PtPackageProductCoach,
)
from app.models.identity import StaffUser
from app.models.member import Member
from app.schemas.common import OrderOut
from app.services.audit import write_audit
from app.services.course_booking import (
    book_group_session,
    cancel_group_booking,
    checkin_group_booking,
)
from app.services.pt_fulfillment import consume_pt_package
from app.services.pricing import effective_price

router = APIRouter(tags=["course"])


class CoachIn(BaseModel):
    merchant_id: int | None = None
    staff_user_id: int
    display_name: str
    specialties: str | None = None
    availability_note: str | None = None


class CoachOut(BaseModel):
    id: int
    merchant_id: int
    staff_user_id: int
    display_name: str
    specialties: str | None
    availability_note: str | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class PtProductIn(BaseModel):
    merchant_id: int | None = None
    name: str
    price: Decimal
    session_count: int = Field(gt=0)
    valid_days: int = Field(gt=0)
    all_coaches: bool = True
    coach_ids: list[int] | None = None
    promo_price: Decimal | None = None
    promo_starts_at: datetime | None = None
    promo_ends_at: datetime | None = None


class PtProductOut(BaseModel):
    id: int
    merchant_id: int
    name: str
    price: Decimal
    session_count: int
    valid_days: int
    all_coaches: bool
    is_active: bool
    coach_ids: list[int] = []
    promo_price: Decimal | None = None
    promo_starts_at: datetime | None = None
    promo_ends_at: datetime | None = None
    effective_price: Decimal | None = None

    model_config = ConfigDict(from_attributes=True)


class PtPurchaseIn(BaseModel):
    merchant_id: int | None = None
    member_id: int
    product_id: int


class PtPackageOut(BaseModel):
    id: int
    merchant_id: int
    member_id: int
    product_id: int
    status: str
    remaining_sessions: int
    starts_at: datetime | None
    ends_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class GroupCourseIn(BaseModel):
    merchant_id: int | None = None
    name: str
    difficulty: str | None = None
    default_duration_minutes: int = 60
    default_capacity: int = Field(gt=0)
    book_ahead_minutes: int = 0
    cancel_ahead_minutes: int = 0


class GroupCourseOut(BaseModel):
    id: int
    merchant_id: int
    name: str
    difficulty: str | None
    default_duration_minutes: int
    default_capacity: int
    book_ahead_minutes: int
    cancel_ahead_minutes: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class GroupSessionIn(BaseModel):
    merchant_id: int | None = None
    course_id: int
    coach_id: int
    starts_at: datetime
    ends_at: datetime
    room: str | None = None
    capacity: int | None = None


class GroupSessionOut(BaseModel):
    id: int
    merchant_id: int
    course_id: int
    coach_id: int
    starts_at: datetime
    ends_at: datetime
    room: str | None
    capacity: int
    status: str

    model_config = ConfigDict(from_attributes=True)


class ReassignIn(BaseModel):
    coach_id: int


class BookIn(BaseModel):
    merchant_id: int | None = None
    session_id: int
    member_id: int


class CancelIn(BaseModel):
    force: bool = False


class CheckinIn(BaseModel):
    status: str


class BookingOut(BaseModel):
    id: int
    session_id: int
    merchant_id: int
    member_id: int
    status: str

    model_config = ConfigDict(from_attributes=True)


def _coach_ids_for_product(db: Session, product_id: int) -> list[int]:
    return list(
        db.scalars(
            select(PtPackageProductCoach.coach_id).where(PtPackageProductCoach.product_id == product_id)
        ).all()
    )


def _product_out(db: Session, p: PtPackageProduct) -> PtProductOut:
    return PtProductOut(
        id=p.id,
        merchant_id=p.merchant_id,
        name=p.name,
        price=p.price,
        session_count=p.session_count,
        valid_days=p.valid_days,
        all_coaches=p.all_coaches,
        is_active=p.is_active,
        coach_ids=[] if p.all_coaches else _coach_ids_for_product(db, p.id),
        promo_price=p.promo_price,
        promo_starts_at=p.promo_starts_at,
        promo_ends_at=p.promo_ends_at,
        effective_price=effective_price(p.price, p.promo_price, p.promo_starts_at, p.promo_ends_at),
    )


def _own_coach(db: Session, ctx: RequestContext, merchant_id: int) -> Coach | None:
    return db.scalar(
        select(Coach).where(Coach.merchant_id == merchant_id, Coach.staff_user_id == ctx.staff.id)
    )


def _coach_scope_only(ctx: RequestContext) -> bool:
    return ROLE_COACH in ctx.role_codes and not ctx.is_site_admin and "course:manage" not in ctx.permissions


# —— 教练 ——


@router.get("/coaches", response_model=list[CoachOut])
def list_coaches(
    merchant_id: int | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("coach:manage", "course:manage", "course:book", "course:checkin", "pt:sell")
    mid = ctx.resolve_merchant_id(merchant_id)
    q = select(Coach).where(Coach.merchant_id == mid)
    if _coach_scope_only(ctx):
        q = q.where(Coach.staff_user_id == ctx.staff.id)
    return list(db.scalars(q.order_by(Coach.id.desc())).all())


@router.post("/coaches", response_model=CoachOut)
def create_coach(
    body: CoachIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("coach:manage")
    mid = ctx.resolve_merchant_id(body.merchant_id)
    assert_merchant_has_system(db, mid, "gym")
    staff = db.get(StaffUser, body.staff_user_id)
    if staff is None or staff.site_id != ctx.site_id:
        raise AppError("invalid_staff", "员工不存在", status_code=400)
    coach = Coach(
        merchant_id=mid,
        staff_user_id=body.staff_user_id,
        display_name=body.display_name,
        specialties=body.specialties,
        availability_note=body.availability_note,
        is_active=True,
    )
    db.add(coach)
    db.flush()
    write_audit(
        db,
        action="coach.create",
        target_type="coach",
        target_id=coach.id,
        summary=f"创建教练 {coach.display_name}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=mid,
    )
    db.commit()
    db.refresh(coach)
    return coach


@router.post("/coaches/{coach_id}/deactivate", response_model=CoachOut)
def deactivate_coach(
    coach_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("coach:manage")
    coach = db.get(Coach, coach_id)
    if coach is None:
        raise AppError("not_found", "教练不存在", status_code=404)
    ctx.resolve_merchant_id(coach.merchant_id)
    if not ctx.is_site_admin and coach.merchant_id != ctx.merchant_id:
        raise AppError("forbidden", "禁止跨商户", status_code=403)
    coach.is_active = False
    write_audit(
        db,
        action="coach.deactivate",
        target_type="coach",
        target_id=coach.id,
        summary="停用教练",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=coach.merchant_id,
    )
    db.commit()
    db.refresh(coach)
    return coach


# —— 私教课包商品 / 实例 ——


@router.get("/pt-products", response_model=list[PtProductOut])
def list_pt_products(
    merchant_id: int | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("course:manage", "pt:sell", "course:checkin")
    mid = ctx.resolve_merchant_id(merchant_id)
    products = list(
        db.scalars(select(PtPackageProduct).where(PtPackageProduct.merchant_id == mid).order_by(PtPackageProduct.id.desc())).all()
    )
    return [_product_out(db, p) for p in products]


@router.post("/pt-products", response_model=PtProductOut)
def create_pt_product(
    body: PtProductIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("course:manage")
    mid = ctx.resolve_merchant_id(body.merchant_id)
    assert_merchant_has_system(db, mid, "gym")
    product = PtPackageProduct(
        merchant_id=mid,
        name=body.name,
        price=body.price,
        session_count=body.session_count,
        valid_days=body.valid_days,
        all_coaches=body.all_coaches,
        promo_price=body.promo_price,
        promo_starts_at=body.promo_starts_at,
        promo_ends_at=body.promo_ends_at,
        is_active=True,
    )
    db.add(product)
    db.flush()
    if not body.all_coaches:
        for cid in body.coach_ids or []:
            db.add(PtPackageProductCoach(product_id=product.id, coach_id=cid))
    write_audit(
        db,
        action="pt_product.create",
        target_type="pt_product",
        target_id=product.id,
        summary=f"创建课包 {product.name}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=mid,
    )
    db.commit()
    db.refresh(product)
    return _product_out(db, product)


@router.post("/pt-products/{product_id}/deactivate", response_model=PtProductOut)
def deactivate_pt_product(
    product_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("course:manage")
    product = db.get(PtPackageProduct, product_id)
    if product is None:
        raise AppError("not_found", "课包商品不存在", status_code=404)
    ctx.resolve_merchant_id(product.merchant_id)
    product.is_active = False
    db.commit()
    db.refresh(product)
    return _product_out(db, product)


@router.get("/pt-packages", response_model=list[PtPackageOut])
def list_pt_packages(
    merchant_id: int | None = None,
    member_id: int | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("pt:sell", "course:manage", "course:checkin", "member:read")
    mid = ctx.resolve_merchant_id(merchant_id)
    q = select(PtPackage).where(PtPackage.merchant_id == mid)
    if member_id is not None:
        q = q.where(PtPackage.member_id == member_id)
    return list(db.scalars(q.order_by(PtPackage.id.desc())).all())


@router.post("/pt-packages/purchase", response_model=OrderOut)
def purchase_pt_package(
    body: PtPurchaseIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("pt:sell", "course:manage")
    mid = ctx.resolve_merchant_id(body.merchant_id)
    assert_merchant_has_system(db, mid, "gym")
    product = db.get(PtPackageProduct, body.product_id)
    if product is None or product.merchant_id != mid:
        raise AppError("not_found", "课包商品不存在", status_code=404)
    if not product.is_active:
        raise AppError("product_inactive", "课包已停用", status_code=400)
    member = db.get(Member, body.member_id)
    if member is None or member.site_id != ctx.site_id:
        raise AppError("not_found", "会员不存在", status_code=404)

    order = Order(
        site_id=ctx.site_id,
        merchant_id=mid,
        member_id=body.member_id,
        order_type="pt_package",
        title=f"私教课包-{product.name}",
        amount=effective_price(product.price, product.promo_price, product.promo_starts_at, product.promo_ends_at),
        status=OrderStatus.PENDING.value,
    )
    db.add(order)
    db.flush()
    db.add(PtOrderLink(order_id=order.id, member_id=body.member_id, product_id=product.id))
    write_audit(
        db,
        action="pt.purchase_order",
        target_type="order",
        target_id=order.id,
        summary=f"购课包 product={product.id}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=mid,
    )
    db.commit()
    db.refresh(order)
    return order


@router.post("/pt-packages/{package_id}/consume", response_model=PtPackageOut)
def consume_package(
    package_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("course:checkin", "pt:sell", "course:manage")
    package = db.get(PtPackage, package_id)
    if package is None:
        raise AppError("not_found", "课包不存在", status_code=404)
    ctx.resolve_merchant_id(package.merchant_id)
    if _coach_scope_only(ctx):
        # 教练可核销本商户课包（适用教练范围一期不强制）
        own = _own_coach(db, ctx, package.merchant_id)
        if own is None:
            raise AppError("forbidden", "未绑定教练档案", status_code=403)
    consume_pt_package(db, package, actor_staff_id=ctx.staff.id)
    db.commit()
    db.refresh(package)
    return package


# —— 团课 ——


@router.get("/group-courses", response_model=list[GroupCourseOut])
def list_group_courses(
    merchant_id: int | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("course:manage", "course:book", "course:checkin")
    mid = ctx.resolve_merchant_id(merchant_id)
    return list(db.scalars(select(GroupCourse).where(GroupCourse.merchant_id == mid).order_by(GroupCourse.id.desc())).all())


@router.post("/group-courses", response_model=GroupCourseOut)
def create_group_course(
    body: GroupCourseIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("course:manage")
    mid = ctx.resolve_merchant_id(body.merchant_id)
    assert_merchant_has_system(db, mid, "gym")
    course = GroupCourse(
        merchant_id=mid,
        name=body.name,
        difficulty=body.difficulty,
        default_duration_minutes=body.default_duration_minutes,
        default_capacity=body.default_capacity,
        book_ahead_minutes=body.book_ahead_minutes,
        cancel_ahead_minutes=body.cancel_ahead_minutes,
        is_active=True,
    )
    db.add(course)
    db.flush()
    write_audit(
        db,
        action="group_course.create",
        target_type="group_course",
        target_id=course.id,
        summary=f"创建团课 {course.name}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=mid,
    )
    db.commit()
    db.refresh(course)
    return course


@router.get("/group-sessions", response_model=list[GroupSessionOut])
def list_group_sessions(
    merchant_id: int | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("course:manage", "course:book", "course:checkin")
    mid = ctx.resolve_merchant_id(merchant_id)
    q = select(GroupSession).where(GroupSession.merchant_id == mid)
    if _coach_scope_only(ctx):
        own = _own_coach(db, ctx, mid)
        if own is None:
            return []
        q = q.where(GroupSession.coach_id == own.id)
    return list(db.scalars(q.order_by(GroupSession.starts_at.desc())).all())


@router.post("/group-sessions", response_model=GroupSessionOut)
def create_group_session(
    body: GroupSessionIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("course:manage")
    mid = ctx.resolve_merchant_id(body.merchant_id)
    assert_merchant_has_system(db, mid, "gym")
    course = db.get(GroupCourse, body.course_id)
    if course is None or course.merchant_id != mid:
        raise AppError("not_found", "课程不存在", status_code=404)
    coach = db.get(Coach, body.coach_id)
    if coach is None or coach.merchant_id != mid or not coach.is_active:
        raise AppError("coach_unavailable", "教练不可用", status_code=400)
    session = GroupSession(
        merchant_id=mid,
        course_id=course.id,
        coach_id=coach.id,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        room=body.room,
        capacity=body.capacity or course.default_capacity,
        status=GroupSessionStatus.OPEN.value,
    )
    db.add(session)
    db.flush()
    write_audit(
        db,
        action="group_session.create",
        target_type="group_session",
        target_id=session.id,
        summary=f"排场次 course={course.id} coach={coach.id}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=mid,
    )
    db.commit()
    db.refresh(session)
    return session


@router.post("/group-sessions/{session_id}/reassign", response_model=GroupSessionOut)
def reassign_session(
    session_id: int,
    body: ReassignIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("course:manage")
    session = db.get(GroupSession, session_id)
    if session is None:
        raise AppError("not_found", "场次不存在", status_code=404)
    mid = ctx.resolve_merchant_id(session.merchant_id)
    coach = db.get(Coach, body.coach_id)
    if coach is None or coach.merchant_id != mid or not coach.is_active:
        raise AppError("coach_unavailable", "教练不可用", status_code=400)
    session.coach_id = coach.id
    write_audit(
        db,
        action="group_session.reassign",
        target_type="group_session",
        target_id=session.id,
        summary=f"改派教练 coach={coach.id}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=mid,
    )
    db.commit()
    db.refresh(session)
    return session


@router.get("/group-bookings", response_model=list[BookingOut])
def list_bookings(
    session_id: int | None = None,
    merchant_id: int | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("course:book", "course:checkin", "course:manage")
    mid = ctx.resolve_merchant_id(merchant_id)
    q = select(GroupBooking).where(GroupBooking.merchant_id == mid)
    if session_id is not None:
        q = q.where(GroupBooking.session_id == session_id)
    return list(db.scalars(q.order_by(GroupBooking.id.desc())).all())


@router.post("/group-bookings", response_model=BookingOut)
def create_booking(
    body: BookIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("course:book", "course:manage")
    mid = ctx.resolve_merchant_id(body.merchant_id)
    assert_merchant_has_system(db, mid, "gym")
    session = db.get(GroupSession, body.session_id)
    if session is None or session.merchant_id != mid:
        raise AppError("not_found", "场次不存在", status_code=404)
    member = db.get(Member, body.member_id)
    if member is None or member.site_id != ctx.site_id:
        raise AppError("not_found", "会员不存在", status_code=404)
    booking = book_group_session(
        db, session, body.member_id, actor_staff_id=ctx.staff.id, site_id=ctx.site_id
    )
    db.commit()
    db.refresh(booking)
    return booking


@router.post("/group-bookings/{booking_id}/cancel", response_model=BookingOut)
def cancel_booking(
    booking_id: int,
    body: CancelIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("course:book", "course:manage")
    booking = db.get(GroupBooking, booking_id)
    if booking is None:
        raise AppError("not_found", "预约不存在", status_code=404)
    ctx.resolve_merchant_id(booking.merchant_id)
    session = db.get(GroupSession, booking.session_id)
    course = db.get(GroupCourse, session.course_id) if session else None
    if session is None or course is None:
        raise AppError("not_found", "场次或课程不存在", status_code=404)
    cancel_group_booking(
        db,
        booking,
        session,
        course,
        force=body.force,
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
    )
    db.commit()
    db.refresh(booking)
    return booking


@router.post("/group-bookings/{booking_id}/checkin", response_model=BookingOut)
def checkin_booking(
    booking_id: int,
    body: CheckinIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("course:checkin", "course:manage")
    booking = db.get(GroupBooking, booking_id)
    if booking is None:
        raise AppError("not_found", "预约不存在", status_code=404)
    mid = ctx.resolve_merchant_id(booking.merchant_id)
    if _coach_scope_only(ctx):
        session = db.get(GroupSession, booking.session_id)
        own = _own_coach(db, ctx, mid)
        if session is None or own is None or session.coach_id != own.id:
            raise AppError("forbidden", "仅可操作本人场次", status_code=403)
    checkin_group_booking(
        db, booking, body.status, actor_staff_id=ctx.staff.id, site_id=ctx.site_id
    )
    db.commit()
    db.refresh(booking)
    return booking
