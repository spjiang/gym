"""零售分类、SKU、库存与收银 API。"""

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import RequestContext, get_current_context
from app.domain.subsystems import assert_merchant_has_system
from app.errors import AppError
from app.models.commerce import Order, OrderStatus
from app.models.member import Member
from app.models.retail import ProductCategory, RetailOrderItem, RetailOrderLink, RetailSku, StockMovement
from app.schemas.common import OrderOut
from app.services.audit import write_audit
from app.services.retail_stock import stock_adjust, stock_in, stock_out
from app.services.coupon import attach_coupon_to_order
from app.services.pricing import effective_price

router = APIRouter(prefix="/retail", tags=["retail"])


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CategoryIn(BaseModel):
    merchant_id: int | None = None
    name: str
    sort_order: int = 0


class CategoryOut(ORMModel):
    id: int
    merchant_id: int
    name: str
    sort_order: int
    is_active: bool


class SkuIn(BaseModel):
    merchant_id: int | None = None
    category_id: int | None = None
    name: str
    price: Decimal
    unit: str = "件"
    barcode: str | None = None
    low_stock_threshold: int = 0
    is_active: bool = True
    promo_price: Decimal | None = None
    promo_starts_at: datetime | None = None
    promo_ends_at: datetime | None = None


class SkuOut(ORMModel):
    id: int
    merchant_id: int
    category_id: int | None
    name: str
    price: Decimal
    unit: str
    barcode: str | None
    stock_qty: int
    low_stock_threshold: int
    is_active: bool
    promo_price: Decimal | None = None
    promo_starts_at: datetime | None = None
    promo_ends_at: datetime | None = None
    effective_price: Decimal | None = None


class StockInBody(BaseModel):
    quantity: int = Field(gt=0)
    note: str | None = None


class StockOutBody(BaseModel):
    quantity: int = Field(gt=0)
    note: str | None = None


class StockAdjustBody(BaseModel):
    target_qty: int = Field(ge=0)
    note: str | None = None


class MovementOut(ORMModel):
    id: int
    sku_id: int
    movement_type: str
    quantity_delta: int
    stock_after: int
    order_id: int | None
    note: str | None
    created_at: datetime


class RetailLineIn(BaseModel):
    sku_id: int
    quantity: int = Field(gt=0)


