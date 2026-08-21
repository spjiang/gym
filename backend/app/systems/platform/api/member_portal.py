"""会员端门户 API：会籍、团课、购卡买课、支付、通行。"""

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import MemberContext, get_current_member
from app.core.errors import AppError
from app.systems.platform.models.access import AccessEvent
from app.systems.platform.models.commerce import Order, OrderStatus, Payment, PaymentChannel, PaymentKind
from app.systems.gym.models.course import (
    Coach,
    GroupBooking,
    GroupBookingStatus,
    GroupCourse,
    GroupSession,
    GroupSessionStatus,
    PtOrderLink,
    PtPackage,
    PtPackageProduct,
)
from app.systems.gym.models.coupon import CouponTemplate, MemberCoupon
from app.systems.platform.models.member import MerchantMember
from app.systems.platform.models.org import Merchant, Site
from app.core.domain.subsystems import merchant_subsystem_codes
from app.systems.gym.models.membership import (
    Membership,
    MembershipOrderAction,
    MembershipOrderLink,
    MembershipProduct,
)
from app.core.schemas.common import OrderOut, OnlinePayIn
from app.systems.platform.services.audit import write_audit
from app.systems.platform.services.agreements import require_enabled_agreement
from app.systems.gym.services.course_booking import (
    book_group_session,
    booked_count,
    cancel_group_booking,
    is_session_open_for_booking,
)
from app.systems.gym.services.fulfillment import fulfill_membership_order, product_access_point_ids, validate_product_for_sale
from app.systems.platform.services.order_pricing import price_order
from app.systems.platform.services.payments import get_online_provider
from app.systems.gym.services.pt_fulfillment import fulfill_pt_package_order
from app.systems.gym.services.coupon import (
    _applicable_to_system,
    issue_member_coupon,
    list_claimable_templates,
    redeem_coupon_for_order,
)
from app.systems.gym.services.pricing import effective_price
from app.systems.gym.api.member_activity import MemberActivityOut, list_published_activities
from app.systems.platform.api.uploads import save_upload_file
from app.systems.platform.api.site_profile import SiteProfileOut, site_profile_out

router = APIRouter(prefix="/member", tags=["member-portal"])


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MemberMerchantOut(BaseModel):
    id: int
    name: str
    subsystem_codes: list[str]
    primary_system: str | None
    tagline: str | None = None
    cover_image_url: str | None = None


class MemberMeOut(BaseModel):
    id: int
    site_id: int
    phone: str
    name: str
    face_status: str
    merchant_ids: list[int]
    merchants: list[MemberMerchantOut] = []
    acquisition_source: str = "platform"
    first_merchant_id: int | None = None
    first_merchant_name: str | None = None
    avatar_url: str | None = None


class MembershipOut(ORMModel):
    id: int
    merchant_id: int
    product_id: int
    product_type: str
    status: str
    starts_at: datetime | None
    ends_at: datetime | None
    remaining_sessions: int | None
    balance: Decimal | None
    product_name: str | None = None


class PtPackageOut(ORMModel):
    id: int
    merchant_id: int
    product_id: int
    remaining_sessions: int
    status: str
    starts_at: datetime | None
    ends_at: datetime | None
    product_name: str | None = None


class AccessEventOut(ORMModel):
    id: int
    access_point_id: int
    allowed: bool
    reason: str | None
    created_at: datetime


class CatalogProductOut(ORMModel):
    id: int
    merchant_id: int
    name: str
    product_type: str
    price: Decimal
    duration_days: int | None
    session_count: int | None
    is_trial: bool
    effective_price: Decimal | None = None


class CatalogPtOut(ORMModel):
    id: int
    merchant_id: int
    name: str
    price: Decimal
    session_count: int
    valid_days: int
    effective_price: Decimal | None = None


class ClaimableCouponOut(ORMModel):
    id: int
    merchant_id: int
    name: str
    discount_type: str
    threshold_amount: Decimal
    fixed_amount: Decimal | None
    percent_off: int | None
    applicable_to: str
    starts_at: datetime
    ends_at: datetime
    per_member_limit: int


