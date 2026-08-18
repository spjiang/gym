"""会籍卡种与办卡/续卡/停卡 API。"""

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import RequestContext, get_current_context
from app.core.domain.subsystems import assert_merchant_has_system
from app.core.errors import AppError
from app.core.schemas.common import MemberBrief, OrderOut
from app.core.schemas.paging import PageOut, paginate
from app.systems.platform.models.access import AccessPoint
from app.systems.platform.models.commerce import Order, OrderStatus
from app.systems.platform.models.member import Member, MerchantMember
from app.systems.gym.models.membership import (
    ConsumptionSource,
    Membership,
    MembershipConsumption,
    MembershipOrderAction,
    MembershipOrderLink,
    MembershipProduct,
    MembershipProductAccessPoint,
    ProductType,
)
from app.systems.platform.models.identity import StaffUser
from app.systems.platform.models.org import Merchant
from app.systems.platform.services.audit import write_audit
from app.systems.gym.services.fulfillment import (
    consume_membership,
    freeze_membership,
    product_access_point_ids,
    update_membership,
    validate_product_for_sale,
    void_membership,
)
from app.systems.gym.services.pricing import effective_price
from app.systems.platform.services.order_pricing import price_order

router = APIRouter(tags=["membership"])


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProductIn(BaseModel):
    merchant_id: int | None = None
    name: str = Field(min_length=1, max_length=128)
    product_type: str
    price: Decimal
    duration_days: int | None = None
    session_count: int | None = None
    stored_value: Decimal | None = None
    access_point_ids: list[int] = Field(default_factory=list)
    is_active: bool = True
    is_trial: bool = False
    promo_price: Decimal | None = None
    promo_starts_at: datetime | None = None
    promo_ends_at: datetime | None = None


class ProductOut(ORMModel):
    id: int
    merchant_id: int
    name: str
    product_type: str
    price: Decimal
    duration_days: int | None
    session_count: int | None
    stored_value: Decimal | None
    is_active: bool
    is_trial: bool
    promo_price: Decimal | None
    promo_starts_at: datetime | None
    promo_ends_at: datetime | None
    access_point_ids: list[int] = []
    created_at: datetime
    effective_price: Decimal | None = None


class MembershipOut(ORMModel):
    id: int
    merchant_id: int
    member_id: int
    product_id: int
    product_type: str
    status: str
    starts_at: datetime | None
    ends_at: datetime | None
    remaining_sessions: int | None
    balance: Decimal | None
    remark: str | None = None
    created_at: datetime
    member: MemberBrief | None = None


class PurchaseIn(BaseModel):
    member_id: int
    product_id: int
    merchant_id: int | None = None
    member_coupon_id: int | None = None


class RenewIn(BaseModel):
    membership_id: int
    product_id: int | None = None
    merchant_id: int | None = None
    member_coupon_id: int | None = None


class ConsumeIn(BaseModel):
    """次卡传 sessions，储值卡传 amount。"""

    sessions: int | None = Field(default=None, ge=1, le=100)
    amount: Decimal | None = None
    note: str | None = Field(default=None, max_length=255)


class ConsumptionOut(ORMModel):
    id: int
    membership_id: int
    member_id: int
    kind: str
    sessions: int | None
    amount: Decimal | None
    remaining_sessions_after: int | None
    balance_after: Decimal | None
    source: str
    note: str | None
    actor_name: str | None = None
    created_at: datetime


class MembershipConsumeOut(BaseModel):
    membership: MembershipOut
    consumption: ConsumptionOut


class MembershipPatch(BaseModel):
    member_id: int | None = None
    product_id: int | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    remaining_sessions: int | None = None
    balance: Decimal | None = None
    status: str | None = None
    remark: str | None = None


def _product_out(db: Session, p: MembershipProduct) -> ProductOut:
    return ProductOut(
        id=p.id,
        merchant_id=p.merchant_id,
        name=p.name,
        product_type=p.product_type,
        price=p.price,
        duration_days=p.duration_days,
        session_count=p.session_count,
        stored_value=p.stored_value,
        is_active=p.is_active,
        is_trial=p.is_trial,
        promo_price=p.promo_price,
        promo_starts_at=p.promo_starts_at,
        promo_ends_at=p.promo_ends_at,
        access_point_ids=product_access_point_ids(db, p.id),
        created_at=p.created_at,
        effective_price=effective_price(p.price, p.promo_price, p.promo_starts_at, p.promo_ends_at),
    )


