"""场地短信通道与模版。"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class SiteSmsSettings(Base):
    __tablename__ = "site_sms_settings"

    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="http")
    api_base_url: Mapped[str | None] = mapped_column(String(512))
    api_key_enc: Mapped[str | None] = mapped_column(Text)
    api_secret_enc: Mapped[str | None] = mapped_column(Text)
    sign_name: Mapped[str | None] = mapped_column(String(64))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    updated_by_staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"))


class SmsTemplate(Base):
    __tablename__ = "sms_templates"
    __table_args__ = (UniqueConstraint("site_id", "code", name="uq_sms_templates_site_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    scene: Mapped[str] = mapped_column(String(32), nullable=False, default="otp")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