class MemberCouponOut(ORMModel):
    id: int
    merchant_id: int
    template_id: int
    status: str
    starts_at: datetime
    ends_at: datetime
    used_order_id: int | None
    template_name: str | None = None
    discount_type: str | None = None
    threshold_amount: Decimal | None = None
    fixed_amount: Decimal | None = None
    percent_off: int | None = None
    applicable_to: str | None = None


class ClaimCouponIn(BaseModel):
    merchant_id: int
    template_id: int


class GroupSessionOut(BaseModel):
    id: int
    merchant_id: int
    course_id: int
    coach_id: int
    starts_at: datetime
    ends_at: datetime
    capacity: int
    status: str
    room: str | None = None
    course_name: str
    difficulty: str | None = None
    duration_minutes: int | None = None
    coach_name: str | None = None
    booked_count: int = 0
    remaining: int = 0
    book_ahead_minutes: int = 0
    cancel_ahead_minutes: int = 0
    already_booked: bool = False


class MemberCoachOut(BaseModel):
    """会员端教练公开资料，不含提成等内部字段。"""

    id: int
    merchant_id: int
    display_name: str
    title: str | None = None
    gender: str | None = None
    phone: str | None = None
    years_experience: int | None = None
    hourly_rate: str | None = None
    specialties: str | None = None
    certifications: str | None = None
    bio: str | None = None
    availability_note: str | None = None
    avatar_url: str | None = None
    intro_image_urls: list[str] = []
    is_active: bool = True


class MemberStoreOut(BaseModel):
    """会员端可见的门店展示信息。"""

    id: int
    name: str
    tagline: str | None = None
    description: str | None = None
    business_hours: str | None = None
    contact_phone: str | None = None
    business_address: str | None = None
    cover_image_url: str | None = None
    gallery_image_urls: list[str] = []


class MemberHomeOut(BaseModel):
    """健身房首页聚合：介绍、教练、会籍、活动与可约团课。"""

    merchant: MemberStoreOut
    coaches: list[MemberCoachOut] = []
    memberships: list[CatalogProductOut] = []
    pt_packages: list[CatalogPtOut] = []
    sessions: list[GroupSessionOut] = []
    activities: list[MemberActivityOut] = []


class BookingOut(BaseModel):
    id: int
    merchant_id: int
    session_id: int
    member_id: int
    status: str
    course_name: str | None = None
    coach_id: int | None = None
    coach_name: str | None = None
    room: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    cancel_ahead_minutes: int = 0


class BookIn(BaseModel):
    merchant_id: int
    session_id: int


class PurchaseMembershipIn(BaseModel):
    merchant_id: int
    product_id: int


class PurchasePtIn(BaseModel):
    merchant_id: int
    product_id: int


class MemberAgreementOut(BaseModel):
    id: int
    title: str
    content: str


def _merchant_ids(db: Session, member_id: int) -> list[int]:
    return list(
        db.scalars(select(MerchantMember.merchant_id).where(MerchantMember.member_id == member_id)).all()
    )


def _primary_system(codes: list[str]) -> str | None:
    for c in ("gym", "catering"):
        if c in codes:
            return c
    return codes[0] if codes else None


def _site_merchants(db: Session, site_id: int) -> list[MemberMerchantOut]:
    ids = list(
        db.scalars(select(Merchant.id).where(Merchant.site_id == site_id).order_by(Merchant.id.asc())).all()
    )
    out: list[MemberMerchantOut] = []
    for mid in ids:
        m = db.get(Merchant, mid)
        if m is None:
            continue
        codes = merchant_subsystem_codes(db, mid)
        out.append(
            MemberMerchantOut(
                id=m.id,
                name=m.name,
                subsystem_codes=codes,
                primary_system=_primary_system(codes),
                tagline=m.tagline,
                cover_image_url=m.cover_image_url,
            )
        )
    return out


def _membership_out(db: Session, row: Membership) -> MembershipOut:
    product = db.get(MembershipProduct, row.product_id)
    return MembershipOut(
        id=row.id,
        merchant_id=row.merchant_id,
        product_id=row.product_id,
        product_type=row.product_type,
        status=row.status,
        starts_at=row.starts_at,
        ends_at=row.ends_at,
        remaining_sessions=row.remaining_sessions,
        balance=row.balance,
        product_name=product.name if product else None,
    )


