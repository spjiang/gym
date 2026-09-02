"""审计写入。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.audit_context import get_audit_envelope, mark_audit_logged
from app.systems.platform.models.audit import AuditLog


def write_audit(
    db: Session,
    *,
    action: str,
    target_type: str,
    target_id: str | int,
    summary: str,
    actor_staff_id: int | None = None,
    actor_member_id: int | None = None,
    actor_type: str | None = None,
    actor_name: str | None = None,
    actor_account: str | None = None,
    site_id: int | None = None,
    merchant_id: int | None = None,
    subsystem_code: str | None = None,
    module: str | None = None,
    client_channel: str | None = None,
    http_method: str | None = None,
    request_path: str | None = None,
    client_ip: str | None = None,
    user_agent: str | None = None,
    status: str | None = "success",
    status_code: int | None = None,
    duration_ms: int | None = None,
    request_id: str | None = None,
    detail_json: dict[str, Any] | None = None,
) -> AuditLog:
    env_kwargs = get_audit_envelope().as_write_kwargs() if get_audit_envelope() else {}
    explicit = {
        "actor_staff_id": actor_staff_id,
        "actor_member_id": actor_member_id,
        "actor_type": actor_type,
        "actor_name": actor_name,
        "actor_account": actor_account,
        "site_id": site_id,
        "merchant_id": merchant_id,
        "subsystem_code": subsystem_code,
        "module": module,
        "client_channel": client_channel,
        "http_method": http_method,
        "request_path": request_path,
        "client_ip": client_ip,
        "user_agent": user_agent,
        "status": status,
        "status_code": status_code,
        "duration_ms": duration_ms,
        "request_id": request_id,
        "detail_json": detail_json,
    }
    merged = {**env_kwargs, **{k: v for k, v in explicit.items() if v is not None}}

    if merged.get("actor_staff_id") and not merged.get("actor_type"):
        merged["actor_type"] = "staff"
    elif merged.get("actor_member_id") and not merged.get("actor_type"):
        merged["actor_type"] = "member"
    elif not merged.get("actor_type"):
        merged["actor_type"] = "system"

    log = AuditLog(
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        summary=summary,
        actor_staff_id=merged.get("actor_staff_id"),
        actor_member_id=merged.get("actor_member_id"),
        actor_type=merged.get("actor_type"),
        actor_name=merged.get("actor_name"),
        actor_account=merged.get("actor_account"),
        site_id=merged.get("site_id"),
        merchant_id=merged.get("merchant_id"),
        subsystem_code=merged.get("subsystem_code"),
        module=merged.get("module"),
        client_channel=merged.get("client_channel"),
        http_method=merged.get("http_method"),
        request_path=merged.get("request_path"),
        client_ip=merged.get("client_ip"),
        user_agent=merged.get("user_agent"),
        status=merged.get("status"),
        status_code=merged.get("status_code"),
        duration_ms=merged.get("duration_ms"),
        request_id=merged.get("request_id"),
        detail_json=merged.get("detail_json"),
    )
    db.add(log)
    db.flush()
    mark_audit_logged()
    return log
