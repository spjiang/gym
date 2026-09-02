"""审计日志。"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.systems.platform.models.identity import JSONType


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id"), index=True)
    merchant_id: Mapped[int | None] = mapped_column(ForeignKey("merchants.id"), index=True)
    actor_staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"), index=True)
    actor_member_id: Mapped[int | None] = mapped_column(ForeignKey("members.id"), index=True)
    actor_type: Mapped[str | None] = mapped_column(String(32), index=True)
    actor_name: Mapped[str | None] = mapped_column(String(128))
    actor_account: Mapped[str | None] = mapped_column(String(64))
    subsystem_code: Mapped[str | None] = mapped_column(String(32), index=True)
    module: Mapped[str | None] = mapped_column(String(64), index=True)
    client_channel: Mapped[str | None] = mapped_column(String(32), index=True)
    http_method: Mapped[str | None] = mapped_column(String(16))
    request_path: Mapped[str | None] = mapped_column(String(512))
    client_ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[str | None] = mapped_column(String(16), index=True)
    status_code: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    request_id: Mapped[str | None] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    detail_json: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