def _pt_package_out(db: Session, row: PtPackage) -> PtPackageOut:
    product = db.get(PtPackageProduct, row.product_id)
    return PtPackageOut(
        id=row.id,
        merchant_id=row.merchant_id,
        product_id=row.product_id,
        remaining_sessions=row.remaining_sessions,
        status=row.status,
        starts_at=row.starts_at,
        ends_at=row.ends_at,
        product_name=product.name if product else None,
    )


def _member_session_out(
    db: Session,
    row: GroupSession,
    *,
    member_id: int | None = None,
) -> GroupSessionOut:
    course = db.get(GroupCourse, row.course_id)
    coach = db.get(Coach, row.coach_id)
    taken = booked_count(db, row.id)
    remaining = max(row.capacity - taken, 0)
    already = False
    if member_id is not None:
        existing = db.scalar(
            select(GroupBooking).where(
                GroupBooking.session_id == row.id,
                GroupBooking.member_id == member_id,
                GroupBooking.status == GroupBookingStatus.BOOKED.value,
            )
        )
        already = existing is not None
    return GroupSessionOut(
        id=row.id,
        merchant_id=row.merchant_id,
        course_id=row.course_id,
        coach_id=row.coach_id,
        starts_at=row.starts_at,
        ends_at=row.ends_at,
        capacity=row.capacity,
        status=row.status,
        room=row.room,
        course_name=course.name if course else f"课程 {row.course_id}",
        difficulty=course.difficulty if course else None,
        duration_minutes=course.default_duration_minutes if course else None,
        coach_name=coach.display_name if coach else None,
        booked_count=taken,
        remaining=remaining,
        book_ahead_minutes=course.book_ahead_minutes if course else 0,
        cancel_ahead_minutes=course.cancel_ahead_minutes if course else 0,
        already_booked=already,
    )


def _member_booking_out(db: Session, row: GroupBooking) -> BookingOut:
    session = db.get(GroupSession, row.session_id)
    course = db.get(GroupCourse, session.course_id) if session else None
    coach = db.get(Coach, session.coach_id) if session else None
    return BookingOut(
        id=row.id,
        merchant_id=row.merchant_id,
        session_id=row.session_id,
        member_id=row.member_id,
        status=row.status,
        course_name=course.name if course else None,
        coach_id=session.coach_id if session else None,
        coach_name=coach.display_name if coach else None,
        room=session.room if session else None,
        starts_at=session.starts_at if session else None,
        ends_at=session.ends_at if session else None,
        cancel_ahead_minutes=course.cancel_ahead_minutes if course else 0,
    )


def _member_coach_out(coach: Coach) -> MemberCoachOut:
    return MemberCoachOut(
        id=coach.id,
        merchant_id=coach.merchant_id,
        display_name=coach.display_name,
        title=coach.title,
        gender=coach.gender,
        phone=coach.phone,
        years_experience=coach.years_experience,
        hourly_rate=str(coach.hourly_rate) if coach.hourly_rate is not None else None,
        specialties=coach.specialties,
        certifications=coach.certifications,
        bio=coach.bio,
        availability_note=coach.availability_note,
        avatar_url=coach.avatar_url,
        intro_image_urls=list(coach.intro_image_urls or []),
        is_active=coach.is_active,
    )


def _member_store_out(row: Merchant) -> MemberStoreOut:
    return MemberStoreOut(
        id=row.id,
        name=row.name,
        tagline=row.tagline,
        description=row.description,
        business_hours=row.business_hours,
        contact_phone=row.contact_phone,
        business_address=row.business_address,
        cover_image_url=row.cover_image_url,
        gallery_image_urls=list(row.gallery_image_urls or []),
    )


def _catalog_membership_out(p: MembershipProduct) -> CatalogProductOut:
    return CatalogProductOut(
        id=p.id,
        merchant_id=p.merchant_id,
        name=p.name,
        product_type=p.product_type,
        price=p.price,
        duration_days=p.duration_days,
        session_count=p.session_count,
        is_trial=p.is_trial,
        effective_price=effective_price(p.price, p.promo_price, p.promo_starts_at, p.promo_ends_at),
    )


