"""系统错误写入：独立会话，避免业务回滚带走记录。"""

from __future__ import annotations

import logging
import traceback
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.core import db as db_module
from app.core.audit_context import get_audit_envelope
from app.core.errors import AppError
from app.core.request_id import error_already_recorded, get_request_id, mark_error_recorded
from app.systems.platform.models.error_event import ErrorEvent
from app.systems.platform.services.audit_catalog import sanitize_audit_payload

logger = logging.getLogger(__name__)

STACK_LIMIT = 8000
MESSAGE_LIMIT = 2000
RETENTION_DAYS = 30

# 支付通道/回调/金额不一致：即使是 AppError 也进错误表
PAYMENT_SYSTEM_CODES = {
    "wechat_api_error",
    "wechat_unconfigured",
    "wechat_notify_invalid",
    "wechat_notify_rejected",
    "online_payment_unconfigured",
    "online_pay_failed",
    "amount_mismatch",
}


def should_persist_app_error(exc: AppError) -> bool:
    if exc.status_code >= 500:
        return True
    return exc.code in PAYMENT_SYSTEM_CODES


def _clip(text: str | None, limit: int) -> str | None:
    if not text:
        return None
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


def record_error(
    *,
    error_code: str,
    message: str,
    status_code: int | None = None,
    source: str = "api",
    level: str = "error",
    exc: BaseException | None = None,
    request: Request | None = None,
    extra: dict[str, Any] | None = None,
    stack_trace: str | None = None,
) -> None:
    """写入错误事件；失败只打日志，不影响主流程。同一请求只记一次。"""
    if error_already_recorded():
        return
    mark_error_recorded()
    env = get_audit_envelope()
    rid = get_request_id()
    path = request.url.path if request is not None else (env.request_path if env else None)
    method = request.method if request is not None else (env.http_method if env else None)
    tb = stack_trace
    exc_type = None
    if exc is not None:
        exc_type = type(exc).__name__
        if tb is None:
            tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    extra_clean = sanitize_audit_payload(extra) if extra else None

    session: Session = db_module.SessionLocal()
    try:
        event = ErrorEvent(
            request_id=rid,
            level=level,
            source=source,
            error_code=error_code,
            status_code=status_code,
            message=_clip(message, MESSAGE_LIMIT) or error_code,
            exception_type=exc_type,
            stack_trace=_clip(tb, STACK_LIMIT),
            http_method=method,
            request_path=path,
            client_channel=env.client_channel if env else None,
            subsystem_code=env.subsystem_code if env else None,
            module=env.module if env else None,
            actor_type=env.actor_type if env else None,
            actor_staff_id=env.actor_staff_id if env else None,
            actor_member_id=env.actor_member_id if env else None,
            actor_name=env.actor_name if env else None,
            site_id=env.site_id if env else None,
            merchant_id=env.merchant_id if env else None,
            client_ip=env.client_ip if env else None,
            extra_json=extra_clean,
        )
        session.add(event)
        cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
        session.execute(delete(ErrorEvent).where(ErrorEvent.created_at < cutoff))
        session.commit()
    except Exception:  # noqa: BLE001
        session.rollback()
        logger.exception("写入错误事件失败 error_code=%s path=%s", error_code, path)
    finally:
        session.close()


def record_notify_failure(request: Request, message: str, *, extra: dict[str, Any] | None = None) -> dict[str, str]:
    """支付回调失败：记错误并返回微信 FAIL 体。"""
    record_error(
        error_code="wechat_notify_invalid",
        message=message,
        status_code=400,
        request=request,
        extra=extra,
    )
    return {"code": "FAIL", "message": message}
