"""餐饮管理：菜单维护 + 点单收款闭环。"""

import re
from collections import defaultdict
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, field_serializer
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import RequestContext, get_current_context
from app.core.domain.subsystems import assert_merchant_has_system
from app.core.errors import AppError
from app.core.schemas.paging import PageOut, paginate
from app.systems.catering.models.catering import CateringMenuCategory, CateringMenuItem, CateringOrderItem, CateringTable
from app.systems.catering.services.kitchen import DiningStatus
from app.systems.catering.services.tables import dining_order_url, generate_table_code, split_dining_note
from app.systems.platform.models.commerce import Order, OrderStatus
from app.systems.platform.models.member import Member
from app.systems.platform.models.org import Merchant
from app.core.schemas.common import OrderOut
from app.systems.platform.services.audit import write_audit
from app.systems.platform.services.order_pricing import price_order

router = APIRouter(prefix="/catering", tags=["catering"])

_MENU_IMAGE_RE = re.compile(r"^/api/v1/files/[0-9a-f]{32}\.(jpg|png|webp)$")


def _blank(value: str | None) -> str | None:
    text = (value or "").strip()
    return text or None


def _normalize_menu_image(url: str | None) -> str | None:
    text = _blank(url)
    if text is None:
        return None
    if not _MENU_IMAGE_RE.match(text):
        raise AppError("invalid_image", "菜品图片地址无效，请通过系统上传", status_code=400)
    return text


class CategoryIn(BaseModel):
    merchant_id: int | None = None
    name: str = Field(min_length=1, max_length=64)
    sort_order: int = 0
    is_active: bool | None = None


class CategoryOut(BaseModel):
    id: int
    merchant_id: int
    name: str
    sort_order: int
    is_active: bool

    model_config = {"from_attributes": True}


class MenuItemIn(BaseModel):
    merchant_id: int | None = None
    name: str = Field(min_length=1, max_length=128)
    category: str | None = Field(default=None, max_length=64)
    category_id: int | None = None
    price: Decimal
    image_url: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=255)
    is_active: bool = True


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
    merchant_id: int | None = None
    items: list[CheckoutLineIn] = Field(min_length=1)
    title: str | None = None
    member_id: int | None = None
    table_no: str | None = None
    note: str | None = None


class OrderLineOut(BaseModel):
    menu_item_id: int
    name: str
    unit_price: Decimal
    quantity: int
    line_amount: Decimal


class KitchenTicketOut(BaseModel):
    """厨房看板工单：已支付且尚未完成的餐饮单。"""

    id: int
    merchant_id: int
    pickup_code: str | None = None
    dining_status: str
    amount: Decimal
    title: str
    table_no: str | None = None
    customer_note: str | None = None
    member_name: str | None = None
    created_at: datetime
    items: list[OrderLineOut] = Field(default_factory=list)

    @field_serializer("amount")
    def _money(self, value: Decimal) -> Decimal:
        return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


_KITCHEN_STATUSES = {DiningStatus.PREPARING.value, DiningStatus.READY.value}


class TableIn(BaseModel):
    merchant_id: int | None = None
    name: str = Field(min_length=1, max_length=32)
    sort_order: int = 0
    is_active: bool = True


class TablePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=32)
    sort_order: int | None = None
    is_active: bool | None = None


class TableOut(BaseModel):
    id: int
    merchant_id: int
    name: str
    code: str
    sort_order: int
    is_active: bool
    order_url: str

    model_config = {"from_attributes": True}


def _table_out(row: CateringTable) -> TableOut:
    return TableOut(
        id=row.id,
        merchant_id=row.merchant_id,
        name=row.name,
        code=row.code,
        sort_order=row.sort_order,
        is_active=row.is_active,
        order_url=dining_order_url(merchant_id=row.merchant_id, code=row.code),
    )


def _require_catering_merchant(db: Session, ctx: RequestContext, merchant_id: int | None) -> tuple[int, Merchant]:
    mid = ctx.resolve_merchant_id(merchant_id)
    merchant = db.get(Merchant, mid)
    if merchant is None or merchant.site_id != ctx.site_id:
        raise AppError("not_found", "商户不存在", status_code=404)
    assert_merchant_has_system(db, mid, "catering")
    return mid, merchant


