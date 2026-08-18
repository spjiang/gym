"""教练、私教课包、团课 API。"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import ROLE_COACH, ROLE_COACH_LEGACY, RequestContext, get_current_context
from app.core.domain.member_brief import load_member_briefs
from app.core.domain.subsystems import assert_merchant_has_system
from app.core.errors import AppError
from app.core.schemas.common import MemberBrief, OrderOut
from app.core.schemas.paging import PageOut, paginate
from app.systems.platform.models.commerce import Order, OrderStatus
from app.systems.gym.models.course import (
    Coach,
    GroupBooking,
    GroupCourse,
    GroupSession,
    GroupSessionStatus,
    PtOrderLink,
    PtPackage,
    PtPackageProduct,
    PtPackageProductCoach,
    PtPackageStatus,
)
from app.systems.platform.models.audit import AuditLog
from app.systems.platform.models.identity import StaffUser
from app.systems.platform.models.member import Member
from app.systems.platform.services.audit import write_audit
from app.systems.platform.services.order_pricing import price_order
from app.systems.gym.services.course_booking import (
    book_group_session,
    booked_count,
    cancel_group_booking,
    cancel_group_session,
    checkin_group_booking,
)
from app.systems.gym.services.pt_fulfillment import consume_pt_package, update_pt_package
from app.systems.gym.services.pricing import effective_price

router = APIRouter(tags=["course"])

_COACH_IMAGE_URL_RE = re.compile(r"^/api/v1/files/[0-9a-f]{32}\.(jpg|png|webp)$")
_MAX_COACH_INTRO_IMAGES = 9
_COACH_GENDERS = {"male", "female", "other"}


def _blank(value: str | None) -> str | None:
    text = (value or "").strip()
    return text or None


def _normalize_coach_image_url(url: str | None, *, field: str) -> str | None:
    text = _blank(url)
    if text is None:
        return None
    if not _COACH_IMAGE_URL_RE.match(text):
        raise AppError("invalid_image", f"{field}地址无效，请通过系统上传", status_code=400)
    return text


def _normalize_intro_images(urls: list[str] | None) -> list[str]:
    """只接受本系统已上传的图片地址，去重且最多 9 张。"""
    out: list[str] = []
    for raw in urls or []:
        url = _normalize_coach_image_url(raw, field="介绍图片")
        if url and url not in out:
            out.append(url)
    if len(out) > _MAX_COACH_INTRO_IMAGES:
        raise AppError("too_many_images", "介绍图片最多 9 张", status_code=400)
    return out


def _normalize_gender(value: str | None) -> str | None:
    text = _blank(value)
    if text is None:
        return None
    if text not in _COACH_GENDERS:
        raise AppError("invalid_gender", "性别仅支持男 / 女 / 其他", status_code=400)
    return text


class CoachIn(BaseModel):
    merchant_id: int | None = None
    staff_user_id: int
    display_name: str
    title: str | None = None
    gender: str | None = None
    phone: str | None = None
    years_experience: int | None = Field(default=None, ge=0, le=60)
    hourly_rate: Decimal | None = Field(default=None, ge=0)
    # 私教课佣金比例，0.4 表示课时单价的 40%
    pt_commission_rate: Decimal | None = Field(default=None, ge=0, le=1)
    specialties: str | None = None
    certifications: str | None = None
    bio: str | None = None
    availability_note: str | None = None
    avatar_url: str | None = None
    intro_image_urls: list[str] = Field(default_factory=list)


class CoachOut(BaseModel):
    id: int
    merchant_id: int
    staff_user_id: int
    display_name: str
    title: str | None
    gender: str | None
    phone: str | None
    years_experience: int | None
    hourly_rate: Decimal | None
    pt_commission_rate: Decimal | None = None
    specialties: str | None
    certifications: str | None
    bio: str | None
    availability_note: str | None
    avatar_url: str | None
    intro_image_urls: list[str] = []
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


class PtPackageProductBrief(BaseModel):
    id: int
    name: str
    price: Decimal
    session_count: int
    valid_days: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class PtPackageOut(BaseModel):
    id: int
    merchant_id: int
    member_id: int
    product_id: int
    status: str
    remaining_sessions: int
    starts_at: datetime | None
    ends_at: datetime | None
    member: MemberBrief | None = None
    product: PtPackageProductBrief | None = None

    model_config = ConfigDict(from_attributes=True)


class PtPackagePatch(BaseModel):
    remaining_sessions: int | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    status: str | None = None


class PtConsumeOut(BaseModel):
    id: int
    created_at: datetime
    sessions: int
    remaining_after: int | None
    actor_name: str | None
    summary: str


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


class GroupSessionPatch(BaseModel):
    course_id: int | None = None
    coach_id: int | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    room: str | None = None
    capacity: int | None = Field(default=None, gt=0)
    status: str | None = None


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
    member: MemberBrief | None = None

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


def _product_brief(p: PtPackageProduct | None) -> PtPackageProductBrief | None:
    if p is None:
        return None
    return PtPackageProductBrief(
        id=p.id,
        name=p.name,
        price=p.price,
        session_count=p.session_count,
        valid_days=p.valid_days,
        is_active=p.is_active,
    )


def _package_out(
    db: Session,
    row: PtPackage,
    *,
    briefs: dict[int, MemberBrief] | None = None,
) -> PtPackageOut:
    product = db.get(PtPackageProduct, row.product_id)
    member = None
    if briefs is not None:
        member = briefs.get(row.member_id)
    else:
        loaded = load_member_briefs(db, {row.member_id})
        member = loaded.get(row.member_id)
    return PtPackageOut(
        id=row.id,
        merchant_id=row.merchant_id,
        member_id=row.member_id,
        product_id=row.product_id,
        status=row.status,
        remaining_sessions=row.remaining_sessions,
        starts_at=row.starts_at,
        ends_at=row.ends_at,
        member=member,
        product=_product_brief(product),
    )


def _own_coach(db: Session, ctx: RequestContext, merchant_id: int | None) -> Coach | None:
    q = select(Coach).where(Coach.staff_user_id == ctx.staff.id)
    if merchant_id:
        q = q.where(Coach.merchant_id == merchant_id)
    return db.scalar(q)


def _coach_scope_only(ctx: RequestContext) -> bool:
    return (
        (ROLE_COACH in ctx.role_codes or ROLE_COACH_LEGACY in ctx.role_codes)
        and not ctx.is_site_admin
        and "course:manage" not in ctx.permissions
    )


# —— 教练 ——


@router.get("/coaches", response_model=PageOut[CoachOut])
def list_coaches(
    merchant_id: int | None = None,
    q: str | None = None,
    is_active: bool | None = None,
    gender: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("coach:manage", "course:manage", "course:book", "course:checkin", "pt:sell")
    mid = ctx.resolve_merchant_id(merchant_id, required=False)
    stmt = select(Coach)
    if mid is not None:
        stmt = stmt.where(Coach.merchant_id == mid)
    if _coach_scope_only(ctx):
        stmt = stmt.where(Coach.staff_user_id == ctx.staff.id)
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(
                Coach.display_name.ilike(like),
                Coach.specialties.ilike(like),
                Coach.title.ilike(like),
                Coach.phone.ilike(like),
            )
        )
    if is_active is not None:
        stmt = stmt.where(Coach.is_active.is_(is_active))
    if gender:
        stmt = stmt.where(Coach.gender == _normalize_gender(gender))
    rows, total = paginate(db, stmt.order_by(Coach.id.desc()), page=page, page_size=page_size)
    return PageOut(items=rows, total=total, page=page, page_size=page_size)


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
    name = (body.display_name or "").strip()
    if not name:
        raise AppError("validation_error", "请填写教练显示名", status_code=422)
    coach = Coach(
        merchant_id=mid,
        staff_user_id=body.staff_user_id,
        display_name=name,
        title=_blank(body.title),
        gender=_normalize_gender(body.gender),
        phone=_blank(body.phone),
        years_experience=body.years_experience,
        hourly_rate=body.hourly_rate,
        pt_commission_rate=body.pt_commission_rate,
        specialties=_blank(body.specialties),
        certifications=_blank(body.certifications),
        bio=_blank(body.bio),
        availability_note=_blank(body.availability_note),
        avatar_url=_normalize_coach_image_url(body.avatar_url, field="头像"),
        intro_image_urls=_normalize_intro_images(body.intro_image_urls),
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


@router.patch("/coaches/{coach_id}", response_model=CoachOut)
def update_coach(
    coach_id: int,
    body: CoachIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """编辑教练展示信息，不改绑定员工。"""
    ctx.require_permission("coach:manage")
    coach = db.get(Coach, coach_id)
    if coach is None:
        raise AppError("not_found", "教练不存在", status_code=404)
    ctx.resolve_merchant_id(coach.merchant_id)
    name = (body.display_name or "").strip()
    if not name:
        raise AppError("validation_error", "请填写教练显示名", status_code=422)
    coach.display_name = name
    coach.title = _blank(body.title)
    coach.gender = _normalize_gender(body.gender)
    coach.phone = _blank(body.phone)
    coach.years_experience = body.years_experience
    coach.hourly_rate = body.hourly_rate
    coach.pt_commission_rate = body.pt_commission_rate
    coach.specialties = _blank(body.specialties)
    coach.certifications = _blank(body.certifications)
    coach.bio = _blank(body.bio)
    coach.availability_note = _blank(body.availability_note)
    coach.avatar_url = _normalize_coach_image_url(body.avatar_url, field="头像")
    coach.intro_image_urls = _normalize_intro_images(body.intro_image_urls)
    write_audit(
        db,
        action="coach.update",
        target_type="coach",
        target_id=coach.id,
        summary=f"更新教练 {coach.display_name}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=coach.merchant_id,
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


@router.get("/pt-products", response_model=PageOut[PtProductOut])
def list_pt_products(
    merchant_id: int | None = None,
    q: str | None = None,
    is_active: bool | None = None,
    price_min: Decimal | None = None,
    price_max: Decimal | None = None,
    session_min: int | None = None,
    session_max: int | None = None,
    valid_days_min: int | None = None,
    valid_days_max: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("course:manage", "pt:sell", "course:checkin")
    mid = ctx.resolve_merchant_id(merchant_id, required=False)
    stmt = select(PtPackageProduct)
    if mid is not None:
        stmt = stmt.where(PtPackageProduct.merchant_id == mid)
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        conds = [PtPackageProduct.name.ilike(like)]
        if keyword.isdigit():
            conds.append(PtPackageProduct.id == int(keyword))
        stmt = stmt.where(or_(*conds))
    if is_active is not None:
        stmt = stmt.where(PtPackageProduct.is_active.is_(is_active))
    if price_min is not None:
        stmt = stmt.where(PtPackageProduct.price >= price_min)
    if price_max is not None:
        stmt = stmt.where(PtPackageProduct.price <= price_max)
    if session_min is not None:
        stmt = stmt.where(PtPackageProduct.session_count >= session_min)
    if session_max is not None:
        stmt = stmt.where(PtPackageProduct.session_count <= session_max)
    if valid_days_min is not None:
        stmt = stmt.where(PtPackageProduct.valid_days >= valid_days_min)
    if valid_days_max is not None:
        stmt = stmt.where(PtPackageProduct.valid_days <= valid_days_max)
    products, total = paginate(db, stmt.order_by(PtPackageProduct.id.desc()), page=page, page_size=page_size)
    return PageOut(items=[_product_out(db, p) for p in products], total=total, page=page, page_size=page_size)


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


@router.patch("/pt-products/{product_id}", response_model=PtProductOut)
def update_pt_product(
    product_id: int,
    body: PtProductIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("course:manage")
    product = db.get(PtPackageProduct, product_id)
    if product is None:
        raise AppError("not_found", "课包商品不存在", status_code=404)
    mid = ctx.resolve_merchant_id(body.merchant_id or product.merchant_id)
    if product.merchant_id != mid:
        raise AppError("forbidden", "禁止跨商户修改", status_code=403)
    product.name = body.name.strip()
    product.price = body.price
    product.session_count = body.session_count
    product.valid_days = body.valid_days
    product.all_coaches = body.all_coaches
    product.promo_price = body.promo_price
    product.promo_starts_at = body.promo_starts_at
    product.promo_ends_at = body.promo_ends_at
    write_audit(
        db,
        action="pt_product.update",
        target_type="pt_product",
        target_id=product.id,
        summary=f"更新课包 {product.name}",
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


@router.post("/pt-products/{product_id}/activate", response_model=PtProductOut)
def activate_pt_product(
    product_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("course:manage")
    product = db.get(PtPackageProduct, product_id)
    if product is None:
        raise AppError("not_found", "课包商品不存在", status_code=404)
    ctx.resolve_merchant_id(product.merchant_id)
    product.is_active = True
    write_audit(
        db,
        action="pt_product.activate",
        target_type="pt_product",
        target_id=product.id,
        summary=f"重新启用课包 {product.name}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=product.merchant_id,
    )
    db.commit()
    db.refresh(product)
    return _product_out(db, product)


@router.get("/pt-packages", response_model=PageOut[PtPackageOut])
def list_pt_packages(
    merchant_id: int | None = None,
    member_id: int | None = None,
    product_id: int | None = None,
    status: str | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("pt:sell", "course:manage", "course:checkin", "member:read")
    mid = ctx.resolve_merchant_id(merchant_id, required=False)
    filters = [PtPackage.merchant_id == mid] if mid is not None else []
    if member_id is not None:
        filters.append(PtPackage.member_id == member_id)
    if product_id is not None:
        filters.append(PtPackage.product_id == product_id)
    if status:
        filters.append(PtPackage.status == status)
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        member_sq = select(Member.id).where(or_(Member.phone.ilike(like), Member.name.ilike(like)))
        product_sq = select(PtPackageProduct.id).where(PtPackageProduct.name.ilike(like))
        filters.append(or_(PtPackage.member_id.in_(member_sq), PtPackage.product_id.in_(product_sq)))
    base = select(PtPackage)
    if filters:
        base = base.where(*filters)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = list(
        db.scalars(
            base
            .order_by(PtPackage.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    briefs = load_member_briefs(db, {r.member_id for r in rows})
    items = [_package_out(db, r, briefs=briefs) for r in rows]
    return PageOut(items=items, total=total, page=page, page_size=page_size)


@router.get("/pt-packages/{package_id}", response_model=PtPackageOut)
def get_pt_package(
    package_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("pt:sell", "course:manage", "course:checkin", "member:read")
    package = db.get(PtPackage, package_id)
    if package is None:
        raise AppError("not_found", "课包不存在", status_code=404)
    ctx.resolve_merchant_id(package.merchant_id)
    return _package_out(db, package)


_CONSUMED_RE = re.compile(r"核销\s*(\d+)")
_REMAINING_RE = re.compile(r"剩余\s*(\d+)")


def _consume_out(row: AuditLog, actor_name: str | None) -> PtConsumeOut:
    consumed = _CONSUMED_RE.search(row.summary or "")
    remaining = _REMAINING_RE.search(row.summary or "")
    return PtConsumeOut(
        id=row.id,
        created_at=row.created_at,
        sessions=int(consumed.group(1)) if consumed else 1,
        remaining_after=int(remaining.group(1)) if remaining else None,
        actor_name=actor_name,
        summary=row.summary,
    )


@router.get("/pt-packages/{package_id}/consumes", response_model=list[PtConsumeOut])
def list_pt_package_consumes(
    package_id: int,
    from_date: date | None = None,
    to_date: date | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """查看会员课包的核销记录，可按核销日期筛选。"""
    ctx.require_permission("pt:sell", "course:manage", "course:checkin", "member:read")
    package = db.get(PtPackage, package_id)
    if package is None:
        raise AppError("not_found", "课包不存在", status_code=404)
    ctx.resolve_merchant_id(package.merchant_id)
    tz = ZoneInfo("Asia/Shanghai")
    filters = [
        AuditLog.action == "pt.consume",
        AuditLog.target_type == "pt_package",
        AuditLog.target_id == str(package_id),
    ]
    if from_date:
        filters.append(AuditLog.created_at >= datetime.combine(from_date, time.min, tzinfo=tz))
    if to_date:
        filters.append(
            AuditLog.created_at < datetime.combine(to_date + timedelta(days=1), time.min, tzinfo=tz)
        )
    rows = list(
        db.scalars(select(AuditLog).where(*filters).order_by(AuditLog.id.desc())).all()
    )
    staff_ids = {r.actor_staff_id for r in rows if r.actor_staff_id}
    names: dict[int, str] = {}
    if staff_ids:
        staff_rows = list(db.scalars(select(StaffUser).where(StaffUser.id.in_(staff_ids))).all())
        names = {s.id: s.display_name for s in staff_rows}
    return [_consume_out(r, names.get(r.actor_staff_id) if r.actor_staff_id else None) for r in rows]


@router.patch("/pt-packages/{package_id}", response_model=PtPackageOut)
def patch_pt_package(
    package_id: int,
    body: PtPackagePatch,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("pt:sell", "course:manage")
    package = db.get(PtPackage, package_id)
    if package is None:
        raise AppError("not_found", "课包不存在", status_code=404)
    ctx.resolve_merchant_id(package.merchant_id)
    update_pt_package(
        db,
        package,
        actor_staff_id=ctx.staff.id,
        remaining_sessions=body.remaining_sessions,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        status=body.status,
        fields_set=set(body.model_fields_set),
    )
    db.commit()
    db.refresh(package)
    return _package_out(db, package)


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

    price = effective_price(
        product.price, product.promo_price, product.promo_starts_at, product.promo_ends_at
    )
    order = Order(
        site_id=ctx.site_id,
        merchant_id=mid,
        member_id=body.member_id,
        order_type="pt_package",
        title=f"私教课包-{product.name}",
        amount=price,
        status=OrderStatus.PENDING.value,
        seller_staff_id=ctx.staff.id,
    )
    db.add(order)
    db.flush()
    price_order(db, order=order, original_amount=price)
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
    return _package_out(db, package)


# —— 团课 ——


@router.get("/group-courses", response_model=PageOut[GroupCourseOut])
def list_group_courses(
    merchant_id: int | None = None,
    q: str | None = None,
    difficulty: str | None = None,
    is_active: bool | None = None,
    duration_min: int | None = None,
    duration_max: int | None = None,
    capacity_min: int | None = None,
    capacity_max: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("course:manage", "course:book", "course:checkin")
    mid = ctx.resolve_merchant_id(merchant_id, required=False)
    stmt = select(GroupCourse)
    if mid is not None:
        stmt = stmt.where(GroupCourse.merchant_id == mid)
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        conds = [GroupCourse.name.ilike(like)]
        if keyword.isdigit():
            conds.append(GroupCourse.id == int(keyword))
        stmt = stmt.where(or_(*conds))
    if difficulty:
        stmt = stmt.where(GroupCourse.difficulty.ilike(f"%{difficulty.strip()}%"))
    if is_active is not None:
        stmt = stmt.where(GroupCourse.is_active.is_(is_active))
    if duration_min is not None:
        stmt = stmt.where(GroupCourse.default_duration_minutes >= duration_min)
    if duration_max is not None:
        stmt = stmt.where(GroupCourse.default_duration_minutes <= duration_max)
    if capacity_min is not None:
        stmt = stmt.where(GroupCourse.default_capacity >= capacity_min)
    if capacity_max is not None:
        stmt = stmt.where(GroupCourse.default_capacity <= capacity_max)
    rows, total = paginate(db, stmt.order_by(GroupCourse.id.desc()), page=page, page_size=page_size)
    return PageOut(items=rows, total=total, page=page, page_size=page_size)


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


@router.patch("/group-courses/{course_id}", response_model=GroupCourseOut)
def update_group_course(
    course_id: int,
    body: GroupCourseIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("course:manage")
    course = db.get(GroupCourse, course_id)
    if course is None:
        raise AppError("not_found", "团课不存在", status_code=404)
    mid = ctx.resolve_merchant_id(body.merchant_id or course.merchant_id)
    if course.merchant_id != mid:
        raise AppError("forbidden", "禁止跨商户修改", status_code=403)
    course.name = body.name.strip()
    course.difficulty = body.difficulty
    course.default_duration_minutes = body.default_duration_minutes
    course.default_capacity = body.default_capacity
    course.book_ahead_minutes = body.book_ahead_minutes
    course.cancel_ahead_minutes = body.cancel_ahead_minutes
    write_audit(
        db,
        action="group_course.update",
        target_type="group_course",
        target_id=course.id,
        summary=f"更新团课 {course.name}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=mid,
    )
    db.commit()
    db.refresh(course)
    return course


SITE_TZ = ZoneInfo("Asia/Shanghai")


@router.get("/group-sessions", response_model=PageOut[GroupSessionOut])
def list_group_sessions(
    merchant_id: int | None = None,
    course_id: int | None = None,
    coach_id: int | None = None,
    status: str | None = None,
    on_date: date | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("course:manage", "course:book", "course:checkin")
    mid = ctx.resolve_merchant_id(merchant_id, required=False)
    filters = []
    if mid is not None:
        filters.append(GroupSession.merchant_id == mid)
    if course_id is not None:
        filters.append(GroupSession.course_id == course_id)
    if coach_id is not None:
        filters.append(GroupSession.coach_id == coach_id)
    if status:
        filters.append(GroupSession.status == status)
    if on_date is not None:
        # 按场地本地日筛选（北京时间），避免 UTC 日期和前台展示错位
        day_start = datetime.combine(on_date, time.min, tzinfo=SITE_TZ).astimezone(timezone.utc)
        filters.append(GroupSession.starts_at >= day_start)
        filters.append(GroupSession.starts_at < day_start + timedelta(days=1))
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        extras = [
            GroupSession.room.ilike(like),
            GroupSession.course_id.in_(select(GroupCourse.id).where(GroupCourse.name.ilike(like))),
            GroupSession.coach_id.in_(select(Coach.id).where(Coach.display_name.ilike(like))),
        ]
        if keyword.isdigit():
            extras.append(GroupSession.id == int(keyword))
        filters.append(or_(*extras))
    if _coach_scope_only(ctx):
        own = _own_coach(db, ctx, mid or ctx.merchant_id)
        if own is None:
            return PageOut(items=[], total=0, page=page, page_size=page_size)
        filters.append(GroupSession.coach_id == own.id)
    base = select(GroupSession)
    if filters:
        base = base.where(*filters)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = list(
        db.scalars(
            base.order_by(GroupSession.starts_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return PageOut(items=rows, total=total, page=page, page_size=page_size)


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


@router.patch("/group-sessions/{session_id}", response_model=GroupSessionOut)
def update_group_session(
    session_id: int,
    body: GroupSessionPatch,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("course:manage")
    session = db.get(GroupSession, session_id)
    if session is None:
        raise AppError("not_found", "场次不存在", status_code=404)
    mid = ctx.resolve_merchant_id(session.merchant_id)
    data = body.model_dump(exclude_unset=True)
    if "course_id" in data:
        course = db.get(GroupCourse, data["course_id"])
        if course is None or course.merchant_id != mid:
            raise AppError("not_found", "课程不存在", status_code=404)
        session.course_id = course.id
    if "coach_id" in data:
        coach = db.get(Coach, data["coach_id"])
        if coach is None or coach.merchant_id != mid or not coach.is_active:
            raise AppError("coach_unavailable", "教练不可用", status_code=400)
        session.coach_id = coach.id
    if "starts_at" in data:
        session.starts_at = data["starts_at"]
    if "ends_at" in data:
        session.ends_at = data["ends_at"]
    if session.ends_at <= session.starts_at:
        raise AppError("invalid_time", "结束时间必须晚于开始时间", status_code=400)
    if "room" in data:
        session.room = data["room"]
    if "capacity" in data:
        taken = booked_count(db, session.id)
        if data["capacity"] < taken:
            raise AppError("capacity_too_small", "上限不能小于已预约人数", status_code=400)
        session.capacity = data["capacity"]
    if "status" in data:
        if data["status"] not in {s.value for s in GroupSessionStatus}:
            raise AppError("invalid_status", "场次状态无效", status_code=400)
        if data["status"] == GroupSessionStatus.CANCELLED.value:
            cancel_group_session(
                db,
                session,
                actor_staff_id=ctx.staff.id,
                site_id=ctx.site_id,
            )
        else:
            session.status = data["status"]
    write_audit(
        db,
        action="group_session.update",
        target_type="group_session",
        target_id=session.id,
        summary=f"编辑场次 course={session.course_id} coach={session.coach_id}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=mid,
    )
    db.commit()
    db.refresh(session)
    return session


@router.delete("/group-sessions/{session_id}", response_model=GroupSessionOut)
def delete_group_session(
    session_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """软删除场次：不落物理删除，标记为已取消并释放已预约名额。"""
    ctx.require_permission("course:manage")
    session = db.get(GroupSession, session_id)
    if session is None:
        raise AppError("not_found", "场次不存在", status_code=404)
    ctx.resolve_merchant_id(session.merchant_id)
    if not ctx.is_site_admin and session.merchant_id != ctx.merchant_id:
        raise AppError("forbidden", "禁止跨商户", status_code=403)
    cancel_group_session(
        db,
        session,
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
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


@router.get("/group-bookings", response_model=PageOut[BookingOut])
def list_bookings(
    session_id: int | None = None,
    merchant_id: int | None = None,
    status: str | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("course:book", "course:checkin", "course:manage")
    mid = ctx.resolve_merchant_id(merchant_id, required=False)
    filters = [GroupBooking.merchant_id == mid] if mid is not None else []
    if session_id is not None:
        filters.append(GroupBooking.session_id == session_id)
    if status:
        filters.append(GroupBooking.status == status)
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        mid_sq = select(Member.id).where(or_(Member.phone.ilike(like), Member.name.ilike(like)))
        filters.append(GroupBooking.member_id.in_(mid_sq))
    base = select(GroupBooking)
    if filters:
        base = base.where(*filters)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = list(
        db.scalars(
            base
            .order_by(GroupBooking.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    briefs = load_member_briefs(db, {r.member_id for r in rows})
    items = [
        BookingOut(
            id=r.id,
            session_id=r.session_id,
            merchant_id=r.merchant_id,
            member_id=r.member_id,
            status=r.status,
            member=briefs.get(r.member_id),
        )
        for r in rows
    ]
    return PageOut(items=items, total=total, page=page, page_size=page_size)


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
    session = db.get(GroupSession, booking.session_id)
    if session is None:
        raise AppError("not_found", "场次不存在", status_code=404)
    if _coach_scope_only(ctx):
        own = _own_coach(db, ctx, mid)
        if own is None or session.coach_id != own.id:
            raise AppError("forbidden", "仅可操作本人场次", status_code=403)
    checkin_group_booking(
        db,
        booking,
        body.status,
        session=session,
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
    )
    db.commit()
    db.refresh(booking)
    return booking
