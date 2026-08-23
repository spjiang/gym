"""零售分类、SKU、库存与收银 API。"""

import re
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
from app.core.schemas.common import OrderOut
from app.core.schemas.paging import PageOut, paginate
from app.systems.platform.models.commerce import Order, OrderStatus
from app.systems.platform.models.identity import StaffUser
from app.systems.platform.models.member import Member
from app.systems.gym.models.retail import ProductCategory, RetailOrderItem, RetailOrderLink, RetailSku, StockMovement
from app.systems.platform.services.audit import write_audit
from app.systems.gym.services.retail_stock import stock_adjust, stock_in, stock_out
from app.systems.gym.services.pricing import effective_price
from app.systems.platform.services.order_pricing import price_order

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
    remark: str | None = Field(default=None, max_length=500)
    image_urls: list[str] = Field(default_factory=list)


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
    remark: str | None = None
    image_urls: list[str] = Field(default_factory=list)


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
    actor_name: str | None = None


class RetailLineIn(BaseModel):
    sku_id: int
    quantity: int = Field(gt=0)


class RetailOrderIn(BaseModel):
    merchant_id: int | None = None
    member_id: int | None = None
    items: list[RetailLineIn]
    member_coupon_id: int | None = None


@router.get("/categories", response_model=PageOut[CategoryOut])
def list_categories(
    merchant_id: int | None = None,
    q: str | None = None,
    is_active: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("retail:read", "retail:manage", "retail:sell")
    mid = ctx.resolve_merchant_id(merchant_id, required=False)
    stmt = select(ProductCategory)
    if mid is not None:
        stmt = stmt.where(ProductCategory.merchant_id == mid)
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        conds = [ProductCategory.name.ilike(like)]
        if keyword.isdigit():
            conds.append(ProductCategory.id == int(keyword))
        stmt = stmt.where(or_(*conds))
    if is_active is not None:
        stmt = stmt.where(ProductCategory.is_active.is_(is_active))
    rows, total = paginate(
        db,
        stmt.order_by(ProductCategory.sort_order, ProductCategory.id),
        page=page,
        page_size=page_size,
    )
    return PageOut(items=rows, total=total, page=page, page_size=page_size)


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


@router.patch("/categories/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: int,
    body: CategoryIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("retail:manage")
    cat = db.get(ProductCategory, category_id)
    if cat is None:
        raise AppError("not_found", "分类不存在", status_code=404)
    mid = ctx.resolve_merchant_id(body.merchant_id or cat.merchant_id)
    if cat.merchant_id != mid:
        raise AppError("forbidden", "禁止跨商户修改", status_code=403)
    cat.name = body.name.strip()
    cat.sort_order = body.sort_order
    db.commit()
    db.refresh(cat)
    return cat


_SKU_IMAGE_URL_RE = re.compile(r"^/api/v1/files/[0-9a-f]{32}\.(jpg|png|webp)$")
_MAX_SKU_IMAGES = 9


def _normalize_remark(value: str | None) -> str | None:
    text = (value or "").strip()
    return text or None


def _normalize_image_urls(urls: list[str] | None) -> list[str]:
    """只接受本系统已上传的图片地址，去重且最多 9 张。"""
    out: list[str] = []
    for raw in urls or []:
        url = (raw or "").strip()
        if not url:
            continue
        if not _SKU_IMAGE_URL_RE.match(url):
            raise AppError("invalid_image", "图片地址无效，请通过系统上传", status_code=400)
        if url not in out:
            out.append(url)
    if len(out) > _MAX_SKU_IMAGES:
        raise AppError("too_many_images", "最多上传 9 张图片", status_code=400)
    return out


def _sku_out(s: RetailSku) -> SkuOut:
    return SkuOut(
        id=s.id,
        merchant_id=s.merchant_id,
        category_id=s.category_id,
        name=s.name,
        price=s.price,
        unit=s.unit,
        barcode=s.barcode,
        stock_qty=s.stock_qty,
        low_stock_threshold=s.low_stock_threshold,
        is_active=s.is_active,
        promo_price=s.promo_price,
        promo_starts_at=s.promo_starts_at,
        promo_ends_at=s.promo_ends_at,
        effective_price=effective_price(s.price, s.promo_price, s.promo_starts_at, s.promo_ends_at),
        remark=s.remark,
        image_urls=list(s.image_urls or []),
    )


@router.get("/skus", response_model=PageOut[SkuOut])
def list_skus(
    merchant_id: int | None = None,
    q: str | None = None,
    category_id: int | None = None,
    is_active: bool | None = None,
    low_stock: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("retail:read", "retail:manage", "retail:sell")
    mid = ctx.resolve_merchant_id(merchant_id, required=False)
    stmt = select(RetailSku)
    if mid is not None:
        stmt = stmt.where(RetailSku.merchant_id == mid)
    if category_id is not None:
        stmt = stmt.where(RetailSku.category_id == category_id)
    if is_active is not None:
        stmt = stmt.where(RetailSku.is_active.is_(is_active))
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(RetailSku.name.ilike(like), RetailSku.barcode.ilike(like)))
    if low_stock:
        stmt = stmt.where(RetailSku.stock_qty <= RetailSku.low_stock_threshold)
    rows, total = paginate(db, stmt.order_by(RetailSku.id.desc()), page=page, page_size=page_size)
    return PageOut(items=[_sku_out(s) for s in rows], total=total, page=page, page_size=page_size)


@router.get("/skus/{sku_id}", response_model=SkuOut)
def get_sku(
    sku_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("retail:read", "retail:manage", "retail:sell")
    sku = db.get(RetailSku, sku_id)
    if sku is None:
        raise AppError("not_found", "商品不存在", status_code=404)
    ctx.resolve_merchant_id(sku.merchant_id)
    return _sku_out(sku)


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
        name=body.name.strip(),
        price=body.price,
        unit=body.unit,
        barcode=body.barcode,
        stock_qty=0,
        low_stock_threshold=body.low_stock_threshold,
        is_active=body.is_active,
        promo_price=body.promo_price,
        promo_starts_at=body.promo_starts_at,
        promo_ends_at=body.promo_ends_at,
        remark=_normalize_remark(body.remark),
        image_urls=_normalize_image_urls(body.image_urls),
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
    return _sku_out(sku)


@router.patch("/skus/{sku_id}", response_model=SkuOut)
def update_sku(
    sku_id: int,
    body: SkuIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("retail:manage")
    sku = db.get(RetailSku, sku_id)
    if sku is None:
        raise AppError("not_found", "SKU 不存在", status_code=404)
    mid = ctx.resolve_merchant_id(body.merchant_id or sku.merchant_id)
    if sku.merchant_id != mid:
        raise AppError("forbidden", "禁止跨商户修改", status_code=403)
    if body.category_id is not None:
        cat = db.get(ProductCategory, body.category_id)
        if cat is None or cat.merchant_id != mid:
            raise AppError("invalid_category", "分类无效", status_code=400)
    sku.category_id = body.category_id
    sku.name = body.name.strip()
    sku.price = body.price
    sku.unit = body.unit
    sku.barcode = body.barcode
    sku.low_stock_threshold = body.low_stock_threshold
    sku.is_active = body.is_active
    sku.promo_price = body.promo_price
    sku.promo_starts_at = body.promo_starts_at
    sku.promo_ends_at = body.promo_ends_at
    sku.remark = _normalize_remark(body.remark)
    sku.image_urls = _normalize_image_urls(body.image_urls)
    db.commit()
    db.refresh(sku)
    return _sku_out(sku)


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


@router.get("/movements", response_model=PageOut[MovementOut])
def list_movements(
    merchant_id: int | None = None,
    sku_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("retail:read", "retail:manage", "retail:sell")
    mid = ctx.resolve_merchant_id(merchant_id, required=False)
    filters = [StockMovement.merchant_id == mid] if mid is not None else []
    if sku_id is not None:
        filters.append(StockMovement.sku_id == sku_id)
    base = select(StockMovement)
    if filters:
        base = base.where(*filters)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = list(
        db.scalars(
            base
            .order_by(StockMovement.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    staff_ids = {r.actor_staff_id for r in rows if r.actor_staff_id}
    names: dict[int, str] = {}
    if staff_ids:
        staff_rows = list(db.scalars(select(StaffUser).where(StaffUser.id.in_(staff_ids))).all())
        names = {s.id: s.display_name for s in staff_rows}
    items = [
        MovementOut(
            id=r.id,
            sku_id=r.sku_id,
            movement_type=r.movement_type,
            quantity_delta=r.quantity_delta,
            stock_after=r.stock_after,
            order_id=r.order_id,
            note=r.note,
            created_at=r.created_at,
            actor_name=names.get(r.actor_staff_id) if r.actor_staff_id else None,
        )
        for r in rows
    ]
    return PageOut(items=items, total=total, page=page, page_size=page_size)


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
        seller_staff_id=ctx.staff.id,
    )
    db.add(order)
    db.flush()
    if body.member_coupon_id is not None:
        ctx.require_permission("coupon:redeem", "coupon:manage", "retail:sell", "retail:manage")
    price_order(db, order=order, original_amount=total, member_coupon_id=body.member_coupon_id)
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