def _resolve_menu_category(
    db: Session,
    merchant_id: int,
    *,
    category_id: int | None,
    category: str | None,
    require_active: bool = False,
) -> CateringMenuCategory:
    """按 id 或名称解析分类；名称不存在时自动创建，避免旧接口中断。"""
    if category_id is not None:
        cat = db.get(CateringMenuCategory, category_id)
        if cat is None or cat.merchant_id != merchant_id:
            raise AppError("invalid_category", "分类无效", status_code=400)
        if require_active and not cat.is_active:
            raise AppError("invalid_category", "分类已停用", status_code=400)
        return cat
    name = (category or "").strip() or "饮品"
    existing = db.scalar(
        select(CateringMenuCategory).where(
            CateringMenuCategory.merchant_id == merchant_id,
            CateringMenuCategory.name == name,
        )
    )
    if existing is not None:
        return existing
    max_sort = db.scalar(
        select(func.max(CateringMenuCategory.sort_order)).where(CateringMenuCategory.merchant_id == merchant_id)
    )
    cat = CateringMenuCategory(
        merchant_id=merchant_id,
        name=name,
        sort_order=(max_sort or 0) + 10,
        is_active=True,
    )
    db.add(cat)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise AppError("conflict", "该分类已存在", status_code=409) from exc
    return cat


