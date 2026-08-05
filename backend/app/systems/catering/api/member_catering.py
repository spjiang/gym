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
from app.systems.catering.models.catering import CateringMenuItem, CateringOrderItem
from app.systems.platform.models.commerce import Order, OrderStatus
from app.systems.platform.models.org import Merchant
from app.systems.platform.services.audit import write_audit

router = APIRouter(prefix="/member/catering", tags=["member-catering"])


class MenuItemOut(BaseModel):
    id: int
    merchant_id: int
    name: str
    category: str
    price: Decimal
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


def assign_pickup_code(order_id: int) -> str:
    return f"C{str(order_id).zfill(4)[-4:]}"


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
            .where(
                CateringMenuItem.merchant_id == merchant_id,
                CateringMenuItem.is_active.is_(True),
            )
            .order_by(CateringMenuItem.category, CateringMenuItem.id)
        ).all()
    )


@router.post("/checkout", response_model=OrderOut)
def checkout(
    body: CheckoutIn,
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    merchant = _require_member_catering(db, mctx, body.merchant_id)
    lines: list[tuple[CateringMenuItem, int]] = []
    total = Decimal("0")
    names: list[str] = []
    for line in body.items:
        item = db.get(CateringMenuItem, line.menu_item_id)
        if item is None or item.merchant_id != body.merchant_id or not item.is_active:
            raise AppError("invalid_menu_item", f"菜单项不可用: {line.menu_item_id}", status_code=400)
        lines.append((item, line.quantity))
        total += item.price * line.quantity
        names.append(f"{item.name}×{line.quantity}")
    if total <= 0:
        raise AppError("validation_error", "订单金额必须大于 0", status_code=422)

    note_parts = []
    if body.table_no and body.table_no.strip():
        note_parts.append(f"桌号:{body.table_no.strip()}")
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
        summary=f"会员餐饮点单 ¥{total}",
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