def _ensure_member_in_merchant(db: Session, *, member_id: int, merchant_id: int, site_id: int) -> Member:
    member = db.get(Member, member_id)
    if member is None or member.site_id != site_id:
        raise AppError("not_found", "会员不存在", status_code=404)
    link = db.scalar(
        select(MerchantMember).where(
            MerchantMember.member_id == member_id, MerchantMember.merchant_id == merchant_id
        )
    )
    if link is None:
        db.add(MerchantMember(member_id=member_id, merchant_id=merchant_id))
        db.flush()
    return member


def _replace_product_points(db: Session, product_id: int, access_point_ids: list[int], merchant_id: int) -> None:
    for ap_id in access_point_ids:
        ap = db.get(AccessPoint, ap_id)
        if ap is None:
            raise AppError("invalid_access_point", f"门禁点不存在: {ap_id}", status_code=400)
        if not ap.is_public_area and ap.merchant_id != merchant_id:
            raise AppError("invalid_access_point", f"门禁点不可用: {ap_id}", status_code=400)
    existing = list(
        db.scalars(
            select(MembershipProductAccessPoint).where(MembershipProductAccessPoint.product_id == product_id)
        ).all()
    )
    for row in existing:
        db.delete(row)
    db.flush()
    for ap_id in access_point_ids:
        db.add(MembershipProductAccessPoint(product_id=product_id, access_point_id=ap_id))
    db.flush()


