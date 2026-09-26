"""场地短信通道与模版。"""

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.systems.platform.models.identity import JSONType


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


class SmsSendLog(Base):
    """平台发出的短信，含测试与会员验证码。"""

    __tablename__ = "sms_send_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    scene: Mapped[str] = mapped_column(String(32), nullable=False, default="otp")
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="aliyun")
    template_code: Mapped[str | None] = mapped_column(String(64))
    sign_name: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="failed")
    provider_code: Mapped[str | None] = mapped_column(String(64))
    provider_message: Mapped[str | None] = mapped_column(String(512))
    request_json: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    response_json: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
