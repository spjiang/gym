"""操作日志（审计）查询 API。"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import RequestContext, get_current_context
from app.core.errors import AppError
from app.core.schemas.paging import PageOut, paginate
from app.systems.platform.models.audit import AuditLog
from app.systems.platform.models.org import Merchant

router = APIRouter(tags=["audit-logs"])


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    site_id: int | None
    merchant_id: int | None
    merchant_name: str | None = None
    actor_staff_id: int | None
    actor_member_id: int | None
    actor_type: str | None
    actor_name: str | None = None
    actor_account: str | None = None
    subsystem_code: str | None
    module: str | None
    client_channel: str | None
    http_method: str | None
    request_path: str | None
    client_ip: str | None
    user_agent: str | None
    status: str | None
    status_code: int | None
    duration_ms: int | None
    action: str
    target_type: str
    target_id: str
    summary: str
    detail_json: dict[str, Any] | None
    created_at: datetime


def _day_bounds(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    start = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
    end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
    return start, end


@router.get("/audit-logs", response_model=PageOut[AuditLogOut])
def list_audit_logs(
    merchant_id: int | None = None,
    subsystem_code: str | None = None,
    module: str | None = None,
    client_channel: str | None = None,
    actor_type: str | None = None,
    action: str | None = None,
    target_type: str | None = None,
    actor_staff_id: int | None = None,
    actor_member_id: int | None = None,
    status: str | None = None,
    q: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """操作日志：按子系统、客户端、操作人与时间筛选，便于追溯。"""
    ctx.require_permission("audit:read")
    stmt = select(AuditLog).where(AuditLog.site_id == ctx.site_id)
    if ctx.is_site_wide:
        if merchant_id is not None:
            stmt = stmt.where(AuditLog.merchant_id == merchant_id)
    else:
        mid = ctx.resolve_merchant_id(merchant_id)
        stmt = stmt.where(
            or_(AuditLog.merchant_id == mid, AuditLog.merchant_id.is_(None))
        )
    if subsystem_code and subsystem_code.strip():
        stmt = stmt.where(AuditLog.subsystem_code == subsystem_code.strip())
    if module and module.strip():
        stmt = stmt.where(AuditLog.module.ilike(f"%{module.strip()}%"))
    if client_channel and client_channel.strip():
        stmt = stmt.where(AuditLog.client_channel == client_channel.strip())
    if actor_type and actor_type.strip():
        stmt = stmt.where(AuditLog.actor_type == actor_type.strip())
    if action and action.strip():
        stmt = stmt.where(AuditLog.action.ilike(f"%{action.strip()}%"))
    if target_type and target_type.strip():
        stmt = stmt.where(AuditLog.target_type == target_type.strip())
    if actor_staff_id is not None:
        stmt = stmt.where(AuditLog.actor_staff_id == actor_staff_id)
    if actor_member_id is not None:
        stmt = stmt.where(AuditLog.actor_member_id == actor_member_id)
    if status and status.strip():
        stmt = stmt.where(AuditLog.status == status.strip())
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(
                AuditLog.summary.ilike(like),
                AuditLog.action.ilike(like),
                AuditLog.target_type.ilike(like),
                AuditLog.target_id.ilike(like),
                AuditLog.actor_name.ilike(like),
                AuditLog.actor_account.ilike(like),
                AuditLog.request_path.ilike(like),
                AuditLog.module.ilike(like),
            )
        )
    if date_from is not None and date_to is not None:
        if date_to < date_from:
            raise AppError("invalid_range", "结束日期不得早于开始日期", status_code=400)
        start, end = _day_bounds(date_from, date_to)
        stmt = stmt.where(AuditLog.created_at >= start, AuditLog.created_at < end)

    rows, total = paginate(
        db, stmt.order_by(AuditLog.id.desc()), page=page, page_size=page_size
    )
    merchant_ids = {r.merchant_id for r in rows if r.merchant_id is not None}
    merchant_names: dict[int, str] = {}
    if merchant_ids:
        merchant_names = {
            m.id: m.name
            for m in db.scalars(select(Merchant).where(Merchant.id.in_(merchant_ids))).all()
        }
    items = [
        AuditLogOut(
            id=row.id,
            site_id=row.site_id,
            merchant_id=row.merchant_id,
            merchant_name=merchant_names.get(row.merchant_id) if row.merchant_id else None,
            actor_staff_id=row.actor_staff_id,
            actor_member_id=row.actor_member_id,
            actor_type=row.actor_type,
            actor_name=row.actor_name,
            actor_account=row.actor_account,
            subsystem_code=row.subsystem_code,
            module=row.module,
            client_channel=row.client_channel,
            http_method=row.http_method,
            request_path=row.request_path,
            client_ip=row.client_ip,
            user_agent=row.user_agent,
            status=row.status,
            status_code=row.status_code,
            duration_ms=row.duration_ms,
            action=row.action,
            target_type=row.target_type,
            target_id=row.target_id,
            summary=row.summary,
            detail_json=row.detail_json,
            created_at=row.created_at,
        )
        for row in rows
    ]
    return PageOut(items=items, total=total, page=page, page_size=page_size)