def _catalog_pt_out(p: PtPackageProduct) -> CatalogPtOut:
    return CatalogPtOut(
        id=p.id,
        merchant_id=p.merchant_id,
        name=p.name,
        price=p.price,
        session_count=p.session_count,
        valid_days=p.valid_days,
        effective_price=effective_price(p.price, p.promo_price, p.promo_starts_at, p.promo_ends_at),
    )


def _bookable_sessions(
    db: Session, *, merchant_id: int, member_id: int, limit: int | None = None
) -> list[GroupSessionOut]:
    now = datetime.now(timezone.utc)
    rows = list(
        db.scalars(
            select(GroupSession)
            .where(
                GroupSession.merchant_id == merchant_id,
                GroupSession.status == GroupSessionStatus.OPEN.value,
                GroupSession.starts_at > now,
            )
            .order_by(GroupSession.starts_at.asc())
        ).all()
    )
    out: list[GroupSessionOut] = []
    for row in rows:
        course = db.get(GroupCourse, row.course_id)
        taken = booked_count(db, row.id)
        if not is_session_open_for_booking(db, row, course, now=now, taken=taken):
            continue
        item = _member_session_out(db, row, member_id=member_id)
        if item.already_booked:
            continue
        out.append(item)
        if limit is not None and len(out) >= limit:
            break
    return out


@router.get("/site", response_model=SiteProfileOut)
def member_site(db: Session = Depends(get_db), mctx: MemberContext = Depends(get_current_member)):
    """会员门户：观野SPACE 整体介绍、客服与广告图。"""
    row = db.get(Site, mctx.site_id)
    if row is None:
        raise AppError("not_found", "场地不存在", status_code=404)
    return site_profile_out(row)


@router.get("/me", response_model=MemberMeOut)
def member_me(db: Session = Depends(get_db), mctx: MemberContext = Depends(get_current_member)):
    m = mctx.member
    merchant_ids = _merchant_ids(db, m.id)
    merchants = _site_merchants(db, m.site_id)
    first_name = None
    if m.first_merchant_id is not None:
        fm = db.get(Merchant, m.first_merchant_id)
        first_name = fm.name if fm else None
    return MemberMeOut(
        id=m.id,
        site_id=m.site_id,
        phone=m.phone,
        name=m.name,
        face_status=m.face_status,
        merchant_ids=merchant_ids,
        merchants=merchants,
        acquisition_source=getattr(m, "acquisition_source", "platform") or "platform",
        first_merchant_id=getattr(m, "first_merchant_id", None),
        first_merchant_name=first_name,
        avatar_url=getattr(m, "avatar_url", None),
    )


@router.post("/avatar", response_model=MemberMeOut)
async def upload_my_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    """会员自己上传展示头像。"""
    saved = await save_upload_file(file, images_only=True)
    mctx.member.avatar_url = saved["url"]
    db.add(mctx.member)
    db.commit()
    db.refresh(mctx.member)
    return member_me(db, mctx)


