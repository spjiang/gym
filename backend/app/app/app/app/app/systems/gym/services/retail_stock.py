"""库存变更：入库、出库、盘点。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.systems.gym.models.retail import RetailSku, StockMovement, StockMovementType
from app.systems.platform.services.audit import write_audit


def _lock_sku(db: Session, sku_id: int) -> RetailSku:
    sku = db.scalar(select(RetailSku).where(RetailSku.id == sku_id).with_for_update())
    if sku is None:
        raise AppError("not_found", "SKU 不存在", status_code=404)
    return sku


def apply_stock_delta(
    db: Session,
    sku: RetailSku,
    *,
    delta: int,
    movement_type: str,
    note: str | None = None,
    order_id: int | None = None,
    actor_staff_id: int | None = None,
) -> RetailSku:
    new_qty = sku.stock_qty + delta
    if new_qty < 0:
        raise AppError("insufficient_stock", "库存不足", status_code=400)
    sku.stock_qty = new_qty
    db.add(
        StockMovement(
            merchant_id=sku.merchant_id,
            sku_id=sku.id,
            movement_type=movement_type,
            quantity_delta=delta,
            stock_after=new_qty,
            order_id=order_id,
            note=note,
            actor_staff_id=actor_staff_id,
        )
    )
    return sku


def stock_in(
    db: Session,
    sku_id: int,
    quantity: int,
    *,
    note: str | None = None,
    actor_staff_id: int | None = None,
) -> RetailSku:
    if quantity <= 0:
        raise AppError("invalid_qty", "入库数量必须为正整数", status_code=400)
    sku = _lock_sku(db, sku_id)
    apply_stock_delta(
        db,
        sku,
        delta=quantity,
        movement_type=StockMovementType.IN.value,
        note=note,
        actor_staff_id=actor_staff_id,
    )
    write_audit(
        db,
        action="retail.stock_in",
        target_type="retail_sku",
        target_id=sku.id,
        summary=f"入库 +{quantity}",
        actor_staff_id=actor_staff_id,
        merchant_id=sku.merchant_id,
    )
    return sku


def stock_out(
    db: Session,
    sku_id: int,
    quantity: int,
    *,
    note: str | None = None,
    actor_staff_id: int | None = None,
) -> RetailSku:
    if quantity <= 0:
        raise AppError("invalid_qty", "出库数量必须为正整数", status_code=400)
    sku = _lock_sku(db, sku_id)
    apply_stock_delta(
        db,
        sku,
        delta=-quantity,
        movement_type=StockMovementType.OUT.value,
        note=note,
        actor_staff_id=actor_staff_id,
    )
    write_audit(
        db,
        action="retail.stock_out",
        target_type="retail_sku",
        target_id=sku.id,
        summary=f"出库 -{quantity}",
        actor_staff_id=actor_staff_id,
        merchant_id=sku.merchant_id,
    )
    return sku


def stock_adjust(
    db: Session,
    sku_id: int,
    target_qty: int,
    *,
    note: str | None = None,
    actor_staff_id: int | None = None,
) -> RetailSku:
    if target_qty < 0:
        raise AppError("invalid_qty", "盘点目标不可为负", status_code=400)
    sku = _lock_sku(db, sku_id)
    delta = target_qty - sku.stock_qty
    apply_stock_delta(
        db,
        sku,
        delta=delta,
        movement_type=StockMovementType.ADJUST.value,
        note=note or f"盘点至 {target_qty}",
        actor_staff_id=actor_staff_id,
    )
    write_audit(
        db,
        action="retail.stock_adjust",
        target_type="retail_sku",
        target_id=sku.id,
        summary=f"盘点至 {target_qty} (delta={delta})",
        actor_staff_id=actor_staff_id,
        merchant_id=sku.merchant_id,
    )
    return sku
