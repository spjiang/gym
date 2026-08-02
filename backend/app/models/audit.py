"""审计日志。"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id"), index=True)
    merchant_id: Mapped[int | None] = mapped_column(ForeignKey("merchants.id"), index=True)
    actor_staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"), index=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
