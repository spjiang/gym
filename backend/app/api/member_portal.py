"""会员端门户 API：会籍、团课、购卡买课、支付、通行。"""

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import MemberContext, get_current_member
from app.errors import AppError
from app.models.access import AccessEvent
from app.models.commerce import Order, OrderStatus, Payment, PaymentChannel, PaymentKind
from app.models.course import (
    GroupBooking,
    GroupCourse,
    GroupSession,
    GroupSessionStatus,
    PtOrderLink,
    PtPackage,
    PtPackageProduct,
)
from app.models.coupon import CouponTemplate, MemberCoupon
from app.models.member import MerchantMember
from app.models.membership import (
    Membership,
    MembershipOrderAction,
    MembershipOrderLink,
    MembershipProduct,
)
from app.schemas.common import OrderOut
from app.services.audit import write_audit
from app.services.course_booking import book_group_session, cancel_group_booking
from app.services.fulfillment import fulfill_membership_order, product_access_point_ids, validate_product_for_sale
from app.services.payments import get_online_provider
from app.services.pt_fulfillment import fulfill_pt_package_order
from app.services.coupon import issue_member_coupon, list_claimable_templates, redeem_coupon_for_order
from app.services.pricing import effective_price

router = APIRouter(prefix="/member", tags=["member-portal"])


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MemberMeOut(BaseModel):
    id: int
    site_id: int
    phone: str
    name: str
    face_status: str
    merchant_ids: list[int]


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


class PtPackageOut(ORMModel):
    id: int
    merchant_id: int
    product_id: int
    remaining_sessions: int
    status: str
    starts_at: datetime | None
    ends_at: datetime | None


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


class ClaimCouponIn(BaseModel):
    merchant_id: int
    template_id: int


class GroupSessionOut(ORMModel):
    id: int
    merchant_id: int
    course_id: int
    coach_id: int
    starts_at: datetime
    ends_at: datetime
    capacity: int
    status: str


class BookingOut(ORMModel):
    id: int
    merchant_id: int
    session_id: int
    member_id: int
    status: str


class BookIn(BaseModel):
    merchant_id: int
    session_id: int


class PurchaseMembershipIn(BaseModel):
    merchant_id: int
    product_id: int


class PurchasePtIn(BaseModel):
    merchant_id: int
    product_id: int


def _merchant_ids(db: Session, member_id: int) -> list[int]:
    return list(
        db.scalars(select(MerchantMember.merchant_id).where(MerchantMember.member_id == member_id)).all()
    )


@router.get("/me", response_model=MemberMeOut)
def member_me(db: Session = Depends(get_db), mctx: MemberContext = Depends(get_current_member)):
    m = mctx.member
    return MemberMeOut(
        id=m.id,
        site_id=m.site_id,
        phone=m.phone,
        name=m.name,
        face_status=m.face_status,
        merchant_ids=_merchant_ids(db, m.id),
    )


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
    return list(db.scalars(q.order_by(Membership.id.desc())).all())


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
    return list(db.scalars(q.order_by(PtPackage.id.desc())).all())


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
    mctx.require_merchant(db, merchant_id)
    return list(
        db.scalars(
            select(GroupSession)
            .where(
                GroupSession.merchant_id == merchant_id,
                GroupSession.status == GroupSessionStatus.OPEN.value,
            )
            .order_by(GroupSession.starts_at.asc())
        ).all()
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
    return list(db.scalars(q.order_by(GroupBooking.id.desc())).all())


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
    return booking


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
    return booking


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
    return [
        CatalogProductOut(
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
        for p in rows
    ]


@router.get("/coupons/claimable", response_model=list[ClaimableCouponOut])
def list_claimable_coupons(
    merchant_id: int,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    mctx.require_merchant(db, merchant_id)
    return list_claimable_templates(db, merchant_id=merchant_id)


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
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    q = select(MemberCoupon).where(MemberCoupon.member_id == mctx.member.id)
    if merchant_id is not None:
        mctx.require_merchant(db, merchant_id)
        q = q.where(MemberCoupon.merchant_id == merchant_id)
    return list(db.scalars(q.order_by(MemberCoupon.id.desc())).all())


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
    return [
        CatalogPtOut(
            id=p.id,
            merchant_id=p.merchant_id,
            name=p.name,
            price=p.price,
            session_count=p.session_count,
            valid_days=p.valid_days,
            effective_price=effective_price(p.price, p.promo_price, p.promo_starts_at, p.promo_ends_at),
        )
        for p in rows
    ]


@router.post("/orders/membership", response_model=OrderOut)
def order_membership(
    body: PurchaseMembershipIn,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    mctx.require_merchant(db, body.merchant_id)
    product = db.get(MembershipProduct, body.product_id)
    if product is None or product.merchant_id != body.merchant_id:
        raise AppError("not_found", "卡种不存在", status_code=404)
    ap_ids = product_access_point_ids(db, product.id)
    validate_product_for_sale(product, ap_ids)

    order = Order(
        site_id=mctx.site_id,
        merchant_id=body.merchant_id,
        member_id=mctx.member.id,
        order_type="membership",
        title=f"办卡-{product.name}",
        amount=effective_price(product.price, product.promo_price, product.promo_starts_at, product.promo_ends_at),
        status=OrderStatus.PENDING.value,
    )
    db.add(order)
    db.flush()
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
    product = db.get(PtPackageProduct, body.product_id)
    if product is None or product.merchant_id != body.merchant_id:
        raise AppError("not_found", "课包商品不存在", status_code=404)
    if not product.is_active:
        raise AppError("product_inactive", "课包已停用", status_code=400)

    order = Order(
        site_id=mctx.site_id,
        merchant_id=body.merchant_id,
        member_id=mctx.member.id,
        order_type="pt_package",
        title=f"私教课包-{product.name}",
        amount=effective_price(product.price, product.promo_price, product.promo_starts_at, product.promo_ends_at),
        status=OrderStatus.PENDING.value,
    )
    db.add(order)
    db.flush()
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


@router.post("/orders/{order_id}/pay/online", response_model=OrderOut)
def pay_my_order_online(
    order_id: int,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    order = db.get(Order, order_id)
    if order is None or order.member_id != mctx.member.id:
        raise AppError("not_found", "订单不存在", status_code=404)
    if order.status != OrderStatus.PENDING.value:
        raise AppError("invalid_state", "仅待支付订单可发起线上支付", status_code=400)

    result = get_online_provider().create_payment(
        order_id=order.id, amount=str(order.amount), title=order.title
    )
    if not result.ok:
        raise AppError("online_pay_failed", result.message, status_code=400)

    order.status = OrderStatus.PAID.value
    db.add(
        Payment(
            order_id=order.id,
            kind=PaymentKind.CHARGE.value,
            channel=PaymentChannel.ONLINE.value,
            amount=order.amount,
            note=result.provider_ref,
        )
    )
    write_audit(
        db,
        action="member.pay_online",
        target_type="order",
        target_id=order.id,
        summary="会员线上支付",
        site_id=mctx.site_id,
        merchant_id=order.merchant_id,
    )
    fulfill_membership_order(db, order, actor_staff_id=None)
    fulfill_pt_package_order(db, order, actor_staff_id=None)
    redeem_coupon_for_order(db, order, actor_staff_id=None)
    db.commit()
    db.refresh(order)
    return order