@router.get("/categories", response_model=PageOut[CategoryOut])
def list_categories(
    merchant_id: int | None = None,
    q: str | None = None,
    is_active: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("catering:menu", "catering:order", "order:read")
    mid = ctx.resolve_merchant_id(merchant_id, required=False)
    stmt = select(CateringMenuCategory)
    if mid is not None:
        _require_catering_merchant(db, ctx, mid)
        stmt = stmt.where(CateringMenuCategory.merchant_id == mid)
    else:
        stmt = stmt.join(Merchant, Merchant.id == CateringMenuCategory.merchant_id).where(Merchant.site_id == ctx.site_id)
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        conds = [CateringMenuCategory.name.ilike(like)]
        if keyword.isdigit():
            conds.append(CateringMenuCategory.id == int(keyword))
        stmt = stmt.where(or_(*conds))
    if is_active is not None:
        stmt = stmt.where(CateringMenuCategory.is_active.is_(is_active))
    rows, total = paginate(
        db,
        stmt.order_by(CateringMenuCategory.sort_order.asc(), CateringMenuCategory.id.asc()),
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
    ctx.require_permission("catering:menu", "order:write")
    mid, _ = _require_catering_merchant(db, ctx, body.merchant_id)
    name = body.name.strip()
    if not name:
        raise AppError("validation_error", "请填写分类名称", status_code=422)
    row = CateringMenuCategory(
        merchant_id=mid,
        name=name,
        sort_order=body.sort_order,
        is_active=True,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise AppError("conflict", "该分类已存在", status_code=409) from exc
    write_audit(
        db,
        action="catering.category_create",
        target_type="catering_menu_category",
        target_id=row.id,
        summary=f"创建菜单分类 {row.name}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=mid,
    )
    db.commit()
    db.refresh(row)
    return row


@router.patch("/categories/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: int,
    body: CategoryIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("catering:menu", "order:write")
    mid, _ = _require_catering_merchant(db, ctx, body.merchant_id)
    row = db.get(CateringMenuCategory, category_id)
    if row is None or row.merchant_id != mid:
        raise AppError("not_found", "分类不存在", status_code=404)
    name = body.name.strip()
    if not name:
        raise AppError("validation_error", "请填写分类名称", status_code=422)
    row.name = name
    row.sort_order = body.sort_order
    if body.is_active is not None:
        row.is_active = body.is_active
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise AppError("conflict", "该分类已存在", status_code=409) from exc
    for item in db.scalars(
        select(CateringMenuItem).where(CateringMenuItem.category_id == row.id)
    ).all():
        item.category = row.name
    write_audit(
        db,
        action="catering.category_update",
        target_type="catering_menu_category",
        target_id=row.id,
        summary=f"更新菜单分类 {row.name}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=mid,
    )
    db.commit()
    db.refresh(row)
    return row


@router.post("/categories/{category_id}/deactivate", response_model=CategoryOut)
def deactivate_category(
    category_id: int,
    merchant_id: int | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("catering:menu", "order:write")
    mid, _ = _require_catering_merchant(db, ctx, merchant_id)
    row = db.get(CateringMenuCategory, category_id)
    if row is None or row.merchant_id != mid:
        raise AppError("not_found", "分类不存在", status_code=404)
    row.is_active = False
    db.commit()
    db.refresh(row)
    return row


@router.get("/menu-items", response_model=PageOut[MenuItemOut])
def list_menu_items(
    merchant_id: int | None = None,
    active_only: bool = False,
    q: str | None = None,
    category: str | None = None,
    category_id: int | None = None,
    is_active: bool | None = None,
    price_min: Decimal | None = None,
    price_max: Decimal | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("catering:menu", "catering:order", "order:read")
    mid = ctx.resolve_merchant_id(merchant_id, required=False)
    stmt = select(CateringMenuItem)
    if mid is not None:
        _require_catering_merchant(db, ctx, mid)
        stmt = stmt.where(CateringMenuItem.merchant_id == mid)
    else:
        stmt = stmt.join(Merchant, Merchant.id == CateringMenuItem.merchant_id).where(Merchant.site_id == ctx.site_id)
    if is_active is not None:
        stmt = stmt.where(CateringMenuItem.is_active.is_(is_active))
    elif active_only:
        stmt = stmt.where(CateringMenuItem.is_active.is_(True))
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        conds = [CateringMenuItem.name.ilike(like)]
        if keyword.isdigit():
            conds.append(CateringMenuItem.id == int(keyword))
        stmt = stmt.where(or_(*conds))
    if category_id is not None:
        stmt = stmt.where(CateringMenuItem.category_id == category_id)
    elif category:
        stmt = stmt.where(CateringMenuItem.category.ilike(f"%{category.strip()}%"))
    if price_min is not None:
        stmt = stmt.where(CateringMenuItem.price >= price_min)
    if price_max is not None:
        stmt = stmt.where(CateringMenuItem.price <= price_max)
    rows, total = paginate(db, stmt.order_by(CateringMenuItem.id.desc()), page=page, page_size=page_size)
    return PageOut(items=rows, total=total, page=page, page_size=page_size)


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
    cat = _resolve_menu_category(
        db,
        mid,
        category_id=body.category_id,
        category=body.category,
        require_active=body.category_id is not None,
    )
    row = CateringMenuItem(
        merchant_id=mid,
        name=body.name.strip(),
        category_id=cat.id,
        category=cat.name,
        price=body.price,
        image_url=_normalize_menu_image(body.image_url),
        description=_blank(body.description),
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
    if body.category_id is not None or (body.category or "").strip():
        cat = _resolve_menu_category(
            db,
            mid,
            category_id=body.category_id,
            category=body.category,
        )
    else:
        cat = _resolve_menu_category(
            db,
            mid,
            category_id=row.category_id,
            category=row.category,
        )
    row.name = body.name.strip()
    row.category_id = cat.id
    row.category = cat.name
    row.price = body.price
    row.image_url = _normalize_menu_image(body.image_url)
    row.description = _blank(body.description)
    row.is_active = body.is_active
    write_audit(
        db,
        action="catering.menu_update",
        target_type="catering_menu_item",
        target_id=row.id,
        summary=f"编辑菜单 {row.name}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=mid,
    )
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


@router.get("/tables", response_model=PageOut[TableOut])
def list_tables(
    merchant_id: int | None = None,
    active_only: bool = False,
    q: str | None = None,
    is_active: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("catering:menu", "catering:order")
    mid = ctx.resolve_merchant_id(merchant_id, required=False)
    stmt = select(CateringTable)
    if mid is not None:
        _require_catering_merchant(db, ctx, mid)
        stmt = stmt.where(CateringTable.merchant_id == mid)
    else:
        stmt = stmt.join(Merchant, Merchant.id == CateringTable.merchant_id).where(Merchant.site_id == ctx.site_id)
    if is_active is not None:
        stmt = stmt.where(CateringTable.is_active.is_(is_active))
    elif active_only:
        stmt = stmt.where(CateringTable.is_active.is_(True))
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        conds = [CateringTable.name.ilike(like), CateringTable.code.ilike(like)]
        if keyword.isdigit():
            conds.append(CateringTable.id == int(keyword))
        stmt = stmt.where(or_(*conds))
    rows, total = paginate(
        db,
        stmt.order_by(CateringTable.sort_order.asc(), CateringTable.id.asc()),
        page=page,
        page_size=page_size,
    )
    return PageOut(items=[_table_out(row) for row in rows], total=total, page=page, page_size=page_size)


@router.post("/tables", response_model=TableOut)
def create_table(
    body: TableIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("catering:menu")
    mid, _ = _require_catering_merchant(db, ctx, body.merchant_id)
    name = body.name.strip()
    if not name:
        raise AppError("validation_error", "请填写桌号", status_code=422)
    row = CateringTable(
        merchant_id=mid,
        name=name,
        code=generate_table_code(db),
        sort_order=body.sort_order,
        is_active=body.is_active,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise AppError("conflict", "该桌号已存在", status_code=409) from exc
    write_audit(
        db,
        action="catering.table_create",
        target_type="catering_table",
        target_id=row.id,
        summary=f"创建桌号 {row.name}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=mid,
    )
    db.commit()
    db.refresh(row)
    return _table_out(row)


@router.patch("/tables/{table_id}", response_model=TableOut)
def update_table(
    table_id: int,
    body: TablePatch,
    merchant_id: int | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("catering:menu")
    mid, _ = _require_catering_merchant(db, ctx, merchant_id)
    row = db.get(CateringTable, table_id)
    if row is None or row.merchant_id != mid:
        raise AppError("not_found", "桌号不存在", status_code=404)
    data = body.model_dump(exclude_unset=True)
    if "name" in data:
        name = (data["name"] or "").strip()
        if not name:
            raise AppError("validation_error", "请填写桌号", status_code=422)
        row.name = name
    if "sort_order" in data and data["sort_order"] is not None:
        row.sort_order = data["sort_order"]
    if "is_active" in data and data["is_active"] is not None:
        row.is_active = data["is_active"]
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise AppError("conflict", "该桌号已存在", status_code=409) from exc
    write_audit(
        db,
        action="catering.table_update",
        target_type="catering_table",
        target_id=row.id,
        summary=f"更新桌号 {row.name}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=mid,
    )
    db.commit()
    db.refresh(row)
    return _table_out(row)


@router.post("/tables/{table_id}/deactivate", response_model=TableOut)
def deactivate_table(
    table_id: int,
    merchant_id: int | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("catering:menu")
    row = db.get(CateringTable, table_id)
    if row is None:
        raise AppError("not_found", "桌号不存在", status_code=404)
    ctx.assert_merchant_access(row.merchant_id)
    _require_catering_merchant(db, ctx, row.merchant_id)
    if merchant_id is not None and merchant_id != row.merchant_id:
        raise AppError("forbidden", "禁止跨商户访问", status_code=403)
    row.is_active = False
    db.commit()
    db.refresh(row)
    return _table_out(row)


@router.get("/kitchen", response_model=list[KitchenTicketOut])
def list_kitchen(
    merchant_id: int | None = None,
    dining_status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """厨房看板：制作中 / 待取餐，按下单时间先进先出。"""
    ctx.require_permission("catering:order", "order:read")
    mid = ctx.resolve_merchant_id(merchant_id, required=False)
    status_filter = (dining_status or "").strip()
    if status_filter and status_filter not in _KITCHEN_STATUSES:
        raise AppError("validation_error", "制作进度仅支持 preparing / ready", status_code=422)

    stmt = select(Order).where(
        Order.site_id == ctx.site_id,
        Order.order_type == "dining",
        Order.status == OrderStatus.PAID.value,
    )
    if status_filter == DiningStatus.READY.value:
        stmt = stmt.where(Order.dining_status == DiningStatus.READY.value)
    elif status_filter == DiningStatus.PREPARING.value:
        stmt = stmt.where(
            or_(
                Order.dining_status == DiningStatus.PREPARING.value,
                Order.dining_status.is_(None),
            )
        )
    else:
        stmt = stmt.where(
            or_(
                Order.dining_status.in_(list(_KITCHEN_STATUSES)),
                Order.dining_status.is_(None),
            )
        )
    if mid is not None:
        _require_catering_merchant(db, ctx, mid)
        stmt = stmt.where(Order.merchant_id == mid)
    orders = list(db.scalars(stmt.order_by(Order.created_at.asc(), Order.id.asc())).all())
    if not orders:
        return []

    order_ids = [row.id for row in orders]
    lines = list(
        db.scalars(select(CateringOrderItem).where(CateringOrderItem.order_id.in_(order_ids))).all()
    )
    items_by_order: dict[int, list[CateringOrderItem]] = defaultdict(list)
    for line in lines:
        items_by_order[line.order_id].append(line)

    member_ids = [row.member_id for row in orders if row.member_id is not None]
    members = {
        m.id: m
        for m in db.scalars(select(Member).where(Member.id.in_(member_ids))).all()
    } if member_ids else {}

    tickets: list[KitchenTicketOut] = []
    for row in orders:
        member = members.get(row.member_id) if row.member_id else None
        table_no, remark = split_dining_note(row.customer_note)
        tickets.append(
            KitchenTicketOut(
                id=row.id,
                merchant_id=row.merchant_id,
                pickup_code=row.pickup_code,
                dining_status=row.dining_status or DiningStatus.PREPARING.value,
                amount=row.amount,
                title=row.title,
                table_no=table_no,
                customer_note=remark,
                member_name=member.name if member else None,
                created_at=row.created_at,
                items=[
                    OrderLineOut(
                        menu_item_id=it.menu_item_id,
                        name=it.name_snapshot,
                        unit_price=it.unit_price,
                        quantity=it.quantity,
                        line_amount=it.line_amount,
                    )
                    for it in items_by_order.get(row.id, [])
                ],
            )
        )
    return tickets


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
    from app.systems.catering.services.tables import compose_dining_note, require_active_table_label

    table_no = (body.table_no or "").strip() or None
    if table_no:
        require_active_table_label(db, merchant_id=mid, table_no=table_no)
    customer_note = compose_dining_note(table_no=table_no, note=body.note)
    order = Order(
        site_id=ctx.site_id,
        merchant_id=mid,
        member_id=body.member_id,
        order_type="dining",
        title=title[:255],
        amount=total,
        status=OrderStatus.PENDING.value,
        customer_note=customer_note,
    )
    db.add(order)
    db.flush()
    price_order(db, order=order, original_amount=total)
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


@router.post("/orders/{order_id}/ready", response_model=OrderOut)
def mark_order_ready(
    order_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """制作中 → 待取餐。"""
    ctx.require_permission("catering:order", "order:write")
    from app.systems.catering.services.kitchen import mark_dining_ready

    order = db.get(Order, order_id)
    if order is None or order.site_id != ctx.site_id:
        raise AppError("not_found", "订单不存在", status_code=404)
    ctx.assert_merchant_access(order.merchant_id)
    _require_catering_merchant(db, ctx, order.merchant_id)
    mark_dining_ready(db, order, actor_staff_id=ctx.staff.id)
    db.commit()
    db.refresh(order)
    return order


@router.post("/orders/{order_id}/complete", response_model=OrderOut)
def mark_order_complete(
    order_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """待取餐 → 已完成。"""
    ctx.require_permission("catering:order", "order:write")
    from app.systems.catering.services.kitchen import mark_dining_completed

    order = db.get(Order, order_id)
    if order is None or order.site_id != ctx.site_id:
        raise AppError("not_found", "订单不存在", status_code=404)
    ctx.assert_merchant_access(order.merchant_id)
    _require_catering_merchant(db, ctx, order.merchant_id)
    mark_dining_completed(db, order, actor_staff_id=ctx.staff.id)
    db.commit()
    db.refresh(order)
    return order


@router.post("/orders/{order_id}/undo", response_model=OrderOut)
def undo_kitchen_status(
    order_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """厨房纠错：待取餐退回制作中，已完成退回待取餐。"""
    ctx.require_permission("catering:order", "order:write")
    from app.systems.catering.services.kitchen import undo_dining_status

    order = db.get(Order, order_id)
    if order is None or order.site_id != ctx.site_id:
        raise AppError("not_found", "订单不存在", status_code=404)
    ctx.assert_merchant_access(order.merchant_id)
    _require_catering_merchant(db, ctx, order.merchant_id)
    undo_dining_status(db, order, actor_staff_id=ctx.staff.id)
    db.commit()
    db.refresh(order)
    return order


@router.post("/orders/{order_id}/cancel", response_model=OrderOut)
def cancel_pending_order(
    order_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """吧台取消待支付餐饮单。"""
    ctx.require_permission("catering:order", "order:write")
    from app.systems.catering.services.kitchen import cancel_pending_dining_order

    order = db.get(Order, order_id)
    if order is None or order.site_id != ctx.site_id:
        raise AppError("not_found", "订单不存在", status_code=404)
    ctx.assert_merchant_access(order.merchant_id)
    _require_catering_merchant(db, ctx, order.merchant_id)
    cancel_pending_dining_order(db, order, actor_staff_id=ctx.staff.id)
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
    ctx.assert_merchant_access(order.merchant_id)
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
