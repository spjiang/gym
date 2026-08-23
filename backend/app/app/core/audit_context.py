"""请求级审计上下文：中间件写入、业务 write_audit 读取。"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

_audit_envelope: ContextVar[AuditEnvelope | None] = ContextVar("audit_envelope", default=None)


@dataclass
class AuditEnvelope:
    """单次 HTTP 请求可复用的审计元数据。"""

    http_method: str | None = None
    request_path: str | None = None
    client_ip: str | None = None
    user_agent: str | None = None
    client_channel: str | None = None
    subsystem_code: str | None = None
    module: str | None = None
    actor_type: str | None = None
    actor_staff_id: int | None = None
    actor_member_id: int | None = None
    actor_name: str | None = None
    actor_account: str | None = None
    site_id: int | None = None
    merchant_id: int | None = None
    status: str | None = None
    status_code: int | None = None
    duration_ms: int | None = None
    detail: dict[str, Any] = field(default_factory=dict)
    skip_auto: bool = False

    def as_write_kwargs(self) -> dict[str, Any]:
        return {
            "http_method": self.http_method,
            "request_path": self.request_path,
            "client_ip": self.client_ip,
            "user_agent": self.user_agent,
            "client_channel": self.client_channel,
            "subsystem_code": self.subsystem_code,
            "module": self.module,
            "actor_type": self.actor_type,
            "actor_staff_id": self.actor_staff_id,
            "actor_member_id": self.actor_member_id,
            "actor_name": self.actor_name,
            "actor_account": self.actor_account,
            "site_id": self.site_id,
            "merchant_id": self.merchant_id,
            "status": self.status,
            "status_code": self.status_code,
            "duration_ms": self.duration_ms,
            "detail_json": dict(self.detail) if self.detail else None,
        }


def set_audit_envelope(env: AuditEnvelope | None) -> None:
    _audit_envelope.set(env)


def get_audit_envelope() -> AuditEnvelope | None:
    return _audit_envelope.get()


def mark_audit_logged() -> None:
    env = get_audit_envelope()
    if env is not None:
        env.skip_auto = True


def merge_audit_detail(**kwargs: Any) -> None:
    env = get_audit_envelope()
    if env is not None:
        env.detail.update(kwargs)