@router.delete("/avatar", response_model=MemberMeOut)
def clear_my_avatar(
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    """会员清除自己的展示头像。"""
    mctx.member.avatar_url = None
    db.add(mctx.member)
    db.commit()
    db.refresh(mctx.member)
    return member_me(db, mctx)


@router.get("/memberships", response_model=list[MembershipOut])
def list_my_memberships(
    merchant_id: int | None = None,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    q = select(Membership).where(Membership.member_id == mctx.member.id)
    if merchant_id is not None:
        mctx.require_merchant(db, merchant_id)
        q = q.where(Membership.merchant_id == merchant_id)
    rows = list(db.scalars(q.order_by(Membership.id.desc())).all())
    return [_membership_out(db, row) for row in rows]


@router.get("/memberships/{membership_id}", response_model=MembershipOut)
def get_my_membership(
    membership_id: int,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    row = db.get(Membership, membership_id)
    if row is None or row.member_id != mctx.member.id:
        raise AppError("not_found", "会籍不存在", status_code=404)
    mctx.require_merchant(db, row.merchant_id)
    return _membership_out(db, row)


@router.get("/pt-packages", response_model=list[PtPackageOut])
def list_my_pt_packages(
    merchant_id: int | None = None,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    q = select(PtPackage).where(PtPackage.member_id == mctx.member.id)
    if merchant_id is not None:
        mctx.require_merchant(db, merchant_id)
        q = q.where(PtPackage.merchant_id == merchant_id)
    rows = list(db.scalars(q.order_by(PtPackage.id.desc())).all())
    return [_pt_package_out(db, row) for row in rows]


@router.get("/pt-packages/{package_id}", response_model=PtPackageOut)
def get_my_pt_package(
    package_id: int,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    row = db.get(PtPackage, package_id)
    if row is None or row.member_id != mctx.member.id:
        raise AppError("not_found", "课包不存在", status_code=404)
    mctx.require_merchant(db, row.merchant_id)
    return _pt_package_out(db, row)


@router.get("/access-events", response_model=list[AccessEventOut])
def list_my_access_events(
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    return list(
        db.scalars(
            select(AccessEvent)
            .where(AccessEvent.member_id == mctx.member.id)
            .order_by(AccessEvent.id.desc())
            .limit(100)
        ).all()
    )


@router.get("/group-sessions", response_model=list[GroupSessionOut])
def list_group_sessions(
    merchant_id: int,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    """仅返回当前仍可新预约的场次，已开始 / 已满 / 已约的不出现在列表。"""
    mctx.require_merchant(db, merchant_id)
    return _bookable_sessions(db, merchant_id=merchant_id, member_id=mctx.member.id)


@router.get("/group-sessions/{session_id}", response_model=GroupSessionOut)
def get_group_session(
    session_id: int,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    """团课场次详情，已开始的仍可查看。"""
    row = db.get(GroupSession, session_id)
    if row is None:
        raise AppError("not_found", "场次不存在", status_code=404)
    mctx.require_merchant(db, row.merchant_id)
    return _member_session_out(db, row, member_id=mctx.member.id)


@router.get("/coaches/{coach_id}", response_model=MemberCoachOut)
def get_member_coach(
    coach_id: int,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    """会员查看教练公开资料。"""
    coach = db.get(Coach, coach_id)
    if coach is None:
        raise AppError("not_found", "教练不存在", status_code=404)
    mctx.require_merchant(db, coach.merchant_id)
    return _member_coach_out(coach)


@router.get("/coaches", response_model=list[MemberCoachOut])
def list_member_coaches(
    merchant_id: int,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    """会员浏览本店启用教练。"""
    mctx.require_merchant(db, merchant_id)
    rows = list(
        db.scalars(
            select(Coach)
            .where(Coach.merchant_id == merchant_id, Coach.is_active.is_(True))
            .order_by(Coach.id.asc())
        ).all()
    )
    return [_member_coach_out(c) for c in rows]


@router.get("/home", response_model=MemberHomeOut)
def get_member_home(
    merchant_id: int,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    """健身房首页：场馆介绍、教练、会籍课包、活动与可约团课。"""
    mctx.require_merchant(db, merchant_id)
    merchant = db.get(Merchant, merchant_id)
    if merchant is None:
        raise AppError("not_found", "门店不存在", status_code=404)
    coaches = list(
        db.scalars(
            select(Coach)
            .where(Coach.merchant_id == merchant_id, Coach.is_active.is_(True))
            .order_by(Coach.id.asc())
            .limit(8)
        ).all()
    )
    memberships = list(
        db.scalars(
            select(MembershipProduct)
            .where(MembershipProduct.merchant_id == merchant_id, MembershipProduct.is_active.is_(True))
            .order_by(MembershipProduct.id.asc())
            .limit(4)
        ).all()
    )
    pts = list(
        db.scalars(
            select(PtPackageProduct)
            .where(PtPackageProduct.merchant_id == merchant_id, PtPackageProduct.is_active.is_(True))
            .order_by(PtPackageProduct.id.asc())
            .limit(4)
        ).all()
    )
    return MemberHomeOut(
        merchant=_member_store_out(merchant),
        coaches=[_member_coach_out(c) for c in coaches],
        memberships=[_catalog_membership_out(p) for p in memberships],
        pt_packages=[_catalog_pt_out(p) for p in pts],
        sessions=_bookable_sessions(db, merchant_id=merchant_id, member_id=mctx.member.id, limit=3),
        activities=list_published_activities(
            db, merchant_id=merchant_id, member_id=mctx.member.id, limit=3
        ),
    )


@router.get("/group-bookings", response_model=list[BookingOut])
def list_my_bookings(
    merchant_id: int | None = None,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    q = select(GroupBooking).where(GroupBooking.member_id == mctx.member.id)
    if merchant_id is not None:
        mctx.require_merchant(db, merchant_id)
        q = q.where(GroupBooking.merchant_id == merchant_id)
    rows = list(db.scalars(q.order_by(GroupBooking.id.desc())).all())
    return [_member_booking_out(db, row) for row in rows]


@router.post("/group-bookings", response_model=BookingOut)
def create_my_booking(
    body: BookIn,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    mctx.require_merchant(db, body.merchant_id)
    session = db.get(GroupSession, body.session_id)
    if session is None or session.merchant_id != body.merchant_id:
        raise AppError("not_found", "场次不存在", status_code=404)
    booking = book_group_session(
        db,
        session,
        mctx.member.id,
        actor_staff_id=None,
        site_id=mctx.site_id,
    )
    db.commit()
    db.refresh(booking)
    return _member_booking_out(db, booking)


@router.delete("/group-bookings/{booking_id}", response_model=BookingOut)
def cancel_my_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    booking = db.get(GroupBooking, booking_id)
    if booking is None or booking.member_id != mctx.member.id:
        raise AppError("not_found", "预约不存在", status_code=404)
    session = db.get(GroupSession, booking.session_id)
    course = db.get(GroupCourse, session.course_id) if session else None
    if session is None or course is None:
        raise AppError("not_found", "场次或课程不存在", status_code=404)
    cancel_group_booking(
        db,
        booking,
        session,
        course,
        force=False,
        actor_staff_id=None,
        site_id=mctx.site_id,
    )
    db.commit()
    db.refresh(booking)
    return _member_booking_out(db, booking)


@router.get("/catalog/membership-products", response_model=list[CatalogProductOut])
def catalog_membership_products(
    merchant_id: int,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    mctx.require_merchant(db, merchant_id)
    rows = db.scalars(
        select(MembershipProduct).where(
            MembershipProduct.merchant_id == merchant_id,
            MembershipProduct.is_active.is_(True),
        )
    ).all()
    return [_catalog_membership_out(p) for p in rows]


@router.get("/coupons/claimable", response_model=list[ClaimableCouponOut])
def list_claimable_coupons(
    merchant_id: int,
    system: str | None = None,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    mctx.require_merchant(db, merchant_id)
    return list_claimable_templates(
        db, merchant_id=merchant_id, member_id=mctx.member.id, system=system
    )


@router.post("/coupons/claim", response_model=MemberCouponOut)
def claim_coupon(
    body: ClaimCouponIn,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    mctx.require_merchant(db, body.merchant_id)
    template = db.get(CouponTemplate, body.template_id)
    if template is None or template.merchant_id != body.merchant_id:
        raise AppError("not_found", "券模板不存在", status_code=404)
    mc = issue_member_coupon(
        db,
        template=template,
        member_id=mctx.member.id,
        require_claimable=True,
        actor_staff_id=None,
        site_id=mctx.site_id,
        audit_action="coupon.claim",
    )
    db.commit()
    db.refresh(mc)
    return mc


@router.get("/coupons", response_model=list[MemberCouponOut])
def list_my_coupons(
    merchant_id: int | None = None,
    system: str | None = None,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    q = select(MemberCoupon, CouponTemplate).join(
        CouponTemplate, CouponTemplate.id == MemberCoupon.template_id
    ).where(MemberCoupon.member_id == mctx.member.id)
    if merchant_id is not None:
        mctx.require_merchant(db, merchant_id)
        q = q.where(MemberCoupon.merchant_id == merchant_id)
    rows = list(db.execute(q.order_by(MemberCoupon.id.desc())).all())
    items: list[MemberCouponOut] = []
    for mc, tpl in rows:
        if not _applicable_to_system(tpl, system):
            continue
        items.append(
            MemberCouponOut(
                id=mc.id,
                merchant_id=mc.merchant_id,
                template_id=mc.template_id,
                status=mc.status,
                starts_at=mc.starts_at,
                ends_at=mc.ends_at,
                used_order_id=mc.used_order_id,
                template_name=tpl.name,
                discount_type=tpl.discount_type,
                threshold_amount=tpl.threshold_amount,
                fixed_amount=tpl.fixed_amount,
                percent_off=tpl.percent_off,
                applicable_to=tpl.applicable_to,
            )
        )
    return items


@router.get("/catalog/pt-products", response_model=list[CatalogPtOut])
def catalog_pt_products(
    merchant_id: int,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    mctx.require_merchant(db, merchant_id)
    rows = db.scalars(
        select(PtPackageProduct).where(
            PtPackageProduct.merchant_id == merchant_id,
            PtPackageProduct.is_active.is_(True),
        )
    ).all()
    return [_catalog_pt_out(p) for p in rows]


@router.get("/agreements", response_model=MemberAgreementOut)
def get_member_agreement(
    merchant_id: int,
    scene: str,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    """当前启用的购买协议全文。"""
    mctx.require_merchant(db, merchant_id)
    row = require_enabled_agreement(db, merchant_id=merchant_id, scene=scene)
    return MemberAgreementOut(id=row.id, title=row.title, content=row.content)


@router.post("/orders/membership", response_model=OrderOut)
def order_membership(
    body: PurchaseMembershipIn,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    mctx.require_merchant(db, body.merchant_id)
    require_enabled_agreement(db, merchant_id=body.merchant_id, scene="membership")
    product = db.get(MembershipProduct, body.product_id)
    if product is None or product.merchant_id != body.merchant_id:
        raise AppError("not_found", "卡种不存在", status_code=404)
    ap_ids = product_access_point_ids(db, product.id)
    validate_product_for_sale(product, ap_ids)

    price = effective_price(
        product.price, product.promo_price, product.promo_starts_at, product.promo_ends_at
    )
    order = Order(
        site_id=mctx.site_id,
        merchant_id=body.merchant_id,
        member_id=mctx.member.id,
        order_type="membership",
        title=f"办卡-{product.name}",
        amount=price,
        status=OrderStatus.PENDING.value,
    )
    db.add(order)
    db.flush()
    price_order(db, order=order, original_amount=price)
    db.add(
        MembershipOrderLink(
            order_id=order.id,
            member_id=mctx.member.id,
            product_id=product.id,
            action=MembershipOrderAction.PURCHASE.value,
        )
    )
    write_audit(
        db,
        action="member.membership_order",
        target_type="order",
        target_id=order.id,
        summary=f"会员购卡 product={product.id}",
        site_id=mctx.site_id,
        merchant_id=body.merchant_id,
    )
    db.commit()
    db.refresh(order)
    return order


@router.post("/orders/pt-package", response_model=OrderOut)
def order_pt_package(
    body: PurchasePtIn,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    mctx.require_merchant(db, body.merchant_id)
    require_enabled_agreement(db, merchant_id=body.merchant_id, scene="pt_package")
    product = db.get(PtPackageProduct, body.product_id)
    if product is None or product.merchant_id != body.merchant_id:
        raise AppError("not_found", "课包商品不存在", status_code=404)
    if not product.is_active:
        raise AppError("product_inactive", "课包已停用", status_code=400)

    price = effective_price(
        product.price, product.promo_price, product.promo_starts_at, product.promo_ends_at
    )
    order = Order(
        site_id=mctx.site_id,
        merchant_id=body.merchant_id,
        member_id=mctx.member.id,
        order_type="pt_package",
        title=f"私教课包-{product.name}",
        amount=price,
        status=OrderStatus.PENDING.value,
    )
    db.add(order)
    db.flush()
    price_order(db, order=order, original_amount=price)
    db.add(PtOrderLink(order_id=order.id, member_id=mctx.member.id, product_id=product.id))
    write_audit(
        db,
        action="member.pt_order",
        target_type="order",
        target_id=order.id,
        summary=f"会员买课包 product={product.id}",
        site_id=mctx.site_id,
        merchant_id=body.merchant_id,
    )
    db.commit()
    db.refresh(order)
    return order


@router.get("/orders/{order_id}", response_model=OrderOut)
def get_my_order(
    order_id: int,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    order = db.get(Order, order_id)
    if order is None or order.member_id != mctx.member.id:
        raise AppError("not_found", "订单不存在", status_code=404)
    return order


@router.post("/orders/{order_id}/pay/online")
def pay_my_order_online(
    order_id: int,
    body: OnlinePayIn | None = None,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    """会员线上支付：mock 可立即入账；微信返回预下单参数，待回调/dry-run 确认。"""
    from app.systems.platform.models.payment_settings import MemberWechatBinding, PaymentIntent
    from app.systems.platform.services.order_fulfill import fulfill_paid_order

    body = body or OnlinePayIn()
    order = db.get(Order, order_id)
    if order is None or order.member_id != mctx.member.id:
        raise AppError("not_found", "订单不存在", status_code=404)
    if order.status != OrderStatus.PENDING.value:
        raise AppError("invalid_state", "仅待支付订单可发起线上支付", status_code=400)

    pay_scene = (body.pay_scene or "miniprogram").strip()
    openid = None
    if pay_scene in ("miniprogram", "jsapi_h5"):
        binding = db.scalar(
            select(MemberWechatBinding).where(MemberWechatBinding.member_id == mctx.member.id)
        )
        openid = (binding.mp_openid if pay_scene == "miniprogram" else binding.oa_openid) if binding else None

    out_trade_no = f"o{order.id}t{int(__import__('time').time())}"
    # 关闭同订单未完成的旧支付意图
    for old in db.scalars(
        select(PaymentIntent).where(
            PaymentIntent.order_id == order.id,
            PaymentIntent.status == "created",
        )
    ).all():
        old.status = "closed"

    provider = get_online_provider(db, mctx.site_id)
    result = provider.create_payment(
        order_id=order.id,
        amount=str(order.amount),
        title=order.title,
        out_trade_no=out_trade_no,
        pay_scene=pay_scene,
        openid=openid,
        client_ip=body.client_ip,
        return_url=body.return_url,
        staff_capture=False,
    )
    if not result.ok:
        raise AppError("online_pay_failed", result.message, status_code=400)

    intent = PaymentIntent(
        site_id=order.site_id,
        order_id=order.id,
        out_trade_no=out_trade_no,
        scene=pay_scene,
        status="created",
        amount=order.amount,
        provider_prepay_id=(result.jsapi_params or {}).get("package", "").replace("prepay_id=", "")
        if result.jsapi_params
        else None,
        provider_ref=result.provider_ref,
    )
    db.add(intent)
    write_audit(
        db,
        action="member.pay_online",
        target_type="order",
        target_id=order.id,
        summary=f"会员预下单 scene={pay_scene}",
        site_id=mctx.site_id,
        merchant_id=order.merchant_id,
    )

    if result.immediate_capture:
        fulfill_paid_order(db, order, provider_ref=result.provider_ref)
        intent.status = "succeeded"
        db.commit()
        db.refresh(order)
        return {
            "id": order.id,
            "order_id": order.id,
            "status": order.status,
            "amount": str(order.amount),
            "pay_scene": pay_scene,
            "dry_run": result.dry_run,
            "immediate_capture": True,
            "jsapi_params": None,
            "mweb_url": None,
            "provider_ref": result.provider_ref,
            "out_trade_no": out_trade_no,
            "pickup_code": order.pickup_code,
            "dining_status": order.dining_status,
        }

    db.commit()
    return {
        "id": order.id,
        "order_id": order.id,
        "status": order.status,
        "amount": str(order.amount),
        "pay_scene": pay_scene,
        "dry_run": result.dry_run,
        "immediate_capture": False,
        "jsapi_params": result.jsapi_params,
        "mweb_url": result.mweb_url,
        "provider_ref": result.provider_ref,
        "out_trade_no": out_trade_no,
        "pickup_code": order.pickup_code,
        "dining_status": order.dining_status,
    }
