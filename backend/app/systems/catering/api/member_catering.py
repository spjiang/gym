"""会员端餐饮：菜单、点餐、订单（退款请走管理端）。"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import MemberContext, get_current_member
from app.core.domain.subsystems import assert_merchant_has_system
from app.core.errors import AppError
from app.core.schemas.common import OrderOut
from app.systems.catering.models.catering import CateringMenuCategory, CateringMenuItem, CateringOrderItem
from app.systems.catering.services.tables import get_active_table, list_active_tables
from app.systems.gym.services.coupon import compute_payable, list_unused_coupons_for_order_type
from app.systems.platform.models.commerce import Order, OrderStatus
from app.systems.platform.models.org import Merchant
from app.systems.platform.services.audit import write_audit
from app.systems.platform.services.agreements import require_enabled_agreement
from app.systems.platform.services.order_pricing import price_order, quote_price

router = APIRouter(prefix="/member/catering", tags=["member-catering"])


class MenuItemOut(BaseModel):
    id: int
    merchant_id: int
    name: str
    category: str
    category_id: int | None = None
    price: Decimal
    image_url: str | None = None
    description: str | None = None
    is_active: bool

    model_config = {"from_attributes": True}


class CheckoutLineIn(BaseModel):
    menu_item_id: int
    quantity: int = Field(ge=1, le=99)


class CheckoutIn(BaseModel):
    merchant_id: int
    items: list[CheckoutLineIn] = Field(min_length=1)
    note: str | None = None
    table_no: str | None = None
    member_coupon_id: int | None = None


class QuoteCouponOut(BaseModel):
    id: int
    name: str
    discount_type: str
    threshold_amount: Decimal
    fixed_amount: Decimal | None = None
    percent_off: int | None = None
    eligible: bool
    ineligible_reason: str | None = None


class DiningQuoteOut(BaseModel):
    original_amount: Decimal
    promotion_discount_amount: Decimal
    promotion_rate: Decimal
    coupon_discount_amount: Decimal
    payable: Decimal
    coupons: list[QuoteCouponOut] = Field(default_factory=list)


class OrderLineOut(BaseModel):
    menu_item_id: int
    name: str
    unit_price: Decimal
    quantity: int
    line_amount: Decimal


class DiningOrderDetailOut(OrderOut):
    items: list[OrderLineOut] = Field(default_factory=list)


def _require_member_catering(db: Session, mctx: MemberContext, merchant_id: int) -> Merchant:
    mctx.require_merchant(db, merchant_id)
    merchant = db.get(Merchant, merchant_id)
    if merchant is None or merchant.site_id != mctx.site_id:
        raise AppError("not_found", "商户不存在", status_code=404)
    assert_merchant_has_system(db, merchant_id, "catering")
    return merchant


class TableResolveOut(BaseModel):
    id: int
    merchant_id: int
    name: str
    code: str


class MemberTableOut(BaseModel):
    id: int
    name: str


@router.get("/table", response_model=TableResolveOut)
def resolve_table(
    merchant_id: int,
    code: str,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    """扫码点餐：用桌台点餐码解析桌号名称。"""
    _require_member_catering(db, mctx, merchant_id)
    row = get_active_table(db, merchant_id=merchant_id, code=code)
    return TableResolveOut(id=row.id, merchant_id=row.merchant_id, name=row.name, code=row.code)


@router.get("/tables", response_model=list[MemberTableOut])
def list_member_tables(
    merchant_id: int,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    """会员点餐选桌：只返回启用桌的名称，不暴露点餐码。"""
    _require_member_catering(db, mctx, merchant_id)
    return [
        MemberTableOut(id=row.id, name=row.name)
        for row in list_active_tables(db, merchant_id=merchant_id)
    ]


def assign_pickup_code(order_id: int) -> str:
    return f"C{order_id}"


@router.get("/menu", response_model=list[MenuItemOut])
def list_menu(
    merchant_id: int,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    _require_member_catering(db, mctx, merchant_id)
    return list(
        db.scalars(
            select(CateringMenuItem)
            .outerjoin(CateringMenuCategory, CateringMenuCategory.id == CateringMenuItem.category_id)
            .where(
                CateringMenuItem.merchant_id == merchant_id,
                CateringMenuItem.is_active.is_(True),
            )
            .order_by(
                CateringMenuCategory.sort_order.asc(),
                CateringMenuItem.category.asc(),
                CateringMenuItem.id.asc(),
            )
        ).all()
    )


@router.get("/menu/{item_id}", response_model=MenuItemOut)
def get_menu_item(
    item_id: int,
    merchant_id: int,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    """会员查看在售菜品详情（大图、完整简介）。"""
    _require_member_catering(db, mctx, merchant_id)
    item = db.get(CateringMenuItem, item_id)
    if item is None or item.merchant_id != merchant_id or not item.is_active:
        raise AppError("not_found", "菜品不存在或已下架", status_code=404)
    return item


def _collect_lines(
    db: Session, merchant_id: int, items: list[CheckoutLineIn]
) -> tuple[list[tuple[CateringMenuItem, int]], Decimal, list[str]]:
    lines: list[tuple[CateringMenuItem, int]] = []
    total = Decimal("0")
    names: list[str] = []
    for line in items:
        item = db.get(CateringMenuItem, line.menu_item_id)
        if item is None or item.merchant_id != merchant_id or not item.is_active:
            raise AppError("invalid_menu_item", f"菜单项不可用: {line.menu_item_id}", status_code=400)
        lines.append((item, line.quantity))
        total += item.price * line.quantity
        names.append(f"{item.name}×{line.quantity}")
    if total <= 0:
        raise AppError("validation_error", "订单金额必须大于 0", status_code=422)
    return lines, total, names


def _coupon_options(
    db: Session,
    *,
    member_id: int,
    merchant_id: int,
    after_promo: Decimal,
) -> list[QuoteCouponOut]:
    options: list[QuoteCouponOut] = []
    for mc, tpl in list_unused_coupons_for_order_type(
        db, member_id=member_id, merchant_id=merchant_id, order_type="dining"
    ):
        eligible = True
        reason: str | None = None
        try:
            compute_payable(after_promo, tpl)
        except AppError as exc:
            eligible = False
            reason = exc.message
        options.append(
            QuoteCouponOut(
                id=mc.id,
                name=tpl.name,
                discount_type=tpl.discount_type,
                threshold_amount=tpl.threshold_amount,
                fixed_amount=tpl.fixed_amount,
                percent_off=tpl.percent_off,
                eligible=eligible,
                ineligible_reason=reason,
            )
        )
    return options


@router.post("/quote", response_model=DiningQuoteOut)
def quote_checkout(
    body: CheckoutIn,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    """点餐预览：推广折扣 + 可用餐饮券。"""
    _require_member_catering(db, mctx, body.merchant_id)
    _lines, total, _names = _collect_lines(db, body.merchant_id, body.items)
    base = quote_price(
        db,
        member_id=mctx.member.id,
        merchant_id=body.merchant_id,
        order_type="dining",
        original_amount=total,
    )
    coupons = _coupon_options(
        db, member_id=mctx.member.id, merchant_id=body.merchant_id, after_promo=base.payable
    )
    coupon_id = body.member_coupon_id
    if coupon_id is not None and not any(c.id == coupon_id and c.eligible for c in coupons):
        coupon_id = None
    priced = (
        quote_price(
            db,
            member_id=mctx.member.id,
            merchant_id=body.merchant_id,
            order_type="dining",
            original_amount=total,
            member_coupon_id=coupon_id,
        )
        if coupon_id is not None
        else base
    )
    return DiningQuoteOut(
        original_amount=priced.original_amount,
        promotion_discount_amount=priced.promotion_discount_amount,
        promotion_rate=priced.promotion_rate,
        coupon_discount_amount=priced.coupon_discount_amount,
        payable=priced.payable,
        coupons=coupons,
    )


@router.post("/checkout", response_model=OrderOut)
def checkout(
    body: CheckoutIn,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    merchant = _require_member_catering(db, mctx, body.merchant_id)
    require_enabled_agreement(db, merchant_id=body.merchant_id, scene="dining")
    lines, total, names = _collect_lines(db, body.merchant_id, body.items)

    note_parts = []
    if body.table_no and body.table_no.strip():
        from app.systems.catering.services.tables import require_active_table_label

        table = require_active_table_label(db, merchant_id=body.merchant_id, table_no=body.table_no)
        note_parts.append(f"桌号:{table.name}")
    if body.note and body.note.strip():
        note_parts.append(body.note.strip())
    customer_note = "；".join(note_parts)[:255] or None

    title = f"{merchant.name}点单：{'、'.join(names[:3])}"
    order = Order(
        site_id=mctx.site_id,
        merchant_id=body.merchant_id,
        member_id=mctx.member.id,
        order_type="dining",
        title=title[:255],
        amount=total,
        status=OrderStatus.PENDING.value,
        customer_note=customer_note,
    )
    db.add(order)
    db.flush()
    price_order(db, order=order, original_amount=total, member_coupon_id=body.member_coupon_id)
    for item, qty in lines:
        db.add(
            CateringOrderItem(
                order_id=order.id,
                menu_item_id=item.id,
                name_snapshot=item.name,
                unit_price=item.price,
                quantity=qty,
                line_amount=item.price * qty,
            )
        )
    write_audit(
        db,
        action="member.dining_checkout",
        target_type="order",
        target_id=order.id,
        summary=f"会员餐饮点单 ¥{order.amount}",
        site_id=mctx.site_id,
        merchant_id=body.merchant_id,
    )
    db.commit()
    db.refresh(order)
    return order


@router.get("/orders", response_model=list[OrderOut])
def list_orders(
    merchant_id: int,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    _require_member_catering(db, mctx, merchant_id)
    return list(
        db.scalars(
            select(Order)
            .where(
                Order.member_id == mctx.member.id,
                Order.merchant_id == merchant_id,
                Order.order_type == "dining",
            )
            .order_by(Order.id.desc())
        ).all()
    )


def _order_detail(db: Session, order: Order) -> DiningOrderDetailOut:
    rows = list(db.scalars(select(CateringOrderItem).where(CateringOrderItem.order_id == order.id)).all())
    return DiningOrderDetailOut(
        id=order.id,
        site_id=order.site_id,
        merchant_id=order.merchant_id,
        member_id=order.member_id,
        order_type=order.order_type,
        title=order.title,
        amount=order.amount,
        status=order.status,
        pickup_code=order.pickup_code,
        customer_note=order.customer_note,
        dining_status=order.dining_status,
        original_amount=order.original_amount,
        promotion_discount_amount=order.promotion_discount_amount,
        created_at=order.created_at,
        items=[
            OrderLineOut(
                menu_item_id=r.menu_item_id,
                name=r.name_snapshot,
                unit_price=r.unit_price,
                quantity=r.quantity,
                line_amount=r.line_amount,
            )
            for r in rows
        ],
    )


@router.get("/orders/{order_id}", response_model=DiningOrderDetailOut)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    order = db.get(Order, order_id)
    if order is None or order.member_id != mctx.member.id or order.order_type != "dining":
        raise AppError("not_found", "订单不存在", status_code=404)
    return _order_detail(db, order)


@router.post("/orders/{order_id}/cancel", response_model=DiningOrderDetailOut)
def cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    """会员取消待支付点餐单。"""
    from app.systems.catering.services.kitchen import cancel_pending_dining_order

    order = db.get(Order, order_id)
    if order is None or order.member_id != mctx.member.id or order.order_type != "dining":
        raise AppError("not_found", "订单不存在", status_code=404)
    cancel_pending_dining_order(db, order)
    db.commit()
    db.refresh(order)
    return _order_detail(db, order)
