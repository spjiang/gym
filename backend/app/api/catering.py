"""餐饮管理：菜单维护 + 点单收款闭环。"""

from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import RequestContext, get_current_context
from app.domain.subsystems import assert_merchant_has_system
from app.errors import AppError
from app.models.catering import CateringMenuItem, CateringOrderItem
from app.models.commerce import Order, OrderStatus
from app.models.org import Merchant
from app.schemas.common import OrderOut
from app.services.audit import write_audit

router = APIRouter(prefix="/catering", tags=["catering"])


class MenuItemIn(BaseModel):
    merchant_id: int | None = None
    name: str = Field(min_length=1, max_length=128)
    category: str = Field(default="饮品", min_length=1, max_length=64)
    price: Decimal
    is_active: bool = True


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
    merchant_id: int | None = None
    items: list[CheckoutLineIn] = Field(min_length=1)
    title: str | None = None
    member_id: int | None = None


class OrderLineOut(BaseModel):
    menu_item_id: int
    name: str
    unit_price: Decimal
    quantity: int
    line_amount: Decimal


def _require_catering_merchant(db: Session, ctx: RequestContext, merchant_id: int | None) -> tuple[int, Merchant]:
    mid = ctx.resolve_merchant_id(merchant_id)
    merchant = db.get(Merchant, mid)
    if merchant is None or merchant.site_id != ctx.site_id:
        raise AppError("not_found", "商户不存在", status_code=404)
    assert_merchant_has_system(db, mid, "catering")
    return mid, merchant


@router.get("/menu-items", response_model=list[MenuItemOut])
def list_menu_items(
    merchant_id: int | None = None,
    active_only: bool = False,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("catering:menu", "catering:order", "order:read")
    mid, _ = _require_catering_merchant(db, ctx, merchant_id)
    q = select(CateringMenuItem).where(CateringMenuItem.merchant_id == mid)
    if active_only:
        q = q.where(CateringMenuItem.is_active.is_(True))
    return list(db.scalars(q.order_by(CateringMenuItem.id.desc())).all())


@router.post("/menu-items", response_model=MenuItemOut)
def create_menu_item(
    body: MenuItemIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("catering:menu", "order:write")
    mid, _ = _require_catering_merchant(db, ctx, body.merchant_id)
    if body.price <= 0:
        raise AppError("validation_error", "菜品价格必须大于 0", status_code=422)
    row = CateringMenuItem(
        merchant_id=mid,
        name=body.name.strip(),
        category=body.category.strip() or "饮品",
        price=body.price,
        is_active=body.is_active,
    )
    db.add(row)
    db.flush()
    write_audit(
        db,
        action="catering.menu_create",
        target_type="catering_menu_item",
        target_id=row.id,
        summary=f"创建菜单 {row.name}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=mid,
    )
    db.commit()
    db.refresh(row)
    return row


@router.patch("/menu-items/{item_id}", response_model=MenuItemOut)
def update_menu_item(
    item_id: int,
    body: MenuItemIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("catering:menu", "order:write")
    mid, _ = _require_catering_merchant(db, ctx, body.merchant_id)
    row = db.get(CateringMenuItem, item_id)
    if row is None or row.merchant_id != mid:
        raise AppError("not_found", "菜单项不存在", status_code=404)
    if body.price <= 0:
        raise AppError("validation_error", "菜品价格必须大于 0", status_code=422)
    row.name = body.name.strip()
    row.category = body.category.strip() or "饮品"
    row.price = body.price
    row.is_active = body.is_active
    db.commit()
    db.refresh(row)
    return row


@router.post("/menu-items/{item_id}/deactivate", response_model=MenuItemOut)
def deactivate_menu_item(
    item_id: int,
    merchant_id: int | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("catering:menu", "order:write")
    mid, _ = _require_catering_merchant(db, ctx, merchant_id)
    row = db.get(CateringMenuItem, item_id)
    if row is None or row.merchant_id != mid:
        raise AppError("not_found", "菜单项不存在", status_code=404)
    row.is_active = False
    db.commit()
    db.refresh(row)
    return row


@router.post("/checkout", response_model=OrderOut)
def checkout(
    body: CheckoutIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """点单下单：生成 dining 订单（待支付），再走统一线下/线上收款。"""
    ctx.require_permission("catering:order", "order:write")
    mid, merchant = _require_catering_merchant(db, ctx, body.merchant_id)

    lines: list[tuple[CateringMenuItem, int]] = []
    total = Decimal("0")
    names: list[str] = []
    for line in body.items:
        item = db.get(CateringMenuItem, line.menu_item_id)
        if item is None or item.merchant_id != mid or not item.is_active:
            raise AppError("invalid_menu_item", f"菜单项不可用: {line.menu_item_id}", status_code=400)
        lines.append((item, line.quantity))
        total += item.price * line.quantity
        names.append(f"{item.name}×{line.quantity}")

    if total <= 0:
        raise AppError("validation_error", "订单金额必须大于 0", status_code=422)

    title = (body.title or "").strip() or f"{merchant.name}点单：{'、'.join(names[:3])}"
    order = Order(
        site_id=ctx.site_id,
        merchant_id=mid,
        member_id=body.member_id,
        order_type="dining",
        title=title[:255],
        amount=total,
        status=OrderStatus.PENDING.value,
    )
    db.add(order)
    db.flush()
    for item, qty in lines:
        line_amount = item.price * qty
        db.add(
            CateringOrderItem(
                order_id=order.id,
                menu_item_id=item.id,
                name_snapshot=item.name,
                unit_price=item.price,
                quantity=qty,
                line_amount=line_amount,
            )
        )
    write_audit(
        db,
        action="catering.checkout",
        target_type="order",
        target_id=order.id,
        summary=f"餐饮点单 ¥{total}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=mid,
    )
    db.commit()
    db.refresh(order)
    return order


@router.get("/orders/{order_id}/items", response_model=list[OrderLineOut])
def order_items(
    order_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("catering:order", "order:read")
    order = db.get(Order, order_id)
    if order is None or order.site_id != ctx.site_id:
        raise AppError("not_found", "订单不存在", status_code=404)
    if not ctx.is_site_admin and order.merchant_id != ctx.merchant_id:
        raise AppError("forbidden", "禁止跨商户访问", status_code=403)
    rows = list(db.scalars(select(CateringOrderItem).where(CateringOrderItem.order_id == order_id)).all())
    return [
        OrderLineOut(
            menu_item_id=r.menu_item_id,
            name=r.name_snapshot,
            unit_price=r.unit_price,
            quantity=r.quantity,
            line_amount=r.line_amount,
        )
        for r in rows
    ]
