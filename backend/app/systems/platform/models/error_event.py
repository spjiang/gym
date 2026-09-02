"""系统错误事件。"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.systems.platform.models.identity import JSONType


class ErrorEvent(Base):
    __tablename__ = "error_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[str | None] = mapped_column(String(64), index=True)
    audit_log_id: Mapped[int | None] = mapped_column(ForeignKey("audit_logs.id"))
    level: Mapped[str] = mapped_column(String(16), nullable=False, default="error")
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="api")
    error_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status_code: Mapped[int | None] = mapped_column(Integer)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    exception_type: Mapped[str | None] = mapped_column(String(128))
    stack_trace: Mapped[str | None] = mapped_column(Text)
    http_method: Mapped[str | None] = mapped_column(String(16))
    request_path: Mapped[str | None] = mapped_column(String(512))
    client_channel: Mapped[str | None] = mapped_column(String(32))
    subsystem_code: Mapped[str | None] = mapped_column(String(32))
    module: Mapped[str | None] = mapped_column(String(64), index=True)
    actor_type: Mapped[str | None] = mapped_column(String(32))
    actor_staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"))
    actor_member_id: Mapped[int | None] = mapped_column(ForeignKey("members.id"))
    actor_name: Mapped[str | None] = mapped_column(String(128))
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id"), index=True)
    merchant_id: Mapped[int | None] = mapped_column(ForeignKey("merchants.id"), index=True)
    client_ip: Mapped[str | None] = mapped_column(String(64))
    extra_json: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