@router.get("/membership-products", response_model=PageOut[ProductOut])
def list_products(
    merchant_id: int | None = None,
    q: str | None = None,
    product_type: str | None = None,
    is_active: bool | None = None,
    is_trial: bool | None = None,
    access_point_id: int | None = None,
    price_min: Decimal | None = None,
    price_max: Decimal | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("membership:manage", "membership:sell")
    mid = ctx.resolve_merchant_id(merchant_id, required=False)
    stmt = select(MembershipProduct)
    if mid is not None:
        stmt = stmt.where(MembershipProduct.merchant_id == mid)
    else:
        stmt = stmt.join(Merchant, Merchant.id == MembershipProduct.merchant_id).where(
            Merchant.site_id == ctx.site_id
        )
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        conds = [MembershipProduct.name.ilike(like)]
        if keyword.isdigit():
            conds.append(MembershipProduct.id == int(keyword))
        stmt = stmt.where(or_(*conds))
    if product_type:
        stmt = stmt.where(MembershipProduct.product_type == product_type)
    if is_active is not None:
        stmt = stmt.where(MembershipProduct.is_active.is_(is_active))
    if is_trial is not None:
        stmt = stmt.where(MembershipProduct.is_trial.is_(is_trial))
    if access_point_id is not None:
        stmt = stmt.where(
            MembershipProduct.id.in_(
                select(MembershipProductAccessPoint.product_id).where(
                    MembershipProductAccessPoint.access_point_id == access_point_id
                )
            )
        )
    if price_min is not None:
        stmt = stmt.where(MembershipProduct.price >= price_min)
    if price_max is not None:
        stmt = stmt.where(MembershipProduct.price <= price_max)
    rows, total = paginate(db, stmt.order_by(MembershipProduct.id.desc()), page=page, page_size=page_size)
    return PageOut(items=[_product_out(db, p) for p in rows], total=total, page=page, page_size=page_size)


@router.post("/membership-products", response_model=ProductOut)
def create_product(
    body: ProductIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("membership:manage")
    mid = ctx.resolve_merchant_id(body.merchant_id)
    merchant = db.get(Merchant, mid)
    if merchant is None or merchant.site_id != ctx.site_id:
        raise AppError("not_found", "商户不存在", status_code=404)
    assert_merchant_has_system(db, mid, "gym")

    product = MembershipProduct(
        merchant_id=mid,
        name=body.name,
        product_type=body.product_type,
        price=body.price,
        duration_days=body.duration_days,
        session_count=body.session_count,
        stored_value=body.stored_value,
        is_trial=body.is_trial,
        promo_price=body.promo_price,
        promo_starts_at=body.promo_starts_at,
        promo_ends_at=body.promo_ends_at,
        is_active=False,
    )
    db.add(product)
    db.flush()
    _replace_product_points(db, product.id, body.access_point_ids, mid)
    if body.is_active:
        validate_product_for_sale(product, body.access_point_ids, require_active=False)
        product.is_active = True
    else:
        # 未启用时仍校验类型字段组合
        if body.product_type == ProductType.TERM.value and (not body.duration_days or body.duration_days <= 0):
            raise AppError("invalid_product", "期限卡必须配置有效天数", status_code=400)
        if body.product_type == ProductType.COUNT.value and (not body.session_count or body.session_count <= 0):
            raise AppError("invalid_product", "次卡必须配置次数", status_code=400)
        if body.product_type == ProductType.VALUE.value and (body.stored_value is None or body.stored_value <= 0):
            raise AppError("invalid_product", "储值卡必须配置储值额度", status_code=400)
        if body.product_type not in {t.value for t in ProductType}:
            raise AppError("invalid_product", "未知卡种类型", status_code=400)
    write_audit(
        db,
        action="membership_product.create",
        target_type="membership_product",
        target_id=product.id,
        summary=f"创建卡种 {product.name}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=mid,
    )
    db.commit()
    db.refresh(product)
    return _product_out(db, product)


@router.patch("/membership-products/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int,
    body: ProductIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("membership:manage")
    product = db.get(MembershipProduct, product_id)
    if product is None:
        raise AppError("not_found", "卡种不存在", status_code=404)
    mid = ctx.resolve_merchant_id(body.merchant_id or product.merchant_id)
    if product.merchant_id != mid:
        raise AppError("forbidden", "禁止跨商户修改", status_code=403)

    product.name = body.name
    product.product_type = body.product_type
    product.price = body.price
    product.duration_days = body.duration_days
    product.session_count = body.session_count
    product.stored_value = body.stored_value
    product.is_trial = body.is_trial
    product.promo_price = body.promo_price
    product.promo_starts_at = body.promo_starts_at
    product.promo_ends_at = body.promo_ends_at
    _replace_product_points(db, product.id, body.access_point_ids, mid)
    if body.is_active:
        validate_product_for_sale(product, body.access_point_ids, require_active=False)
    product.is_active = body.is_active
    write_audit(
        db,
        action="membership_product.update",
        target_type="membership_product",
        target_id=product.id,
        summary=f"更新卡种 {product.name}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=mid,
    )
    db.commit()
    db.refresh(product)
    return _product_out(db, product)


@router.post("/membership-products/{product_id}/deactivate", response_model=ProductOut)
def deactivate_product(
    product_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("membership:manage")
    product = db.get(MembershipProduct, product_id)
    if product is None:
        raise AppError("not_found", "卡种不存在", status_code=404)
    ctx.resolve_merchant_id(product.merchant_id)
    product.is_active = False
    db.commit()
    db.refresh(product)
    return _product_out(db, product)


@router.get("/memberships", response_model=PageOut[MembershipOut])
def list_memberships(
    merchant_id: int | None = None,
    member_id: int | None = None,
    status: str | None = None,
    product_type: str | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("membership:manage", "membership:sell", "member:read")
    mid = ctx.resolve_merchant_id(merchant_id, required=False)
    filters = []
    if mid is not None:
        filters.append(Membership.merchant_id == mid)
    else:
        filters.append(
            Membership.merchant_id.in_(select(Merchant.id).where(Merchant.site_id == ctx.site_id))
        )
    if member_id is not None:
        filters.append(Membership.member_id == member_id)
    if status:
        filters.append(Membership.status == status)
    if product_type:
        filters.append(Membership.product_type == product_type)
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        member_ids = select(Member.id).where(or_(Member.phone.ilike(like), Member.name.ilike(like)))
        filters.append(Membership.member_id.in_(member_ids))

    total = db.scalar(select(func.count()).select_from(Membership).where(*filters)) or 0
    rows = list(
        db.scalars(
            select(Membership)
            .where(*filters)
            .order_by(Membership.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    member_map = {
        m.id: m
        for m in db.scalars(
            select(Member).where(Member.id.in_({r.member_id for r in rows} or {-1}))
        ).all()
    }
    items: list[MembershipOut] = []
    for r in rows:
        m = member_map.get(r.member_id)
        items.append(
            MembershipOut(
                id=r.id,
                merchant_id=r.merchant_id,
                member_id=r.member_id,
                product_id=r.product_id,
                product_type=r.product_type,
                status=r.status,
                starts_at=r.starts_at,
                ends_at=r.ends_at,
                remaining_sessions=r.remaining_sessions,
                balance=r.balance,
                remark=r.remark,
                created_at=r.created_at,
                member=MemberBrief(id=m.id, name=m.name, phone=m.phone) if m else None,
            )
        )
    return PageOut(items=items, total=total, page=page, page_size=page_size)


def _membership_out(db: Session, row: Membership) -> MembershipOut:
    m = db.get(Member, row.member_id)
    return MembershipOut(
        id=row.id,
        merchant_id=row.merchant_id,
        member_id=row.member_id,
        product_id=row.product_id,
        product_type=row.product_type,
        status=row.status,
        starts_at=row.starts_at,
        ends_at=row.ends_at,
        remaining_sessions=row.remaining_sessions,
        balance=row.balance,
        remark=row.remark,
        created_at=row.created_at,
        member=MemberBrief(id=m.id, name=m.name, phone=m.phone) if m else None,
    )


@router.patch("/memberships/{membership_id}", response_model=MembershipOut)
def patch_membership(
    membership_id: int,
    body: MembershipPatch,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("membership:manage")
    membership = db.get(Membership, membership_id)
    if membership is None:
        raise AppError("not_found", "会籍不存在", status_code=404)
    mid = ctx.resolve_merchant_id(membership.merchant_id)
    identity_fields = {"member_id", "product_id"} & set(body.model_fields_set)
    if identity_fields and not ctx.is_site_admin:
        raise AppError("forbidden", "仅场地超管可改正会员或卡种", status_code=403)
    if body.member_id is not None and "member_id" in body.model_fields_set:
        _ensure_member_in_merchant(db, member_id=body.member_id, merchant_id=mid, site_id=ctx.site_id)
    update_membership(
        db,
        membership,
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        member_id=body.member_id,
        product_id=body.product_id,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        remaining_sessions=body.remaining_sessions,
        balance=body.balance,
        status=body.status,
        remark=body.remark,
        fields_set=set(body.model_fields_set),
    )
    db.commit()
    db.refresh(membership)
    return _membership_out(db, membership)


@router.post("/memberships/purchase", response_model=OrderOut)
def purchase_membership(
    body: PurchaseIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("membership:sell", "membership:manage")
    product = db.get(MembershipProduct, body.product_id)
    if product is None:
        raise AppError("not_found", "卡种不存在", status_code=404)
    mid = ctx.resolve_merchant_id(body.merchant_id or product.merchant_id)
    if product.merchant_id != mid:
        raise AppError("forbidden", "卡种不属于当前商户", status_code=403)
    assert_merchant_has_system(db, mid, "gym")
    ap_ids = product_access_point_ids(db, product.id)
    validate_product_for_sale(product, ap_ids)
    _ensure_member_in_merchant(db, member_id=body.member_id, merchant_id=mid, site_id=ctx.site_id)
    price = effective_price(product.price, product.promo_price, product.promo_starts_at, product.promo_ends_at)

    order = Order(
        site_id=ctx.site_id,
        merchant_id=mid,
        member_id=body.member_id,
        order_type="membership",
        title=f"办卡-{product.name}",
        amount=price,
        status=OrderStatus.PENDING.value,
        seller_staff_id=ctx.staff.id,
    )
    db.add(order)
    db.flush()
    if body.member_coupon_id is not None:
        ctx.require_permission("coupon:redeem", "coupon:manage", "membership:sell", "membership:manage")
    price_order(db, order=order, original_amount=price, member_coupon_id=body.member_coupon_id)
    db.add(
        MembershipOrderLink(
            order_id=order.id,
            member_id=body.member_id,
            product_id=product.id,
            action=MembershipOrderAction.PURCHASE.value,
        )
    )
    write_audit(
        db,
        action="membership.purchase_order",
        target_type="order",
        target_id=order.id,
        summary=f"办卡下单 product={product.id} member={body.member_id}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=mid,
    )
    db.commit()
    db.refresh(order)
    return order


@router.post("/memberships/renew", response_model=OrderOut)
def renew_membership(
    body: RenewIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("membership:sell", "membership:manage")
    membership = db.get(Membership, body.membership_id)
    if membership is None:
        raise AppError("not_found", "会籍不存在", status_code=404)
    mid = ctx.resolve_merchant_id(body.merchant_id or membership.merchant_id)
    if membership.merchant_id != mid:
        raise AppError("forbidden", "禁止跨商户续卡", status_code=403)
    assert_merchant_has_system(db, mid, "gym")
    product_id = body.product_id or membership.product_id
    product = db.get(MembershipProduct, product_id)
    if product is None or product.merchant_id != mid:
        raise AppError("not_found", "卡种不存在", status_code=404)
    ap_ids = product_access_point_ids(db, product.id)
    validate_product_for_sale(product, ap_ids)
    price = effective_price(product.price, product.promo_price, product.promo_starts_at, product.promo_ends_at)

    order = Order(
        site_id=ctx.site_id,
        merchant_id=mid,
        member_id=membership.member_id,
        order_type="membership",
        title=f"续卡-{product.name}",
        amount=price,
        status=OrderStatus.PENDING.value,
        seller_staff_id=ctx.staff.id,
    )
    db.add(order)
    db.flush()
    if body.member_coupon_id is not None:
        ctx.require_permission("coupon:redeem", "coupon:manage", "membership:sell", "membership:manage")
    price_order(db, order=order, original_amount=price, member_coupon_id=body.member_coupon_id)
    db.add(
        MembershipOrderLink(
            order_id=order.id,
            member_id=membership.member_id,
            product_id=product.id,
            action=MembershipOrderAction.RENEW.value,
            target_membership_id=membership.id,
        )
    )
    write_audit(
        db,
        action="membership.renew_order",
        target_type="order",
        target_id=order.id,
        summary=f"续卡下单 membership={membership.id}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=mid,
    )
    db.commit()
    db.refresh(order)
    return order


@router.post("/memberships/{membership_id}/freeze", response_model=MembershipOut)
def api_freeze(
    membership_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("membership:manage", "membership:sell")
    membership = db.get(Membership, membership_id)
    if membership is None:
        raise AppError("not_found", "会籍不存在", status_code=404)
    ctx.resolve_merchant_id(membership.merchant_id)
    freeze_membership(db, membership, actor_staff_id=ctx.staff.id, site_id=ctx.site_id)
    db.commit()
    db.refresh(membership)
    return _membership_out(db, membership)


def _consumption_out(row: MembershipConsumption, actor_name: str | None) -> ConsumptionOut:
    return ConsumptionOut(
        id=row.id,
        membership_id=row.membership_id,
        member_id=row.member_id,
        kind=row.kind,
        sessions=row.sessions,
        amount=row.amount,
        remaining_sessions_after=row.remaining_sessions_after,
        balance_after=row.balance_after,
        source=row.source,
        note=row.note,
        actor_name=actor_name,
        created_at=row.created_at,
    )


@router.post("/memberships/{membership_id}/consume", response_model=MembershipConsumeOut)
def api_consume(
    membership_id: int,
    body: ConsumeIn | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """次卡销次 / 储值卡按次计费。"""
    ctx.require_permission("membership:manage", "membership:sell")
    membership = db.get(Membership, membership_id)
    if membership is None:
        raise AppError("not_found", "会籍不存在", status_code=404)
    ctx.resolve_merchant_id(membership.merchant_id)
    body = body or ConsumeIn()
    record = consume_membership(
        db,
        membership,
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        sessions=body.sessions,
        amount=body.amount,
        source=ConsumptionSource.FRONT_DESK.value,
        note=body.note,
    )
    db.commit()
    db.refresh(membership)
    db.refresh(record)
    return MembershipConsumeOut(
        membership=_membership_out(db, membership),
        consumption=_consumption_out(record, ctx.staff.display_name),
    )


@router.get("/memberships/{membership_id}/consumptions", response_model=PageOut[ConsumptionOut])
def list_membership_consumptions(
    membership_id: int,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """查看会籍销次流水。"""
    ctx.require_permission("membership:manage", "membership:sell", "member:read")
    membership = db.get(Membership, membership_id)
    if membership is None:
        raise AppError("not_found", "会籍不存在", status_code=404)
    ctx.resolve_merchant_id(membership.merchant_id)
    stmt = select(MembershipConsumption).where(MembershipConsumption.membership_id == membership_id)
    if from_date is not None:
        stmt = stmt.where(MembershipConsumption.created_at >= from_date)
    if to_date is not None:
        stmt = stmt.where(MembershipConsumption.created_at <= to_date)
    rows, total = paginate(
        db, stmt.order_by(MembershipConsumption.id.desc()), page=page, page_size=page_size
    )
    staff_ids = {r.actor_staff_id for r in rows if r.actor_staff_id}
    names: dict[int, str] = {}
    if staff_ids:
        names = {
            s.id: s.display_name
            for s in db.scalars(select(StaffUser).where(StaffUser.id.in_(staff_ids))).all()
        }
    items = [
        _consumption_out(r, names.get(r.actor_staff_id) if r.actor_staff_id else None) for r in rows
    ]
    return PageOut(items=items, total=total, page=page, page_size=page_size)


@router.post("/memberships/{membership_id}/void", response_model=MembershipOut)
def api_void(
    membership_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("membership:manage")
    membership = db.get(Membership, membership_id)
    if membership is None:
        raise AppError("not_found", "会籍不存在", status_code=404)
    ctx.resolve_merchant_id(membership.merchant_id)
    void_membership(db, membership, actor_staff_id=ctx.staff.id, site_id=ctx.site_id)
    db.commit()
    db.refresh(membership)
    return _membership_out(db, membership)