class RetailOrderIn(BaseModel):
    merchant_id: int | None = None
    member_id: int | None = None
    items: list[RetailLineIn]
    member_coupon_id: int | None = None


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(
    merchant_id: int | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("retail:read", "retail:manage", "retail:sell")
    mid = ctx.resolve_merchant_id(merchant_id)
    return list(
        db.scalars(
            select(ProductCategory)
            .where(ProductCategory.merchant_id == mid)
            .order_by(ProductCategory.sort_order, ProductCategory.id)
        ).all()
    )


@router.post("/categories", response_model=CategoryOut)
def create_category(
    body: CategoryIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("retail:manage")
    mid = ctx.resolve_merchant_id(body.merchant_id)
    assert_merchant_has_system(db, mid, "gym")
    cat = ProductCategory(merchant_id=mid, name=body.name, sort_order=body.sort_order, is_active=True)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@router.get("/skus", response_model=list[SkuOut])
def list_skus(
    merchant_id: int | None = None,
    low_stock: bool = Query(False),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("retail:read", "retail:manage", "retail:sell")
    mid = ctx.resolve_merchant_id(merchant_id)
    q = select(RetailSku).where(RetailSku.merchant_id == mid)
    rows = list(db.scalars(q.order_by(RetailSku.id.desc())).all())
    if low_stock:
        rows = [s for s in rows if s.stock_qty <= s.low_stock_threshold]
    return rows


@router.post("/skus", response_model=SkuOut)
def create_sku(
    body: SkuIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("retail:manage")
    mid = ctx.resolve_merchant_id(body.merchant_id)
    assert_merchant_has_system(db, mid, "gym")
    if body.category_id is not None:
        cat = db.get(ProductCategory, body.category_id)
        if cat is None or cat.merchant_id != mid:
            raise AppError("invalid_category", "分类无效", status_code=400)
    sku = RetailSku(
        merchant_id=mid,
        category_id=body.category_id,
        name=body.name,
        price=body.price,
        unit=body.unit,
        barcode=body.barcode,
        stock_qty=0,
        low_stock_threshold=body.low_stock_threshold,
        is_active=body.is_active,
        promo_price=body.promo_price,
        promo_starts_at=body.promo_starts_at,
        promo_ends_at=body.promo_ends_at,
    )
    db.add(sku)
    db.flush()
    write_audit(
        db,
        action="retail.sku_create",
        target_type="retail_sku",
        target_id=sku.id,
        summary=f"创建 SKU {sku.name}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=mid,
    )
    db.commit()
    db.refresh(sku)
    return sku


@router.post("/skus/{sku_id}/deactivate", response_model=SkuOut)
def deactivate_sku(
    sku_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("retail:manage")
    sku = db.get(RetailSku, sku_id)
    if sku is None:
        raise AppError("not_found", "SKU 不存在", status_code=404)
    ctx.resolve_merchant_id(sku.merchant_id)
    sku.is_active = False
    db.commit()
    db.refresh(sku)
    return sku


@router.post("/skus/{sku_id}/stock/in", response_model=SkuOut)
def sku_stock_in(
    sku_id: int,
    body: StockInBody,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("retail:manage")
    sku = db.get(RetailSku, sku_id)
    if sku is None:
        raise AppError("not_found", "SKU 不存在", status_code=404)
    ctx.resolve_merchant_id(sku.merchant_id)
    stock_in(db, sku_id, body.quantity, note=body.note, actor_staff_id=ctx.staff.id)
    db.commit()
    db.refresh(sku)
    return sku


@router.post("/skus/{sku_id}/stock/out", response_model=SkuOut)
def sku_stock_out(
    sku_id: int,
    body: StockOutBody,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("retail:manage")
    sku = db.get(RetailSku, sku_id)
    if sku is None:
        raise AppError("not_found", "SKU 不存在", status_code=404)
    ctx.resolve_merchant_id(sku.merchant_id)
    stock_out(db, sku_id, body.quantity, note=body.note, actor_staff_id=ctx.staff.id)
    db.commit()
    db.refresh(sku)
    return sku


@router.post("/skus/{sku_id}/stock/adjust", response_model=SkuOut)
def sku_stock_adjust(
    sku_id: int,
    body: StockAdjustBody,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("retail:manage")
    sku = db.get(RetailSku, sku_id)
    if sku is None:
        raise AppError("not_found", "SKU 不存在", status_code=404)
    ctx.resolve_merchant_id(sku.merchant_id)
    stock_adjust(db, sku_id, body.target_qty, note=body.note, actor_staff_id=ctx.staff.id)
    db.commit()
    db.refresh(sku)
    return sku


@router.get("/movements", response_model=list[MovementOut])
def list_movements(
    merchant_id: int | None = None,
    sku_id: int | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("retail:read", "retail:manage")
    mid = ctx.resolve_merchant_id(merchant_id)
    q = select(StockMovement).where(StockMovement.merchant_id == mid)
    if sku_id is not None:
        q = q.where(StockMovement.sku_id == sku_id)
    return list(db.scalars(q.order_by(StockMovement.id.desc()).limit(200)).all())


@router.post("/orders", response_model=OrderOut)
def create_retail_order(
    body: RetailOrderIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("retail:sell", "retail:manage")
    mid = ctx.resolve_merchant_id(body.merchant_id)
    assert_merchant_has_system(db, mid, "gym")
    if not body.items:
        raise AppError("empty_order", "请至少添加一行商品", status_code=400)
    if body.member_id is not None:
        member = db.get(Member, body.member_id)
        if member is None or member.site_id != ctx.site_id:
            raise AppError("not_found", "会员不存在", status_code=404)

    total = Decimal("0")
    resolved: list[tuple[RetailSku, int, Decimal]] = []
    for line in body.items:
        sku = db.get(RetailSku, line.sku_id)
        if sku is None or sku.merchant_id != mid:
            raise AppError("not_found", "商品不存在", status_code=404)
        if not sku.is_active:
            raise AppError("sku_inactive", f"商品已停用: {sku.name}", status_code=400)
        if sku.stock_qty < line.quantity:
            raise AppError(
                "insufficient_stock",
                f"库存不足: {sku.name}",
                status_code=400,
            )
        price = effective_price(sku.price, sku.promo_price, sku.promo_starts_at, sku.promo_ends_at)
        total += price * line.quantity
        resolved.append((sku, line.quantity, price))

    order = Order(
        site_id=ctx.site_id,
        merchant_id=mid,
        member_id=body.member_id,
        order_type="retail",
        title="零售收银",
        amount=total,
        status=OrderStatus.PENDING.value,
    )
    db.add(order)
    db.flush()
    if body.member_coupon_id is not None:
        ctx.require_permission("coupon:redeem", "coupon:manage", "retail:sell", "retail:manage")
        payable = attach_coupon_to_order(
            db,
            order=order,
            member_coupon_id=body.member_coupon_id,
            original_amount=total,
            member_id=body.member_id,
        )
        order.amount = payable
    link = RetailOrderLink(order_id=order.id, member_id=body.member_id, fulfilled=False)
    db.add(link)
    db.flush()
    for sku, qty, price in resolved:
        db.add(
            RetailOrderItem(
                order_link_id=link.id,
                sku_id=sku.id,
                quantity=qty,
                unit_price=price,
            )
        )
    write_audit(
        db,
        action="retail.order_create",
        target_type="order",
        target_id=order.id,
        summary=f"零售下单 lines={len(resolved)} amount={total}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=mid,
    )
    db.commit()
    db.refresh(order)
    return order
