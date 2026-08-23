"""餐饮桌台：点餐码生成、会员扫码链接、订单备注里的桌号。"""

from __future__ import annotations

import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.systems.catering.models.catering import CateringTable

_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_table_code(db: Session) -> str:
    """生成桌台点餐码，去掉易混字符。"""
    for _ in range(20):
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))
        if db.scalar(select(CateringTable.id).where(CateringTable.code == code)) is None:
            return code
    raise AppError("code_exhausted", "桌号点餐码生成失败，请重试", status_code=500)


def dining_order_url(*, merchant_id: int, code: str) -> str:
    """会员 H5 点餐落地页：未登录会带 merchant_id 走登录并回跳。"""
    base = get_settings().member_web_public_url.rstrip("/")
    return f"{base}/m/{merchant_id}/catering?table={code}"


def get_active_table(db: Session, *, merchant_id: int, code: str) -> CateringTable:
    token = (code or "").strip().upper()
    if not token:
        raise AppError("not_found", "桌号不存在", status_code=404)
    row = db.scalar(
        select(CateringTable).where(
            CateringTable.merchant_id == merchant_id,
            CateringTable.code == token,
        )
    )
    if row is None:
        raise AppError("not_found", "桌号不存在", status_code=404)
    if not row.is_active:
        raise AppError("table_inactive", "该桌已停用", status_code=400)
    return row


def split_dining_note(note: str | None) -> tuple[str | None, str | None]:
    """从 customer_note 拆出桌号与宾客备注。"""
    text = (note or "").strip()
    if not text:
        return None, None
    if text.startswith("桌号:"):
        rest = text[3:]
        if "；" in rest:
            table, remark = rest.split("；", 1)
            return table.strip() or None, remark.strip() or None
        return rest.strip() or None, None
    return None, text


def compose_dining_note(*, table_no: str | None, note: str | None) -> str | None:
    parts: list[str] = []
    if table_no and table_no.strip():
        parts.append(f"桌号:{table_no.strip()}")
    if note and note.strip():
        parts.append(note.strip())
    text = "；".join(parts)[:255]
    return text or None


def require_active_table_label(db: Session, *, merchant_id: int, table_no: str) -> CateringTable:
    """按桌名或点餐码校验仍在用的桌台。"""
    label = (table_no or "").strip()
    if not label:
        raise AppError("invalid_table", "请填写有效桌号", status_code=400)
    row = db.scalar(
        select(CateringTable).where(
            CateringTable.merchant_id == merchant_id,
            CateringTable.name == label,
        )
    )
    if row is None:
        try:
            return get_active_table(db, merchant_id=merchant_id, code=label)
        except AppError:
            raise AppError("invalid_table", "桌号无效或已停用", status_code=400) from None
    if not row.is_active:
        raise AppError("table_inactive", "该桌已停用", status_code=400)
    return row


def list_active_tables(db: Session, *, merchant_id: int) -> list[CateringTable]:
    """点单用的启用桌清单。"""
    return list(
        db.scalars(
            select(CateringTable)
            .where(CateringTable.merchant_id == merchant_id, CateringTable.is_active.is_(True))
            .order_by(CateringTable.sort_order.asc(), CateringTable.id.asc())
        ).all()
    )
