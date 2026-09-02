"""运维：服务状态与错误日志。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import RequestContext, get_current_context
from app.core.health import collect_readiness
from app.core.schemas.paging import PageOut, paginate
from app.systems.platform.models.error_event import ErrorEvent
from app.systems.platform.models.org import Merchant

router = APIRouter(prefix="/ops", tags=["ops"])


class HealthCheckOut(BaseModel):
    ok: bool
    detail: str | None = None


class OpsHealthOut(BaseModel):
    status: str
    postgres: HealthCheckOut
    minio: HealthCheckOut
    error_count_24h: int


class ErrorEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_id: str | None
    audit_log_id: int | None = None
    level: str
    source: str
    error_code: str
    status_code: int | None
    message: str
    exception_type: str | None
    stack_trace: str | None
    http_method: str | None
    request_path: str | None
    client_channel: str | None
    subsystem_code: str | None
    module: str | None
    actor_type: str | None
    actor_name: str | None
    site_id: int | None
    merchant_id: int | None
    merchant_name: str | None = None
    client_ip: str | None
    extra_json: dict[str, Any] | None
    created_at: datetime


@router.get("/health-status", response_model=OpsHealthOut)
def ops_health_status(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("devops:read")
    ready = collect_readiness()
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    stmt = select(func.count()).select_from(ErrorEvent).where(ErrorEvent.created_at >= since)
    if not ctx.is_site_wide:
        stmt = stmt.where(ErrorEvent.merchant_id == ctx.resolve_merchant_id())
    count = db.scalar(stmt) or 0
    return OpsHealthOut(
        status=ready["status"],
        postgres=HealthCheckOut(**ready["postgres"]),
        minio=HealthCheckOut(**ready["minio"]),
        error_count_24h=int(count),
    )


@router.get("/error-events", response_model=PageOut[ErrorEventOut])
def list_error_events(
    module: str | None = None,
    error_code: str | None = None,
    request_id: str | None = None,
    q: str | None = None,
    merchant_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("devops:read")
    stmt = select(ErrorEvent)
    if ctx.is_site_wide:
        if merchant_id is not None:
            stmt = stmt.where(ErrorEvent.merchant_id == merchant_id)
    else:
        stmt = stmt.where(ErrorEvent.merchant_id == ctx.resolve_merchant_id())
    if module and module.strip():
        stmt = stmt.where(ErrorEvent.module.ilike(f"%{module.strip()}%"))
    if error_code and error_code.strip():
        stmt = stmt.where(ErrorEvent.error_code == error_code.strip())
    if request_id and request_id.strip():
        stmt = stmt.where(ErrorEvent.request_id == request_id.strip())
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(
                ErrorEvent.message.ilike(like),
                ErrorEvent.error_code.ilike(like),
                ErrorEvent.request_path.ilike(like),
                ErrorEvent.request_id.ilike(like),
            )
        )
    rows, total = paginate(db, stmt.order_by(ErrorEvent.id.desc()), page=page, page_size=page_size)
    merchant_ids = {r.merchant_id for r in rows if r.merchant_id is not None}
    names: dict[int, str] = {}
    if merchant_ids:
        names = {
            m.id: m.name for m in db.scalars(select(Merchant).where(Merchant.id.in_(merchant_ids))).all()
        }
    items = [
        ErrorEventOut(
            id=row.id,
            request_id=row.request_id,
            audit_log_id=row.audit_log_id,
            level=row.level,
            source=row.source,
            error_code=row.error_code,
            status_code=row.status_code,
            message=row.message,
            exception_type=row.exception_type,
            stack_trace=row.stack_trace,
            http_method=row.http_method,
            request_path=row.request_path,
            client_channel=row.client_channel,
            subsystem_code=row.subsystem_code,
            module=row.module,
            actor_type=row.actor_type,
            actor_name=row.actor_name,
            site_id=row.site_id,
            merchant_id=row.merchant_id,
            merchant_name=names.get(row.merchant_id) if row.merchant_id else None,
            client_ip=row.client_ip,
            extra_json=row.extra_json,
            created_at=row.created_at,
        )
        for row in rows
    ]
    return PageOut(items=items, total=total, page=page, page_size=page_size)
